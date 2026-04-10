from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.compare_agent_reports import compare_reports


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class CompareAgentReportsTests(unittest.TestCase):
    def test_compare_reports_with_motif_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bench_root = tmp / "bench"
            self._create_seed(
                bench_root,
                "seed_simple",
                "SELECT a.name FROM artists AS a JOIN albums AS b ON a.id = b.artist_id ORDER BY a.name",
            )
            self._create_seed(
                bench_root,
                "seed_agg",
                "SELECT a.name, COUNT(*) FROM artists AS a JOIN albums AS b ON a.id = b.artist_id GROUP BY a.name",
            )

            baseline = self._build_report(
                {
                    "seed_simple": {"A": False, "B": False, "C": False},
                    "seed_agg": {"A": True, "B": True, "C": True},
                }
            )
            candidate = self._build_report(
                {
                    "seed_simple": {"A": True, "B": True, "C": False},
                    "seed_agg": {"A": True, "B": True, "C": True},
                }
            )

            summary = compare_reports(baseline, candidate, bench_root=bench_root)

            self.assertEqual(6, summary["shared_record_count"])
            self.assertEqual(
                {
                    "candidate_only_pass": 2,
                    "baseline_only_pass": 0,
                    "both_pass": 3,
                    "both_fail": 1,
                },
                summary["record_head_to_head"],
            )
            self.assertEqual(
                {
                    "candidate_only_asr": 0,
                    "baseline_only_asr": 0,
                    "both_asr": 1,
                    "neither_asr": 1,
                },
                summary["seed_asr_head_to_head"],
            )

            setting = summary["shared_setting_summary"]["l1.full"]
            self.assertEqual(6, setting["record_count"])
            self.assertEqual(2, setting["seed_count"])
            self.assertEqual(["A", "B", "C"], setting["variants_considered"])
            self.assertAlmostEqual(0.5, setting["baseline_pass_rate"])
            self.assertAlmostEqual(5 / 6, setting["candidate_pass_rate"])
            self.assertAlmostEqual(0.5, setting["baseline_asr"])
            self.assertAlmostEqual(0.5, setting["candidate_asr"])

            self.assertEqual(
                {"AggregationJoin": 1, "SimpleJoin": 1},
                summary["motif_taxonomy_summary"]["base_counts"],
            )
            self.assertEqual(
                {"has_order": 1},
                summary["motif_taxonomy_summary"]["modifier_counts"],
            )

            simple = summary["motif_breakdown"]["SimpleJoin"]
            self.assertEqual(1, simple["seed_count"])
            self.assertEqual(3, simple["record_count"])
            self.assertEqual(1, simple["has_order_seed_count"])
            self.assertEqual(0, simple["has_distinct_seed_count"])
            self.assertAlmostEqual(0.0, simple["baseline_pass_rate"])
            self.assertAlmostEqual(2 / 3, simple["candidate_pass_rate"])
            self.assertAlmostEqual(0.0, simple["baseline_asr"])
            self.assertAlmostEqual(0.0, simple["candidate_asr"])

            agg = summary["motif_breakdown"]["AggregationJoin"]
            self.assertEqual(1, agg["seed_count"])
            self.assertEqual(3, agg["record_count"])
            self.assertAlmostEqual(1.0, agg["baseline_pass_rate"])
            self.assertAlmostEqual(1.0, agg["candidate_pass_rate"])
            self.assertAlmostEqual(1.0, agg["baseline_asr"])
            self.assertAlmostEqual(1.0, agg["candidate_asr"])

    def _create_seed(self, bench_root: Path, seed_id: str, gold_sql: str) -> None:
        seed_dir = bench_root / seed_id
        _write_json(seed_dir / "seed_report.json", {"seed_id": seed_id})
        for variant in ("A", "B", "C"):
            _write_json(
                seed_dir / "variants" / variant / "manifest_private.json",
                {"gold_sql": gold_sql},
            )

    def _build_report(self, passes: dict[str, dict[str, bool]]) -> dict:
        records = []
        for seed_id in ("seed_simple", "seed_agg"):
            for variant in ("A", "B", "C"):
                records.append(
                    {
                        "seed_id": seed_id,
                        "variant": variant,
                        "split": "l1",
                        "view": "full",
                        "pass": passes[seed_id][variant],
                        "score": 1.0 if passes[seed_id][variant] else 0.0,
                        "stage": None if passes[seed_id][variant] else "QUERY_FAIL",
                        "attribution": "PASS" if passes[seed_id][variant] else "QUERY_FAIL",
                        "meta": {},
                    }
                )
        return {
            "mode": "synthetic",
            "canonical_mode": "synthetic",
            "agent_variant": "default",
            "records": records,
            "num_records": len(records),
        }


if __name__ == "__main__":
    unittest.main()
