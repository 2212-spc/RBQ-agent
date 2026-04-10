"""Check all obligation probabilities for target seeds."""
from pathlib import Path
from evaluation.run_hdrbench_eval import _load_json
from evaluation.support_plan_agent.probes import prepare_case_context

BENCH = Path("outputs/hdrbench_full150_v1")

for sid in [
    "spider__party_host__02678",
    "spider__riding_club__01728",
    "spider__pilot_record__02093",
    "spider__climbing__01130",
    "spider__match_season__01072",
    "spider__tracking_share_transactions__05871",
]:
    ctx = prepare_case_context(
        _load_json(BENCH / sid / "variants/A/manifest_public.json"),
        _load_json(BENCH / sid / "variants/A/manifest_private.json"),
        split="l0", view="full", sketch_mode="live", namespace=f"mini_{sid}",
    )
    obl = ctx.obligation_sketch
    probs = {o.name: round(o.probability, 2) for o in obl.obligations}
    # also check output join paths for top direct plan
    from evaluation.support_plan_agent.search import _output_plan_candidates
    from evaluation.workspace_catalog import tokenize
    qtok = tokenize(ctx.instruction)
    combos = _output_plan_candidates(ctx.observable_sketch, ctx.catalog, qtok, top_k=1)
    if combos:
        _, paths, _ = combos[0]
        total_hops = sum(len(p.edges) for p in paths)
    else:
        total_hops = 0
    print(f"\n{sid.split('__')[1]:30s}  Q: {ctx.instruction[:60]}")
    print(f"  obligations: {probs}")
    print(f"  top_combo output_join hops={total_hops}")
