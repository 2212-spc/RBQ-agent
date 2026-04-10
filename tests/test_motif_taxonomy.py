from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.motif_taxonomy import build_seed_motif_index, classify_sql_motif, summarize_seed_motifs


class MotifTaxonomyTests(unittest.TestCase):
    def test_classify_sql_motif_examples(self) -> None:
        cases = [
            (
                "SELECT a.name FROM artists AS a JOIN albums AS b ON a.id = b.artist_id",
                {"base_label": "SimpleJoin", "has_order": False, "has_distinct": False},
            ),
            (
                "SELECT a.name FROM artists AS a JOIN albums AS b ON a.id = b.artist_id WHERE b.year > 2010",
                {"base_label": "FilterJoin", "has_order": False, "has_distinct": False},
            ),
            (
                "SELECT a.name, COUNT(*) FROM artists AS a JOIN albums AS b ON a.id = b.artist_id GROUP BY a.name",
                {"base_label": "AggregationJoin", "has_order": False, "has_distinct": False},
            ),
            (
                "SELECT a.name FROM artists AS a JOIN albums AS b ON a.id = b.artist_id ORDER BY a.name LIMIT 5",
                {"base_label": "SimpleJoin", "has_order": True, "has_distinct": False},
            ),
            (
                "SELECT DISTINCT a.name FROM artists AS a JOIN albums AS b ON a.id = b.artist_id WHERE b.year > 2010",
                {"base_label": "FilterJoin", "has_order": False, "has_distinct": True},
            ),
            (
                "SELECT DISTINCT a.name, COUNT(*) FROM artists AS a JOIN albums AS b ON a.id = b.artist_id GROUP BY a.name ORDER BY COUNT(*) DESC",
                {"base_label": "AggregationJoin", "has_order": True, "has_distinct": True},
            ),
        ]

        for sql, expected in cases:
            with self.subTest(sql=sql):
                motif = classify_sql_motif(sql)
                self.assertEqual(expected["base_label"], motif["base_label"])
                self.assertEqual(expected["has_order"], motif["has_order"])
                self.assertEqual(expected["has_distinct"], motif["has_distinct"])

    def test_full_benchmark_taxonomy_counts(self) -> None:
        bench_root = ROOT / "outputs" / "hdrbench_full150_v1"
        self.assertTrue(bench_root.exists(), f"Missing benchmark root: {bench_root}")

        summary = summarize_seed_motifs(build_seed_motif_index(bench_root))
        self.assertEqual(
            {"AggregationJoin": 29, "FilterJoin": 29, "SimpleJoin": 109},
            summary["base_counts"],
        )
        self.assertEqual(
            {"has_distinct": 21, "has_order": 54},
            summary["modifier_counts"],
        )


if __name__ == "__main__":
    unittest.main()
