"""Deep debug: combo scores + joint rerank breakdown for rerank seeds."""
from __future__ import annotations

from itertools import product
from pathlib import Path
from dataclasses import asdict

from evaluation.run_hdrbench_eval import _load_json
from evaluation.support_plan_agent.probes import prepare_case_context
from evaluation.support_plan_agent.search import (
    _best_output_bindings,
    _output_plan_candidates,
    _joint_rerank_adjustment,
    _question_overlap,
    search_support_plans,
)
from evaluation.support_plan_agent.obligations import build_obligation_sketch
from evaluation.support_plan_agent.ir import build_support_plan_ir
from evaluation.support_plan_agent.verifier import obligations_from_trace, verify_support_plan
from evaluation.support_plan_agent.utils import infer_operator_hints, normalize_operator_direction
from evaluation.support_plan_agent.types import SupportPlan
from evaluation.workspace_catalog import tokenize

BENCH = Path("outputs/hdrbench_full150_v1")


def debug_combos(seed_id: str, max_combos: int = 8) -> None:
    seed_dir = BENCH / seed_id
    pub = _load_json(seed_dir / "variants" / "A" / "manifest_public.json")
    pri = _load_json(seed_dir / "variants" / "A" / "manifest_private.json")
    ctx = prepare_case_context(pub, pri, split="l0", view="full", sketch_mode="live",
                               namespace=f"dbg2_{seed_id}")
    qtok = tokenize(ctx.instruction)
    print(f"\n{'='*70}")
    print(f"SEED: {seed_id}")
    print(f"Q: {ctx.instruction}")
    print(f"REQUIRED_COLS: {ctx.deliverable_spec.get('required_columns', [])}")
    print(f"OUTPUT_SLOTS: {[(s.label, s.role) for s in ctx.observable_sketch.output_slots]}")

    # catalog edges relevant to output sources
    binding_opts = _best_output_bindings(ctx.observable_sketch, ctx.catalog, qtok, top_k=4)
    for slot in ctx.observable_sketch.output_slots:
        print(f"  slot[{slot.label}]: " + " | ".join(
            f"{b.source_id.split('::')[-1]}.{b.column_name}={b.score:.2f}"
            for b in binding_opts.get(slot.label, [])[:4]
        ))

    # show catalog edges for key sources
    key_sids = set()
    for bs in binding_opts.values():
        for b in bs[:2]:
            key_sids.add(b.source_id)
    print("  relevant catalog edges:")
    for edge in ctx.catalog.join_edges:
        if edge.left_source_id in key_sids or edge.right_source_id in key_sids:
            print(f"    {edge.left_source_id.split('::')[-1]}.{edge.left_column} <-> "
                  f"{edge.right_source_id.split('::')[-1]}.{edge.right_column} overlap={edge.overlap:.3f}")

    # show top output combos with their scores
    output_candidates = _output_plan_candidates(ctx.observable_sketch, ctx.catalog, qtok, top_k=12)
    print(f"\n  TOP OUTPUT COMBOS (out of {len(output_candidates)}):")
    for i, (bindings, paths, combo_score) in enumerate(output_candidates[:max_combos]):
        bound_str = " + ".join(f"{b.source_id.split('::')[-1]}.{b.column_name}" for b in bindings)
        path_str = f"paths={[p.score for p in paths]}" if paths else "single-src"
        print(f"    [{i}] combo_score={combo_score:.2f}  {bound_str}  {path_str}")

    # show joint rerank for top-2 combos
    operator_plan = infer_operator_hints(ctx.instruction)
    if ctx.observable_sketch.order_hint:
        if ctx.observable_sketch.order_hint.get("direction") and not operator_plan.get("direction"):
            od = normalize_operator_direction(ctx.observable_sketch.order_hint["direction"])
            if od:
                operator_plan["direction"] = od

    print("\n  JOINT RERANK DETAIL (top-2 combos as direct plans):")
    for i, (bindings, paths, combo_score) in enumerate(output_candidates[:2]):
        plan = SupportPlan(
            output_bindings=bindings,
            output_join_paths=paths,
            support_binding=None, anchor_binding=None,
            evidence_bindings=[], measure_binding=None, filter_bindings=[],
            operator_plan=operator_plan,
            confidence=combo_score,
            source_trace=sorted({b.source_id for b in bindings}),
            notes=["direct_plan"],
        )
        trace = verify_support_plan(plan, ctx.observable_sketch, ctx.obligation_sketch, ctx.catalog)
        satisfied, unmet = obligations_from_trace(trace, ctx.obligation_sketch)
        plan.satisfied_obligations = satisfied
        plan.unmet_obligations = unmet
        plan.confidence += sum(item["score"] for item in trace if item["passed"]) * 2.0
        joint_bonus, breakdown = _joint_rerank_adjustment(plan, ctx.observable_sketch, ctx.obligation_sketch, ctx.catalog)
        final_conf = plan.confidence + joint_bonus
        bound_str = " + ".join(f"{b.source_id.split('::')[-1]}.{b.column_name}" for b in bindings)
        print(f"    [{i}] conf={final_conf:.2f}  joint={joint_bonus:.2f}  {bound_str}")
        print(f"         breakdown: {breakdown}")

    # show what best_plan actually is
    summary = search_support_plans(ctx.instruction, ctx.observable_sketch,
                                   ctx.obligation_sketch, ctx.catalog)
    best = summary["best_plan"]
    print(f"\n  BEST_PLAN: {[(b.source_id.split('::')[-1], b.column_name) for b in best.output_bindings]}")
    print(f"  best.confidence={best.confidence:.2f}  notes={best.notes[:4]}")


if __name__ == "__main__":
    for sid in [
        "spider__climbing__01130",
        "spider__match_season__01072",
        "spider__tracking_share_transactions__05871",
    ]:
        debug_combos(sid)
