"""Show all top plan candidates and their component scores for climbing."""
from __future__ import annotations
from pathlib import Path
from evaluation.run_hdrbench_eval import _load_json
from evaluation.support_plan_agent.probes import prepare_case_context
from evaluation.support_plan_agent.search import search_support_plans, _joint_rerank_adjustment

BENCH = Path("outputs/hdrbench_full150_v1")

for seed_id in [
    "spider__climbing__01130",
    "spider__match_season__01072",
]:
    sid = seed_id
    ctx = prepare_case_context(
        _load_json(BENCH / sid / "variants/A/manifest_public.json"),
        _load_json(BENCH / sid / "variants/A/manifest_private.json"),
        split="l0", view="full", sketch_mode="live", namespace=f"dbg3_{sid}",
    )
    summary = search_support_plans(ctx.instruction, ctx.observable_sketch, ctx.obligation_sketch, ctx.catalog)
    print(f"\n{'='*70}\n{sid}")
    for i, p in enumerate(summary["top_plan_candidates"][:8]):
        outs = [(b.source_id.split("::")[-1], b.column_name) for b in p.output_bindings]
        sb = p.support_binding.source_id.split("::")[-1] if p.support_binding else "NONE"
        # Recompute breakdown for display
        _, bd = _joint_rerank_adjustment(p, ctx.observable_sketch, ctx.obligation_sketch, ctx.catalog)
        print(f"  [{i}] conf={p.confidence:.2f}  out={outs}  support={sb}")
        print(f"       out_cons={bd['output_consistency']:.1f}  oblig={bd['obligation_consistency']:.1f}  shape={bd['shape_sanity']:.1f}  agg={bd['aggregation_consistency']:.1f}")
