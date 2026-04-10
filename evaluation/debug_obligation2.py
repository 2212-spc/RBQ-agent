"""Verify obligation cap is correct for all target seeds."""
from pathlib import Path
from evaluation.run_hdrbench_eval import _load_json
from evaluation.support_plan_agent.probes import prepare_case_context

BENCH = Path("outputs/hdrbench_full150_v1")

tests = [
    ("spider__party_host__02678", True),
    ("spider__riding_club__01728", True),
    ("spider__pilot_record__02093", True),
    ("spider__climbing__01130", False),
    ("spider__match_season__01072", False),
    ("spider__tracking_share_transactions__05871", False),
]

for sid, expect_support in tests:
    ctx = prepare_case_context(
        _load_json(BENCH / sid / "variants/A/manifest_public.json"),
        _load_json(BENCH / sid / "variants/A/manifest_private.json"),
        split="l0", view="full", sketch_mode="live", namespace=f"mini_{sid}",
    )
    sr = ctx.obligation_sketch.probability("support_relation")
    support_required = sr >= 0.45
    status = "OK" if (support_required == expect_support) else "FAIL"
    label = sid.split("__")[1]
    print(f"[{status}] {label:30s}  sr={sr:.2f}  support_required={support_required}  (expected={expect_support})")
    print(f"       Q: {ctx.instruction[:80]}")
