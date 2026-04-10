"""Diagnose L0 cases where llm_code_agent passes but support_plan_agent fails.

For each sampled case, classify:
- recall: gold (source_id, column) for at least one output slot is not in per-slot
  top-k output binding candidates (same pool as search._best_output_bindings).
- rerank: gold appears in all per-slot pools, but best_plan output bindings do not match gold.
- compiler: best_plan output bindings match gold, but compile/execute/score still fails
  (pipeline issue after correct output pick).

Usage:
  python -m evaluation.diagnose_support_recall_l0 \\
    --bench_root outputs/hdrbench_full150_v1 \\
    --report_support outputs/full150_support_v3_l0_ABC/report_support_plan_agent.json \\
    --report_llm outputs/full150_llm_l0_ABC/report_llm_code_agent.json \\
    --variant A --max_cases 20 --out outputs/analysis/support_recall_diag_l0.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.run_hdrbench_eval import _load_json
from evaluation.scorer import score_single
from evaluation.support_plan_agent.compiler import compile_support_plan
from evaluation.support_plan_agent.ir import build_support_plan_ir
from evaluation.support_plan_agent.probes import (
    CaseContext,
    GoldBinding,
    _resolve_gold_column,
    _resolve_gold_source,
    prepare_case_context,
)
from evaluation.support_plan_agent.search import _best_output_bindings, search_support_plans
from evaluation.support_plan_agent.types import Binding
from evaluation.workspace_catalog import tokenize


def _load_variant_records(report_path: Path, split: str, variant: str) -> Dict[str, Dict[str, Any]]:
    report = _load_json(report_path)
    out: Dict[str, Dict[str, Any]] = {}
    for rec in report.get("records", []):
        if rec.get("split") != split or rec.get("variant") != variant:
            continue
        out[str(rec["seed_id"])] = rec
    return out


def _binding_matches_gold(plan_b: Binding, gold: GoldBinding, source) -> bool:
    if plan_b.source_id != gold.source_id:
        return False
    resolved = _resolve_gold_column(source, gold)
    if resolved is None:
        return False
    return plan_b.column_name.lower() == resolved.lower()


def _gold_primary_output_bindings(context: CaseContext) -> List[Tuple[str, GoldBinding]]:
    """(slot_label, gold_binding) for each required output slot; skip if unresolvable."""
    rows: List[Tuple[str, GoldBinding]] = []
    for slot in context.observable_sketch.output_slots:
        label = slot.label
        bindings = context.gold_targets.output_bindings_by_label.get(label, [])
        if not bindings:
            continue
        gold = bindings[0]
        src = _resolve_gold_source(context, gold)
        if src is None or gold.source_id is None:
            continue
        col = _resolve_gold_column(src, gold)
        if col is None:
            continue
        rows.append((label, gold))
    return rows


def _gold_in_candidate_pools(
    context: CaseContext,
    ranked: Dict[str, List[Binding]],
    gold_pairs: List[Tuple[str, GoldBinding]],
) -> Tuple[bool, List[str]]:
    missing: List[str] = []
    for label, gold in gold_pairs:
        pool = ranked.get(label, [])
        src = _resolve_gold_source(context, gold)
        if src is None:
            missing.append(f"{label}:unresolved_source")
            continue
        ok = any(_binding_matches_gold(b, gold, src) for b in pool)
        if not ok:
            missing.append(label)
    return len(missing) == 0, missing


def _top1_output_matches_gold(context: CaseContext, plan, gold_pairs: List[Tuple[str, GoldBinding]]) -> bool:
    if len(plan.output_bindings) != len(gold_pairs):
        return False
    for plan_b, (label, gold) in zip(plan.output_bindings, gold_pairs):
        if plan_b.metadata.get("slot_label", label) != label and plan_b.metadata.get("slot_label"):
            # Order should follow observable_sketch.output_slots
            pass
        src = _resolve_gold_source(context, gold)
        if src is None:
            return False
        if not _binding_matches_gold(plan_b, gold, src):
            return False
    return True


def _compiler_failure_kind(compile_meta: Dict[str, Any], score: Dict[str, Any]) -> str:
    """Rough bucket for compiler-category rows (output matches gold but eval fails)."""
    reason = str(compile_meta.get("reason") or "")
    if not compile_meta.get("executed"):
        rl = reason.lower()
        if "syntax" in rl or "parser" in rl:
            return "sql_syntax"
        if "unmet" in rl or "obligation" in rl or "ir" in rl:
            return "ir_or_obligation_blocked"
        if not compile_meta.get("compiled"):
            return "compile_failed"
        return "execute_failed"
    stage = str(score.get("stage") or "")
    if stage == "QUERY_FAIL":
        return "wrong_result_or_empty"
    return "other"


def classify_case(
    context: CaseContext,
    *,
    output_top_k: int,
) -> Dict[str, Any]:
    question_tok = tokenize(context.instruction)
    ranked = _best_output_bindings(context.observable_sketch, context.catalog, question_tok, top_k=output_top_k)
    gold_pairs = _gold_primary_output_bindings(context)
    if not gold_pairs:
        return {
            "category": "gold_parse_skip",
            "reason": "no_resolvable_gold_output_bindings",
            "gold_pairs_count": 0,
        }

    all_in_pool, missing_labels = _gold_in_candidate_pools(context, ranked, gold_pairs)
    if not all_in_pool:
        return {
            "category": "recall",
            "missing_slots": missing_labels,
            "gold_pairs": [(l, g.source_id, _resolve_gold_column(_resolve_gold_source(context, g), g)) for l, g in gold_pairs],
        }

    search_summary = search_support_plans(
        instruction=context.instruction,
        observable_sketch=context.observable_sketch,
        obligation_sketch=context.obligation_sketch,
        catalog=context.catalog,
    )
    best = search_summary["best_plan"]
    if not best.output_bindings:
        return {"category": "rerank", "reason": "empty_best_plan despite gold_in_pool"}

    top1_ok = _top1_output_matches_gold(context, best, gold_pairs)
    if not top1_ok:
        return {
            "category": "rerank",
            "reason": "best_plan_output_mismatch",
            "best_output": [(b.source_id, b.column_name) for b in best.output_bindings],
            "gold_output": [(g.source_id, _resolve_gold_column(_resolve_gold_source(context, g), g)) for _, g in gold_pairs],
        }

    plan_ir = build_support_plan_ir(best, context.observable_sketch, context.obligation_sketch, context.catalog)
    with tempfile.TemporaryDirectory() as tmp:
        out_csv = Path(tmp) / "out.csv"
        compile_meta = compile_support_plan(best, plan_ir, context.catalog, context.deliverable_spec, out_csv)
        score = score_single(out_csv, context.gold_path, context.deliverable_spec)
        passed = bool(score.get("pass"))
        if passed:
            return {
                "category": "unexpected_pass",
                "reason": "top1_matches_gold_and_passes",
                "score": float(score.get("score", 0)),
            }
        return {
            "category": "compiler",
            "compiler_failure_kind": _compiler_failure_kind(compile_meta, score),
            "reason": "output_matches_gold_but_eval_fail",
            "compile_meta": {
                "compiled": compile_meta.get("compiled"),
                "executed": compile_meta.get("executed"),
                "reason": compile_meta.get("reason"),
            },
            "score": float(score.get("score", 0)),
            "stage": score.get("stage"),
            "final_sql": compile_meta.get("final_sql"),
        }


def run_diagnosis(
    bench_root: Path,
    report_support: Path,
    report_llm: Path,
    *,
    variant: str = "A",
    split: str = "l0",
    max_cases: int = 20,
    output_top_k: int = 4,
    sketch_mode: str = "live",
) -> Dict[str, Any]:
    sup = _load_variant_records(report_support, split, variant)
    llm = _load_variant_records(report_llm, split, variant)
    pool: List[str] = []
    for seed_id in sorted(sup.keys()):
        if seed_id not in llm:
            continue
        if not llm[seed_id].get("pass"):
            continue
        if sup[seed_id].get("pass"):
            continue
        pool.append(seed_id)
    seeds = pool[:max_cases]

    rows: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {"recall": 0, "rerank": 0, "compiler": 0, "gold_parse_skip": 0, "unexpected_pass": 0, "error": 0}
    compiler_kind_counts: Dict[str, int] = {}

    for seed_id in seeds:
        seed_dir = bench_root / seed_id
        pub = _load_json(seed_dir / "variants" / variant / "manifest_public.json")
        pri = _load_json(seed_dir / "variants" / variant / "manifest_private.json")
        try:
            context = prepare_case_context(
                pub,
                pri,
                split=split,
                view="full",
                sketch_mode=sketch_mode,
                namespace=f"support_recall_diag_{seed_id}",
            )
            detail = classify_case(context, output_top_k=output_top_k)
            detail["seed_id"] = seed_id
            detail["sketch_mode_used"] = context.sketch_mode
            cat = detail.get("category", "error")
            if cat in counts:
                counts[cat] += 1
            if detail.get("category") == "compiler" and detail.get("compiler_failure_kind"):
                k = str(detail["compiler_failure_kind"])
                compiler_kind_counts[k] = compiler_kind_counts.get(k, 0) + 1
            rows.append(detail)
        except Exception as exc:  # noqa: BLE001
            counts["error"] += 1
            rows.append({"seed_id": seed_id, "category": "error", "error": str(exc)})

    n = len(seeds)
    recall_n = counts["recall"]
    rerank_n = counts["rerank"]
    compiler_n = counts["compiler"]
    denom = max(n - counts["gold_parse_skip"] - counts["error"], 1)
    if recall_n >= rerank_n and recall_n >= compiler_n:
        bottleneck = "recall (expand per-slot top_k / output signals)"
    elif rerank_n >= compiler_n:
        bottleneck = "rerank / combo selection (joint_rerank, obligation, sketch roles)"
    else:
        bottleneck = "compile & execute path (support CTE, filter joins, SQL shape)"

    return {
        "bench_root": str(bench_root),
        "split": split,
        "variant": variant,
        "report_support": str(report_support),
        "report_llm": str(report_llm),
        "criteria": "llm_pass_and_support_fail",
        "output_candidate_top_k": output_top_k,
        "sample_size_requested": max_cases,
        "matching_pool_size": len(pool),
        "sampled_seed_count": len(seeds),
        "seed_ids": seeds,
        "counts": counts,
        "rows": rows,
        "summary": {
            "bottleneck_guess": bottleneck,
            "compiler_failure_kind_counts": compiler_kind_counts,
            "note": "Among classifiable cases only (excludes gold_parse_skip/error). "
            "recall = gold output not in per-slot top_k; rerank = in pool but best_plan mismatch; "
            "compiler = top1 output matches gold but score still fails.",
            "classifiable": denom,
            "recall_share": round(recall_n / denom, 4),
            "rerank_share": round(rerank_n / denom, 4),
            "compiler_share": round(compiler_n / denom, 4),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="L0 recall vs rerank vs compiler diagnosis (support fail, llm pass).")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--report_support", required=True)
    parser.add_argument("--report_llm", required=True)
    parser.add_argument("--variant", default="A")
    parser.add_argument("--split", default="l0")
    parser.add_argument("--max_cases", type=int, default=20)
    parser.add_argument("--output_top_k", type=int, default=4, help="Must match search._best_output_bindings default (4).")
    parser.add_argument("--sketch_mode", default="live", choices=["live", "fallback"])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    payload = run_diagnosis(
        bench_root=Path(args.bench_root),
        report_support=Path(args.report_support),
        report_llm=Path(args.report_llm),
        variant=args.variant,
        split=args.split,
        max_cases=args.max_cases,
        output_top_k=args.output_top_k,
        sketch_mode=args.sketch_mode,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(out_path),
                "counts": payload["counts"],
                "n": payload["sampled_seed_count"],
                "matching_pool_size": payload.get("matching_pool_size"),
                "summary": payload.get("summary"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
