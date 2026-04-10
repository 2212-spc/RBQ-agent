"""Check obligation sketch details for mini-regression seeds."""
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
        split="l0", view="full", sketch_mode="live", namespace=f"dbgob_{sid}",
    )
    obs = ctx.observable_sketch
    obl = ctx.obligation_sketch
    sr_prob = obl.probability("support_relation")
    has_agg = bool(obs.measure_hints) or any(
        item in {"count", "sum", "avg", "average", "max", "min"}
        for item in obs.operator_hints
    )
    has_agg_in_labels = any(
        any(slot.label.lower().startswith(fn) or f" {fn}" in slot.label.lower()
            for fn in ("avg(", "count(", "sum(", "max(", "min("))
        for slot in obs.output_slots
    )
    print(f"\n{sid}")
    print(f"  Q: {ctx.instruction}")
    print(f"  operator_hints={obs.operator_hints}  measure_hints={obs.measure_hints}")
    print(f"  has_explicit_agg={has_agg}  has_agg_in_labels={has_agg_in_labels}")
    print(f"  support_relation={sr_prob:.3f}  (cap_applied={sr_prob <= 0.44})")
    print(f"  output_slots={[(s.label, s.role) for s in obs.output_slots]}")
