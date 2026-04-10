from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.motif_taxonomy import build_seed_motif_index
from evaluation.run_hdrbench_eval import _list_seed_dirs, _load_json
from evaluation.scorer import score_single
from evaluation.support_plan_agent import run_support_plan_agent
from evaluation.support_plan_agent.diagnostics import classify_failure
from evaluation.support_plan_agent.probes import prepare_case_context, run_probe


PROBE_SEQUENCE = [
    "baseline",
    "oracle_output",
    "joint_rerank",
    "oracle_filter",
    "typed_filter_strict",
    "oracle_measure_anchor",
    "oracle_all",
    "sensitivity_topk_hops",
]


def _load_variant_a_rows(report_path: Path) -> Dict[str, Dict[str, Any]]:
    report = _load_json(report_path)
    return {
        str(rec["seed_id"]): rec
        for rec in report.get("records", [])
        if rec.get("variant") == "A"
    }


def select_probe_samples(
    report_by_split: Dict[str, Dict[str, Dict[str, Any]]],
    seed_motifs: Dict[str, Dict[str, Any]],
    *,
    splits: Iterable[str] = ("l1", "l2"),
    motifs: Iterable[str] = ("SimpleJoin", "FilterJoin", "AggregationJoin"),
    filter_kind_index: Dict[Tuple[str, str], str] | None = None,
    filter_kinds: Iterable[str] | None = None,
    per_group: int = 6,
    fail_target: int = 4,
    pass_target: int = 2,
    random_seed: int = 13,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    allowed_filter_kinds = {str(item) for item in (filter_kinds or [])}
    for split in splits:
        rows = report_by_split[split]
        for motif in motifs:
            failed = sorted(
                seed_id
                for seed_id, rec in rows.items()
                if (
                    not rec.get("pass")
                    and seed_motifs[seed_id]["base_label"] == motif
                    and (
                        not allowed_filter_kinds
                        or (filter_kind_index is not None and filter_kind_index.get((seed_id, split)) in allowed_filter_kinds)
                    )
                )
            )
            passed = sorted(
                seed_id
                for seed_id, rec in rows.items()
                if (
                    rec.get("pass")
                    and seed_motifs[seed_id]["base_label"] == motif
                    and (
                        not allowed_filter_kinds
                        or (filter_kind_index is not None and filter_kind_index.get((seed_id, split)) in allowed_filter_kinds)
                    )
                )
            )
            rng = random.Random(f"{random_seed}:{split}:{motif}")
            rng.shuffle(failed)
            rng.shuffle(passed)

            picked_fail = failed[:fail_target]
            picked_pass = passed[:pass_target]
            combined = picked_fail + picked_pass
            if len(combined) < per_group:
                pool = [seed_id for seed_id in failed[fail_target:] + passed[pass_target:] if seed_id not in combined]
                combined.extend(pool[: max(per_group - len(combined), 0)])

            for seed_id in combined[:per_group]:
                selected.append(
                    {
                        "seed_id": seed_id,
                        "split": split,
                        "view": "full",
                        "variant": "A",
                        "motif": motif,
                        "baseline_pass_from_report": bool(rows[seed_id]["pass"]),
                        "filter_kind": filter_kind_index.get((seed_id, split)) if filter_kind_index is not None else None,
                    }
                )
    return selected


def _build_filter_kind_index(recall_summary: Dict[str, Any] | None) -> Dict[Tuple[str, str], str]:
    if not recall_summary:
        return {}
    index: Dict[Tuple[str, str], str] = {}
    for row in recall_summary.get("rows", []):
        index[(str(row["seed_id"]), str(row["split"]))] = str(row.get("filter_kind", "none"))
    return index


def _summarize_probe_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_probe: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    baseline_lookup = {
        (row["seed_id"], row["split"]): row
        for row in rows
        if row["probe"] == "baseline"
    }
    for row in rows:
        by_probe[row["probe"]].append(row)

    summary: Dict[str, Any] = {}
    for probe, probe_rows in sorted(by_probe.items()):
        passed = sum(int(bool(row["pass"])) for row in probe_rows)
        empty_fail = sum(int(bool(row["empty_fail"])) for row in probe_rows)
        nonempty_fail = sum(int(bool(row["nonempty_fail"])) for row in probe_rows)
        delta = 0.0
        comparable = 0
        motif_summary: Dict[str, Dict[str, Any]] = {}
        by_motif: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in probe_rows:
            by_motif[row["motif"]].append(row)
            key = (row["seed_id"], row["split"])
            baseline_row = baseline_lookup.get(key)
            if baseline_row is not None and probe != "baseline":
                delta += int(bool(row["pass"])) - int(bool(baseline_row["pass"]))
                comparable += 1
        for motif, motif_rows in sorted(by_motif.items()):
            motif_passed = sum(int(bool(row["pass"])) for row in motif_rows)
            motif_empty_fail = sum(int(bool(row["empty_fail"])) for row in motif_rows)
            motif_nonempty_fail = sum(int(bool(row["nonempty_fail"])) for row in motif_rows)
            motif_delta = 0.0
            motif_comp = 0
            for row in motif_rows:
                baseline_row = baseline_lookup.get((row["seed_id"], row["split"]))
                if baseline_row is not None and probe != "baseline":
                    motif_delta += int(bool(row["pass"])) - int(bool(baseline_row["pass"]))
                    motif_comp += 1
            motif_summary[motif] = {
                "case_count": len(motif_rows),
                "pass_rate": motif_passed / len(motif_rows) if motif_rows else 0.0,
                "delta_vs_baseline": motif_delta / motif_comp if motif_comp else 0.0,
                "empty_fail_ratio": motif_empty_fail / len(motif_rows) if motif_rows else 0.0,
                "nonempty_fail_ratio": motif_nonempty_fail / len(motif_rows) if motif_rows else 0.0,
            }
        summary[probe] = {
            "case_count": len(probe_rows),
            "pass_rate": passed / len(probe_rows) if probe_rows else 0.0,
            "empty_fail_ratio": empty_fail / len(probe_rows) if probe_rows else 0.0,
            "nonempty_fail_ratio": nonempty_fail / len(probe_rows) if probe_rows else 0.0,
            "delta_vs_baseline": delta / comparable if comparable else 0.0,
            "by_motif": motif_summary,
        }
    return summary


def _normalize_critique_label(label: str) -> str:
    lower = label.lower()
    if "role" in lower:
        return "role_consistency_fail"
    if any(token in lower for token in ["obligation", "support_relation"]):
        return "obligation_fail"
    if "filter" in lower:
        return "support_retrieval_fail"
    if any(token in lower for token in ["compil", "syntax", "sql"]):
        return "compilation"
    return "execution_fail"


def _validate_critique(
    sampled_cases: List[Dict[str, Any]],
    bench_root: Path,
    *,
    max_cases: int = 30,
) -> Dict[str, Any]:
    failing_cases = [case for case in sampled_cases if not case.get("baseline_pass", False)][:max_cases]
    rows: List[Dict[str, Any]] = []
    for case in failing_cases:
        seed_dir = bench_root / case["seed_id"]
        pub = _load_json(seed_dir / "variants" / "A" / "manifest_public.json")
        pri = _load_json(seed_dir / "variants" / "A" / "manifest_private.json")
        workspace = Path(pub["splits"][case["split"]][case["view"]])
        output_csv = bench_root.parent / "analysis" / "probe_outputs" / "critique_validation" / case["split"] / case["seed_id"] / "baseline.csv"
        meta = run_support_plan_agent(
            instruction=pub.get("instruction", ""),
            workspace=workspace,
            deliverable_spec=pub.get("deliverable_spec", {}),
            output_csv=output_csv,
        )
        score = score_single(output_csv, pub["gold_path"], pub["deliverable_spec"])
        actual = classify_failure({"pass": bool(score.get("pass")), "meta": meta})
        critique = meta.get("critique", {}) or {}
        predicted = _normalize_critique_label(str(critique.get("likely_failure_layer", ""))) if critique.get("likely_failure_layer") else "missing"
        rows.append(
            {
                "seed_id": case["seed_id"],
                "split": case["split"],
                "actual": actual,
                "predicted": predicted,
                "hit": actual == predicted,
            }
        )
    hit_rate = sum(int(row["hit"]) for row in rows) / len(rows) if rows else 0.0
    return {"case_count": len(rows), "hit_rate": hit_rate, "rows": rows}


def _write_decision_memo(
    out_path: Path,
    recall_summary: Dict[str, Any] | None,
    probe_summary: Dict[str, Any],
    critique_summary: Dict[str, Any] | None,
) -> None:
    split_l1 = (recall_summary or {}).get("summary_by_split", {}).get("l1", {})
    split_l2 = (recall_summary or {}).get("summary_by_split", {}).get("l2", {})
    output_l1 = float(split_l1.get("output_column_recall_at_6", 0.0))
    output_l2 = float(split_l2.get("output_column_recall_at_6", 0.0))
    filter_l1 = float(split_l1.get("filter_column_recall_at_3", 0.0))
    filter_l2 = float(split_l2.get("filter_column_recall_at_3", 0.0))

    baseline = probe_summary.get("baseline", {})
    oracle_output = probe_summary.get("oracle_output", {})
    joint = probe_summary.get("joint_rerank", {})
    oracle_filter = probe_summary.get("oracle_filter", {})
    typed = probe_summary.get("typed_filter_strict", {})
    oracle_measure_anchor = probe_summary.get("oracle_measure_anchor", {})
    oracle_all = probe_summary.get("oracle_all", {})

    h1 = (output_l1 - output_l2) > 0.15 and float(oracle_output.get("delta_vs_baseline", 0.0)) > 0.08
    h2 = float(joint.get("delta_vs_baseline", 0.0)) > 0.08
    h3 = max(float(oracle_filter.get("delta_vs_baseline", 0.0)), float(typed.get("delta_vs_baseline", 0.0))) > 0.08
    h4 = float(oracle_measure_anchor.get("delta_vs_baseline", 0.0)) > 0.08
    critique_rate = float((critique_summary or {}).get("hit_rate", 0.0))
    h5 = critique_rate >= 0.75

    filter_family_delta = max(float(oracle_filter.get("delta_vs_baseline", 0.0)), float(typed.get("delta_vs_baseline", 0.0)))
    decision_scores = {
        "output_alignment": float(oracle_output.get("delta_vs_baseline", 0.0)),
        "joint_rerank": float(joint.get("delta_vs_baseline", 0.0)),
        "filter_typed": filter_family_delta,
        "measure_anchor": float(oracle_measure_anchor.get("delta_vs_baseline", 0.0)),
    }
    winning_axis = max(decision_scores, key=decision_scores.get)

    if winning_axis == "output_alignment":
        recommendation = "Prioritize output latent alignment and candidate generation first."
    elif winning_axis == "joint_rerank":
        recommendation = "Prioritize joint rerank / answerability scoring first."
    elif winning_axis == "measure_anchor":
        recommendation = "Prioritize aggregation semantics and anchor-measure consistency first."
    elif winning_axis == "filter_typed":
        recommendation = "Prioritize filter recall and typed semantics in planning first."
    else:
        recommendation = "Keep diagnosis open; rerun controls after L3 and larger probe coverage."

    agg_measure_delta = float(oracle_measure_anchor.get("by_motif", {}).get("AggregationJoin", {}).get("delta_vs_baseline", 0.0))
    agg_filter_delta = float(oracle_filter.get("by_motif", {}).get("AggregationJoin", {}).get("delta_vs_baseline", 0.0))
    agg_output_delta = float(oracle_output.get("by_motif", {}).get("AggregationJoin", {}).get("delta_vs_baseline", 0.0))
    if agg_measure_delta > max(agg_filter_delta, agg_output_delta):
        aggregation_read = "AggregationJoin bottleneck looks more like measure/anchor consistency."
    else:
        aggregation_read = "AggregationJoin bottleneck still looks more like output/filter side than measure/anchor."

    content = "\n".join(
        [
            "# Support Plan Decision Memo",
            "",
            "## Hypothesis Status",
            f"- H1 L2 output alignment collapse: {'supported' if h1 else 'not supported yet'}",
            f"- H2 local assembly / joint weakness: {'supported' if h2 else 'not supported yet'}",
            f"- H3 filter recall + typed semantics gap: {'supported' if h3 else 'not supported yet'}",
            f"- H4 aggregation measure/anchor consistency gap: {'supported' if h4 else 'not supported yet'}",
            f"- H5 critique is strong enough to justify repair next: {'supported' if h5 else 'not supported yet'}",
            "",
            "## Aggregation Read",
            f"- {aggregation_read}",
            "",
            "## Recommendation",
            f"- {recommendation}",
            "",
            "## Key Numbers",
            f"- L1 output recall@6: {output_l1:.3f}",
            f"- L2 output recall@6: {output_l2:.3f}",
            f"- L1 filter recall@3: {filter_l1:.3f}",
            f"- L2 filter recall@3: {filter_l2:.3f}",
            f"- Oracle-output delta vs baseline: {float(oracle_output.get('delta_vs_baseline', 0.0)):.3f}",
            f"- Joint-rerank delta vs baseline: {float(joint.get('delta_vs_baseline', 0.0)):.3f}",
            f"- Oracle-filter delta vs baseline: {float(oracle_filter.get('delta_vs_baseline', 0.0)):.3f}",
            f"- Oracle-all delta vs baseline: {float(oracle_all.get('delta_vs_baseline', 0.0)):.3f}",
            f"- Oracle-measure-anchor delta vs baseline: {float(oracle_measure_anchor.get('delta_vs_baseline', 0.0)):.3f}",
            f"- Typed-filter-strict delta vs baseline: {float(typed.get('delta_vs_baseline', 0.0)):.3f}",
            f"- Critique hit rate: {critique_rate:.3f}",
        ]
    )
    out_path.write_text(content, encoding="utf-8")


def run_controls(
    bench_root: Path,
    report_l1: Path,
    report_l2: Path,
    *,
    out_dir: Path,
    recall_summary_path: Path | None = None,
    sketch_mode: str = "live",
    validate_critique: bool = False,
    splits: List[str] | None = None,
    motifs: List[str] | None = None,
    filter_kinds: List[str] | None = None,
    per_group: int = 6,
    fail_target: int = 4,
    pass_target: int = 2,
    probe_names: List[str] | None = None,
) -> Dict[str, Any]:
    seed_motifs = build_seed_motif_index(bench_root)
    report_by_split = {
        "l1": _load_variant_a_rows(report_l1),
        "l2": _load_variant_a_rows(report_l2),
    }
    recall_summary = _load_json(recall_summary_path) if recall_summary_path and recall_summary_path.exists() else None
    filter_kind_index = _build_filter_kind_index(recall_summary)
    active_splits = splits or ["l1", "l2"]
    active_motifs = motifs or ["SimpleJoin", "FilterJoin", "AggregationJoin"]
    active_probes = probe_names or list(PROBE_SEQUENCE)
    samples = select_probe_samples(
        report_by_split,
        seed_motifs,
        splits=active_splits,
        motifs=active_motifs,
        filter_kind_index=filter_kind_index,
        filter_kinds=filter_kinds,
        per_group=per_group,
        fail_target=fail_target,
        pass_target=pass_target,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    probe_rows: List[Dict[str, Any]] = []
    enriched_samples: List[Dict[str, Any]] = []
    for case in samples:
        seed_dir = bench_root / case["seed_id"]
        pub = _load_json(seed_dir / "variants" / "A" / "manifest_public.json")
        pri = _load_json(seed_dir / "variants" / "A" / "manifest_private.json")
        context = prepare_case_context(pub, pri, split=case["split"], view=case["view"], sketch_mode=sketch_mode, namespace=f"support_plan_control_{case['split']}_{case['seed_id']}")
        enabled_probes = list(active_probes)
        case_result: Dict[str, Any] = dict(case)
        case_result["sketch_mode"] = context.sketch_mode
        for probe in enabled_probes:
            output_csv = out_dir / "probe_outputs" / probe / case["split"] / case["seed_id"] / "full.csv"
            result = run_probe(context, probe, output_csv=output_csv)
            result["motif"] = case["motif"]
            probe_rows.append(result)
            if probe == "baseline":
                case_result["baseline_pass"] = bool(result["pass"])
                case_result["baseline_score"] = float(result["score"])
        enriched_samples.append(case_result)

    probe_summary = _summarize_probe_rows(probe_rows)
    critique_summary = _validate_critique(enriched_samples, bench_root) if validate_critique else None
    memo_path = out_dir / "support_plan_decision_memo.md"
    _write_decision_memo(memo_path, recall_summary, probe_summary, critique_summary)

    payload = {
        "bench_root": str(bench_root),
        "sample_count": len(enriched_samples),
        "requested_splits": list(active_splits),
        "requested_motifs": list(active_motifs),
        "requested_filter_kinds": list(filter_kinds or []),
        "requested_probes": list(active_probes),
        "per_group": per_group,
        "fail_target": fail_target,
        "pass_target": pass_target,
        "samples": enriched_samples,
        "probe_summary": probe_summary,
        "probe_rows": probe_rows,
        "critique_summary": critique_summary,
        "decision_memo": str(memo_path),
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run stratified support-plan probe controls on sampled seeds.")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--report_l1", required=True)
    parser.add_argument("--report_l2", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--recall_summary", required=False)
    parser.add_argument("--sketch_mode", default="live", choices=["live", "fallback"])
    parser.add_argument("--validate_critique", action="store_true")
    parser.add_argument("--splits", default="l1,l2")
    parser.add_argument("--motifs", default="SimpleJoin,FilterJoin,AggregationJoin")
    parser.add_argument("--filter_kinds", default="")
    parser.add_argument("--probes", default="")
    parser.add_argument("--per_group", type=int, default=6)
    parser.add_argument("--fail_target", type=int, default=4)
    parser.add_argument("--pass_target", type=int, default=2)
    args = parser.parse_args()

    split_names = [item.strip() for item in args.splits.split(",") if item.strip()]
    motif_names = [item.strip() for item in args.motifs.split(",") if item.strip()]
    filter_kind_names = [item.strip() for item in args.filter_kinds.split(",") if item.strip()]
    probe_names = [item.strip() for item in args.probes.split(",") if item.strip()]

    payload = run_controls(
        bench_root=Path(args.bench_root),
        report_l1=Path(args.report_l1),
        report_l2=Path(args.report_l2),
        out_dir=Path(args.out_dir),
        recall_summary_path=Path(args.recall_summary) if args.recall_summary else None,
        sketch_mode=args.sketch_mode,
        validate_critique=args.validate_critique,
        splits=split_names,
        motifs=motif_names,
        filter_kinds=filter_kind_names,
        per_group=args.per_group,
        fail_target=args.fail_target,
        pass_target=args.pass_target,
        probe_names=probe_names,
    )

    out_dir = Path(args.out_dir)
    json_path = out_dir / "support_plan_probe_summary.json"
    csv_path = out_dir / "support_plan_probe_rows.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(payload["probe_rows"]).to_csv(csv_path, index=False)
    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "sample_count": payload["sample_count"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
