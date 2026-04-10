from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.run_hdrbench_eval import run_eval


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class RunHdrbenchEvalTests(unittest.TestCase):
    def test_support_plan_no_obligation_report_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bench_root = tmp / "bench"
            workspace = tmp / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            gold_path = tmp / "gold.csv"
            pd.DataFrame({"Answer": ["ok"]}).to_csv(gold_path, index=False)

            seed_dir = bench_root / "seed_case"
            _write_json(seed_dir / "seed_report.json", {"seed_id": "seed_case"})
            _write_json(
                seed_dir / "variants" / "A" / "manifest_public.json",
                {
                    "instruction": "Return the answer column.",
                    "splits": {"l1": {"full": str(workspace)}},
                    "deliverable_spec": {
                        "format": "csv",
                        "required_columns": ["Answer"],
                        "optional_columns": [],
                        "order_required": False,
                        "float_tolerance": 1e-6,
                    },
                    "gold_path": str(gold_path),
                },
            )
            _write_json(
                seed_dir / "variants" / "A" / "manifest_private.json",
                {"gold_sql": "SELECT 'ok' AS Answer"},
            )

            def _fake_support_plan_agent(
                instruction: str,
                workspace: Path,
                deliverable_spec: dict,
                output_csv: Path,
                obligation_mode: str = "full",
            ) -> dict:
                self.assertEqual("off", obligation_mode)
                output_csv.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame({"Answer": ["ok"]}).to_csv(output_csv, index=False)
                return {
                    "success": True,
                    "files_touched": [],
                    "error": None,
                    "obligation_mode": obligation_mode,
                    "search_summary": {"search_log": [{"kind": "direct_candidate"}]},
                }

            with patch("evaluation.support_plan_agent.run_support_plan_agent", side_effect=_fake_support_plan_agent):
                report = run_eval(
                    bench_root=bench_root,
                    mode="support_plan_no_obligation",
                    out_dir=tmp / "out",
                    split_filter="l1",
                    view_filter="full",
                    access_mode="public",
                    variant_filter=["A"],
                    seed_filter=[],
                )

            self.assertEqual("support_plan_no_obligation", report["mode"])
            self.assertEqual("support_plan_agent", report["canonical_mode"])
            self.assertEqual("no_obligation", report["agent_variant"])
            self.assertEqual("off", report["records"][0]["meta"]["obligation_mode"])
            self.assertTrue((tmp / "out" / "report_support_plan_no_obligation.json").exists())


if __name__ == "__main__":
    unittest.main()
