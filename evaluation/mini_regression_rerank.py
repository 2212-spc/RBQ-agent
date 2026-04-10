"""Mini regression for rerank-category seeds: climbing, match_season, tracking."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from evaluation.run_hdrbench_eval import _load_json
from evaluation.scorer import score_single
from evaluation.support_plan_agent.compiler import compile_support_plan
from evaluation.support_plan_agent.ir import build_support_plan_ir
from evaluation.support_plan_agent.probes import prepare_case_context
from evaluation.support_plan_agent.search import search_support_plans

BENCH = Path("outputs/hdrbench_full150_v1")

TARGET_SEEDS = [
    "spider__climbing__01130",
    "spider__match_season__01072",
    "spider__tracking_share_transactions__05871",
]


def run_one(seed_id: str) -> dict:
    seed_dir = BENCH / seed_id
    pub = _load_json(seed_dir / "variants" / "A" / "manifest_public.json")
    pri = _load_json(seed_dir / "variants" / "A" / "manifest_private.json")
    ctx = prepare_case_context(pub, pri, split="l0", view="full", sketch_mode="live",
                               namespace=f"rerank_{seed_id}")
    summary = search_support_plans(ctx.instruction, ctx.observable_sketch,
                                   ctx.obligation_sketch, ctx.catalog)
    best = summary["best_plan"]
    plan_ir = build_support_plan_ir(best, ctx.observable_sketch, ctx.obligation_sketch, ctx.catalog)
    best_out = [(b.source_id.split("::")[-1], b.column_name) for b in best.output_bindings]
    with tempfile.TemporaryDirectory() as tmp:
        out_csv = Path(tmp) / "out.csv"
        meta = compile_support_plan(best, plan_ir, ctx.catalog, ctx.deliverable_spec, out_csv)
        score = score_single(out_csv, ctx.gold_path, ctx.deliverable_spec)
    sql = meta.get("final_sql") or ""
    return {
        "seed_id": seed_id,
        "pass": bool(score.get("pass")),
        "score": round(float(score.get("score", 0)), 4),
        "stage": score.get("stage"),
        "compile_reason": meta.get("reason") or "",
        "best_output": best_out,
        "sql_snippet": sql[:300],
    }


if __name__ == "__main__":
    results = []
    for sid in TARGET_SEEDS:
        r = run_one(sid)
        results.append(r)
        print(f"  {sid}: pass={r['pass']} score={r['score']:.3f}  best_out={r['best_output']}")
        if not r["pass"]:
            print(f"    reason={r['compile_reason'][:80]}")
            print(f"    sql={r['sql_snippet'][:200]}")
    print()
    print(json.dumps(results, indent=2, ensure_ascii=False))
