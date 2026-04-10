from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.support_plan_agent.obligations import disable_obligation_reasoning
from evaluation.support_plan_agent.types import AtomicObligation, ObligationSketch, RolePrior


class SupportPlanAblationTests(unittest.TestCase):
    def test_disable_obligation_reasoning_lowers_all_probabilities(self) -> None:
        sketch = ObligationSketch(
            obligations=[
                AtomicObligation("support_relation", 0.9, "needs support"),
                AtomicObligation("aggregation_support", 0.8, "needs measure"),
            ],
            role_priors=[RolePrior("support_role", "fact", 0.8, "fact-like")],
            family_labels=[{"label": "AggregationJoin", "probability": 0.9, "reason": "test"}],
            raw_response={"source": "unit-test"},
        )

        disabled = disable_obligation_reasoning(sketch)

        self.assertTrue(all(item.probability < 0.45 for item in disabled.obligations))
        self.assertEqual([], disabled.family_labels)
        self.assertEqual("off", disabled.raw_response["obligation_mode"])
        self.assertEqual(7, len(disabled.obligations))


if __name__ == "__main__":
    unittest.main()
