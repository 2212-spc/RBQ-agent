"""Trace obligation sketch building to find where cap is bypassed."""
from pathlib import Path
from evaluation.run_hdrbench_eval import _load_json
from evaluation.support_plan_agent import obligations as obl_mod

orig = obl_mod.build_obligation_sketch


def patched(instruction, observable_sketch, session=None):
    result = orig(instruction, observable_sketch, session)
    sr = result.probability("support_relation")
    mh = result.probability("multihop")
    va = result.probability("value_alignment")
    raw_flag = result.raw_response.get("fallback", False)
    print(f"  build_obligation_sketch  fallback={raw_flag}  sr={sr:.3f}  multihop={mh:.3f}  va={va:.3f}")
    return result


obl_mod.build_obligation_sketch = patched

from evaluation.support_plan_agent.probes import prepare_case_context

BENCH = Path("outputs/hdrbench_full150_v1")
for sid in ["spider__climbing__01130", "spider__match_season__01072"]:
    print(f"\n--- {sid} ---")
    ctx = prepare_case_context(
        _load_json(BENCH / sid / "variants/A/manifest_public.json"),
        _load_json(BENCH / sid / "variants/A/manifest_private.json"),
        split="l0", view="full", sketch_mode="live", namespace=f"verify_{sid}",
    )
    sr = ctx.obligation_sketch.probability("support_relation")
    mh = ctx.obligation_sketch.probability("multihop")
    va = ctx.obligation_sketch.probability("value_alignment")
    print(f"  ctx.obligation_sketch     sr={sr:.3f}  multihop={mh:.3f}  va={va:.3f}")
    print(f"  Q: {ctx.instruction}")
