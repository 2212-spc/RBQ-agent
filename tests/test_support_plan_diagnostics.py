from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.analyze_support_plan_controls import _build_filter_kind_index, _summarize_probe_rows, run_controls, select_probe_samples
from evaluation.analyze_support_plan_recall import analyze_recall
from evaluation.analyze_support_plan_minireg import _head_to_head
from evaluation.support_plan_agent.diagnostics import classify_discovery_fail_subtype, summarize_discovery_failures
from evaluation.support_plan_agent.probes import extract_gold_targets, prepare_case_context, run_probe


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class SupportPlanDiagnosticsTests(unittest.TestCase):
    def test_classify_discovery_fail_subtype_path_gap(self) -> None:
        subtype = classify_discovery_fail_subtype(
            {
                "attribution": "DISCOVERY_FAIL",
                "meta": {
                    "calibrated_grounding_hints": {
                        "cross_source_join_risk": True,
                        "output_priors_by_slot": {
                            "Aircraft": {
                                "s1 | c1": {
                                    "is_primary": True,
                                    "is_uncertain": False,
                                    "is_dummy_likely": False,
                                    "confidence": 0.9,
                                }
                            }
                        },
                        "filter_priors_by_attribute": {},
                        "order_priors_by_target": {},
                        "fallback_injected": {"output_slots": [], "filter_attributes": [], "order_targets": []},
                        "calibration_rules_fired": ["rule_cross_source_without_join_evidence"],
                    },
                    "support_plan": {"plan_score": {"hard_invalid_reasons": [], "semantic_complete_reasons": []}},
                },
            }
        )
        self.assertEqual("A_path_gap", subtype)

    def test_classify_discovery_fail_subtype_world_not_found(self) -> None:
        subtype = classify_discovery_fail_subtype(
            {
                "attribution": "DISCOVERY_FAIL",
                "meta": {
                    "calibrated_grounding_hints": {
                        "cross_source_join_risk": False,
                        "output_priors_by_slot": {},
                        "filter_priors_by_attribute": {},
                        "order_priors_by_target": {},
                        "fallback_injected": {"output_slots": ["Title"], "filter_attributes": [], "order_targets": []},
                        "calibration_rules_fired": ["rule_profile_fallback_output"],
                    },
                    "support_plan": {"plan_score": {"hard_invalid_reasons": [], "semantic_complete_reasons": []}},
                },
            }
        )
        self.assertEqual("B_world_not_found", subtype)

    def test_classify_discovery_fail_subtype_calibration_overreach(self) -> None:
        subtype = classify_discovery_fail_subtype(
            {
                "attribution": "DISCOVERY_FAIL",
                "meta": {
                    "calibrated_grounding_hints": {
                        "cross_source_join_risk": True,
                        "output_priors_by_slot": {},
                        "filter_priors_by_attribute": {},
                        "order_priors_by_target": {},
                        "fallback_injected": {"output_slots": ["Aircraft"], "filter_attributes": [], "order_targets": []},
                        "calibration_rules_fired": ["rule_profile_fallback_output"],
                    },
                    "support_plan": {
                        "plan_score": {
                            "hard_invalid_reasons": ["selected_output_binding_unsupported_by_calibrated_prior"],
                            "semantic_complete_reasons": [],
                        }
                    },
                },
            }
        )
        self.assertEqual("C_calibration_overreach", subtype)

    def test_summarize_discovery_failures(self) -> None:
        summary = summarize_discovery_failures(
            {
                "records": [
                    {
                        "seed_id": "s1",
                        "variant": "A",
                        "split": "l2",
                        "attribution": "DISCOVERY_FAIL",
                        "meta": {
                            "calibrated_grounding_hints": {
                                "cross_source_join_risk": True,
                                "output_priors_by_slot": {"A": {"k": {"is_primary": True, "is_uncertain": False, "is_dummy_likely": False, "confidence": 0.9}}},
                                "filter_priors_by_attribute": {},
                                "order_priors_by_target": {},
                                "fallback_injected": {"output_slots": [], "filter_attributes": [], "order_targets": []},
                                "calibration_rules_fired": [],
                            },
                            "support_plan": {"plan_score": {"hard_invalid_reasons": [], "semantic_complete_reasons": []}},
                        },
                    }
                ]
            }
        )
        self.assertEqual(1, summary["counts"]["A_path_gap"])

    def test_extract_gold_targets_for_aggregation_join(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            manifest_private = {
                "gold_sql": "SELECT T1.part_name FROM Parts AS T1 JOIN Part_Faults AS T2 ON T1.part_id = T2.part_id GROUP BY T1.part_name ORDER BY COUNT(*) ASC LIMIT 1",
                "table_registry_by_split": {
                    "l2": {
                        "Parts": {"storage_type": "csv", "file": "parts_dirty.csv", "table_name": "Parts"},
                        "Part_Faults": {"storage_type": "csv", "file": "faults_dirty.csv", "table_name": "Part_Faults"},
                    }
                },
                "column_mapping_by_split": {
                    "l2": {
                        "Parts": {"part_id": "k0", "part_name": "field_part_name"},
                        "Part_Faults": {"part_id": "k1", "fault_count": "field_fault_count"},
                    }
                },
            }
            gold = extract_gold_targets(
                manifest_private=manifest_private,
                deliverable_spec={"required_columns": ["part_name"]},
                split="l2",
                workspace=workspace,
                instruction="Which part_name has the fewest faults?",
            )
            self.assertTrue(gold.has_aggregation)
            self.assertTrue(gold.has_order)
            self.assertTrue(gold.has_limit)
            self.assertTrue(gold.ambiguous_count_star)
            self.assertEqual("ordering/superlative", gold.primary_filter_kind)
            self.assertEqual("field_part_name", gold.output_bindings_by_label["part_name"][0].dirty_column)
            self.assertEqual(["Part_Faults"], gold.evidence_tables)

    def test_extract_gold_targets_for_date_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            manifest_private = {
                "gold_sql": "SELECT T1.event_name FROM Events AS T1 WHERE T1.event_date = '2020-01-01'",
                "table_registry_by_split": {
                    "l2": {
                        "Events": {"storage_type": "csv", "file": "events_dirty.csv", "table_name": "Events"},
                    }
                },
                "column_mapping_by_split": {
                    "l2": {
                        "Events": {"event_name": "field_event_name", "event_date": "field_event_date"},
                    }
                },
            }
            gold = extract_gold_targets(
                manifest_private=manifest_private,
                deliverable_spec={"required_columns": ["event_name"]},
                split="l2",
                workspace=workspace,
                instruction="List the event_name on 2020-01-01.",
            )
            self.assertEqual("time", gold.primary_filter_kind)
            self.assertEqual("field_event_date", gold.filter_bindings[0].dirty_column)

    def test_analyze_recall_on_toy_bench(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bench_root = self._build_toy_bench(Path(tmp_dir))
            payload = analyze_recall(bench_root=bench_root, variant="A", splits=["l1"], sketch_mode="fallback")
            self.assertEqual(1, payload["overall_summary"]["seed_count"])
            row = payload["rows"][0]
            self.assertAlmostEqual(1.0, row["output_column_recall_at_6"])
            self.assertAlmostEqual(1.0, row["filter_column_recall_at_3"])
            self.assertAlmostEqual(1.0, row["gold_join_path_reachable_at_2"])

    def test_run_probe_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bench_root = self._build_toy_bench(Path(tmp_dir))
            seed_dir = bench_root / "seed_simple"
            pub = json.loads((seed_dir / "variants" / "A" / "manifest_public.json").read_text(encoding="utf-8"))
            pri = json.loads((seed_dir / "variants" / "A" / "manifest_private.json").read_text(encoding="utf-8"))
            context = prepare_case_context(pub, pri, split="l1", view="full", sketch_mode="fallback")

            result_a = run_probe(context, "baseline", output_csv=Path(tmp_dir) / "baseline_a.csv")
            result_b = run_probe(context, "baseline", output_csv=Path(tmp_dir) / "baseline_b.csv")

            self.assertEqual(result_a["pass"], result_b["pass"])
            self.assertAlmostEqual(result_a["score"], result_b["score"])
            self.assertEqual(result_a["final_sql"], result_b["final_sql"])

    def test_oracle_measure_anchor_changes_measure_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bench_root = self._build_toy_aggregation_bench(Path(tmp_dir))
            seed_dir = bench_root / "seed_agg"
            pub = json.loads((seed_dir / "variants" / "A" / "manifest_public.json").read_text(encoding="utf-8"))
            pri = json.loads((seed_dir / "variants" / "A" / "manifest_private.json").read_text(encoding="utf-8"))
            context = prepare_case_context(pub, pri, split="l1", view="full", sketch_mode="fallback")

            evidence_only = run_probe(context, "oracle_evidence_path", output_csv=Path(tmp_dir) / "oracle_evidence_path.csv")
            measure_anchor = run_probe(context, "oracle_measure_anchor", output_csv=Path(tmp_dir) / "oracle_measure_anchor.csv")

            self.assertNotEqual(
                evidence_only["best_plan"]["measure_binding"]["column_name"],
                measure_anchor["best_plan"]["measure_binding"]["column_name"],
            )
            self.assertNotEqual("repair_cost", evidence_only["best_plan"]["measure_binding"]["column_name"])
            self.assertEqual("repair_cost", measure_anchor["best_plan"]["measure_binding"]["column_name"])
            self.assertFalse(evidence_only["pass"])
            self.assertTrue(measure_anchor["pass"])

    def test_probe_summary_includes_motif_failure_ratios(self) -> None:
        rows = [
            {"probe": "baseline", "seed_id": "s1", "split": "l1", "motif": "AggregationJoin", "pass": False, "empty_fail": True, "nonempty_fail": False},
            {"probe": "oracle_measure_anchor", "seed_id": "s1", "split": "l1", "motif": "AggregationJoin", "pass": True, "empty_fail": False, "nonempty_fail": False},
            {"probe": "oracle_measure_anchor", "seed_id": "s2", "split": "l1", "motif": "AggregationJoin", "pass": False, "empty_fail": False, "nonempty_fail": True},
        ]
        summary = _summarize_probe_rows(rows)
        motif = summary["oracle_measure_anchor"]["by_motif"]["AggregationJoin"]
        self.assertIn("empty_fail_ratio", motif)
        self.assertIn("nonempty_fail_ratio", motif)
        self.assertAlmostEqual(0.0, motif["empty_fail_ratio"])
        self.assertAlmostEqual(0.5, motif["nonempty_fail_ratio"])

    def test_select_probe_samples_counts(self) -> None:
        seed_motifs = {}
        report_by_split = {"l1": {}, "l2": {}}
        for split in ("l1", "l2"):
            for motif in ("SimpleJoin", "FilterJoin", "AggregationJoin"):
                for idx in range(8):
                    seed_id = f"{split}_{motif}_{idx}"
                    seed_motifs[seed_id] = {"base_label": motif}
                    report_by_split[split][seed_id] = {"seed_id": seed_id, "pass": idx >= 4}
        samples = select_probe_samples(report_by_split, seed_motifs)
        counts = Counter((sample["split"], sample["motif"]) for sample in samples)
        self.assertEqual(36, len(samples))
        for key in counts:
            self.assertEqual(6, counts[key])

    def test_select_probe_samples_fast_mode_counts(self) -> None:
        seed_motifs = {}
        report_by_split = {"l1": {}, "l2": {}}
        filter_kind_index = {}
        for split in ("l1", "l2"):
            for motif in ("SimpleJoin", "FilterJoin", "AggregationJoin"):
                for idx in range(4):
                    seed_id = f"{split}_{motif}_{idx}"
                    seed_motifs[seed_id] = {"base_label": motif}
                    report_by_split[split][seed_id] = {"seed_id": seed_id, "pass": idx >= 2}
                    filter_kind_index[(seed_id, split)] = "numeric"
        samples = select_probe_samples(
            report_by_split,
            seed_motifs,
            splits=["l1", "l2"],
            motifs=["SimpleJoin", "FilterJoin", "AggregationJoin"],
            filter_kind_index=filter_kind_index,
            per_group=2,
            fail_target=1,
            pass_target=1,
        )
        counts = Counter((sample["split"], sample["motif"]) for sample in samples)
        self.assertEqual(12, len(samples))
        for key in counts:
            self.assertEqual(2, counts[key])

    def test_select_probe_samples_filter_kind_restricts_pool(self) -> None:
        seed_motifs = {}
        report_by_split = {"l1": {}, "l2": {}}
        filter_kind_index = {}
        for split in ("l1", "l2"):
            for motif in ("SimpleJoin", "FilterJoin", "AggregationJoin"):
                for idx in range(4):
                    seed_id = f"{split}_{motif}_{idx}"
                    seed_motifs[seed_id] = {"base_label": motif}
                    report_by_split[split][seed_id] = {"seed_id": seed_id, "pass": idx >= 2}
                    filter_kind_index[(seed_id, split)] = "numeric" if idx < 2 else "text"
        samples = select_probe_samples(
            report_by_split,
            seed_motifs,
            filter_kind_index=filter_kind_index,
            filter_kinds=["numeric"],
            per_group=2,
            fail_target=1,
            pass_target=1,
        )
        self.assertTrue(all(sample["filter_kind"] == "numeric" for sample in samples))

    def test_build_filter_kind_index_from_recall_rows(self) -> None:
        index = _build_filter_kind_index(
            {
                "rows": [
                    {"seed_id": "s1", "split": "l1", "filter_kind": "numeric"},
                    {"seed_id": "s2", "split": "l2", "filter_kind": "time"},
                ]
            }
        )
        self.assertEqual("numeric", index[("s1", "l1")])
        self.assertEqual("time", index[("s2", "l2")])

    def test_run_controls_respects_probe_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bench_root = self._build_toy_bench(Path(tmp_dir))
            seed_dir = bench_root / "seed_simple"
            report_payload = {
                "records": [
                    {"seed_id": "seed_simple", "variant": "A", "pass": False},
                ]
            }
            report_l1 = Path(tmp_dir) / "report_l1.json"
            report_l2 = Path(tmp_dir) / "report_l2.json"
            _write_json(report_l1, report_payload)
            _write_json(report_l2, report_payload)

            fake_samples = [
                {
                    "seed_id": "seed_simple",
                    "split": "l1",
                    "view": "full",
                    "variant": "A",
                    "motif": "FilterJoin",
                    "baseline_pass_from_report": False,
                    "filter_kind": "numeric",
                }
            ]

            def _fake_run_probe(context, probe, *, output_csv=None):
                return {
                    "probe": probe,
                    "seed_id": "seed_simple",
                    "split": "l1",
                    "pass": probe == "oracle_output",
                    "score": 1.0 if probe == "oracle_output" else 0.0,
                    "empty_fail": probe == "baseline",
                    "nonempty_fail": False,
                    "motif": "FilterJoin",
                }

            with patch("evaluation.analyze_support_plan_controls.select_probe_samples", return_value=fake_samples), patch(
                "evaluation.analyze_support_plan_controls.run_probe",
                side_effect=_fake_run_probe,
            ):
                payload = run_controls(
                    bench_root=bench_root,
                    report_l1=report_l1,
                    report_l2=report_l2,
                    out_dir=Path(tmp_dir) / "controls_out",
                    sketch_mode="fallback",
                    splits=["l1"],
                    motifs=["FilterJoin"],
                    probe_names=["baseline", "oracle_output"],
                    per_group=2,
                    fail_target=1,
                    pass_target=1,
                )

            self.assertEqual(["baseline", "oracle_output"], payload["requested_probes"])
            self.assertEqual({"baseline", "oracle_output"}, {row["probe"] for row in payload["probe_rows"]})
            self.assertEqual(1, payload["sample_count"])

    def test_minireg_head_to_head_includes_transitions(self) -> None:
        motif_index = {"s1": {"base_label": "FilterJoin"}, "s2": {"base_label": "AggregationJoin"}}
        old_rows = [
            {"seed_id": "s1", "pass": False, "score": 0.5, "stage": "INSTANCE_FAIL", "result_rows": 10},
            {"seed_id": "s2", "pass": False, "score": 0.0, "stage": "QUERY_FAIL", "result_rows": 0},
        ]
        new_rows = [
            {"seed_id": "s1", "pass": False, "score": 0.0, "stage": "QUERY_FAIL", "result_rows": 0},
            {"seed_id": "s2", "pass": True, "score": 1.0, "stage": None, "result_rows": 1},
        ]
        summary = _head_to_head(old_rows, new_rows, motif_index)
        self.assertIn("transitions", summary)
        self.assertEqual(1, summary["transitions"]["nonempty_to_empty_fail"])
        self.assertEqual(1, summary["transitions"]["net_pass_delta"])

    def _build_toy_bench(self, root: Path) -> Path:
        bench_root = root / "bench"
        seed_dir = bench_root / "seed_simple"
        workspace = seed_dir / "variants" / "A" / "workspace_l1"
        workspace.mkdir(parents=True, exist_ok=True)
        parts = pd.DataFrame({"part_id": [1, 2, 3], "part_name": ["A", "B", "C"]})
        faults = pd.DataFrame({"part_id": [1, 2, 3], "fault_count": [1, 3, 5]})
        parts.to_csv(workspace / "Parts.csv", index=False)
        faults.to_csv(workspace / "Part_Faults.csv", index=False)

        gold = pd.DataFrame({"part_name": ["B", "C"]})
        gold_path = seed_dir / "variants" / "A" / "gold.csv"
        gold_path.parent.mkdir(parents=True, exist_ok=True)
        gold.to_csv(gold_path, index=False)

        _write_json(seed_dir / "seed_report.json", {"seed_id": "seed_simple"})
        _write_json(
            seed_dir / "variants" / "A" / "manifest_public.json",
            {
                "seed_id": "seed_simple",
                "instruction": "List the part_name with more than 2 fault_count.",
                "splits": {"l1": {"full": str(workspace)}},
                "deliverable_spec": {
                    "format": "csv",
                    "required_columns": ["part_name"],
                    "optional_columns": [],
                    "order_required": False,
                    "float_tolerance": 1e-6,
                },
                "gold_path": str(gold_path),
            },
        )
        _write_json(
            seed_dir / "variants" / "A" / "manifest_private.json",
            {
                "seed_id": "seed_simple",
                "gold_sql": "SELECT T1.part_name FROM Parts AS T1 JOIN Part_Faults AS T2 ON T1.part_id = T2.part_id WHERE T2.fault_count > 2",
                "table_registry_by_split": {
                    "l1": {
                        "Parts": {
                            "storage_type": "csv",
                            "file": "Parts.csv",
                            "table_name": "Parts",
                            "canonical_columns": ["part_id", "part_name"],
                            "dirty_columns": ["part_id", "part_name"],
                        },
                        "Part_Faults": {
                            "storage_type": "csv",
                            "file": "Part_Faults.csv",
                            "table_name": "Part_Faults",
                            "canonical_columns": ["part_id", "fault_count"],
                            "dirty_columns": ["part_id", "fault_count"],
                        },
                    }
                },
                "column_mapping_by_split": {
                    "l1": {
                        "Parts": {"part_id": "part_id", "part_name": "part_name"},
                        "Part_Faults": {"part_id": "part_id", "fault_count": "fault_count"},
                    }
                },
            },
        )
        return bench_root

    def _build_toy_aggregation_bench(self, root: Path) -> Path:
        bench_root = root / "bench_agg"
        seed_dir = bench_root / "seed_agg"
        workspace = seed_dir / "variants" / "A" / "workspace_l1"
        workspace.mkdir(parents=True, exist_ok=True)
        parts = pd.DataFrame({"part_id": [10, 1], "part_name": ["A", "B"]})
        faults = pd.DataFrame(
            {
                "part_id": [10, 1],
                "severity_score": [100, 1],
                "repair_cost": [1, 100],
            }
        )
        parts.to_csv(workspace / "Parts.csv", index=False)
        faults.to_csv(workspace / "Part_Faults.csv", index=False)

        gold = pd.DataFrame({"part_name": ["B"]})
        gold_path = seed_dir / "variants" / "A" / "gold.csv"
        gold_path.parent.mkdir(parents=True, exist_ok=True)
        gold.to_csv(gold_path, index=False)

        _write_json(seed_dir / "seed_report.json", {"seed_id": "seed_agg"})
        _write_json(
            seed_dir / "variants" / "A" / "manifest_public.json",
            {
                "seed_id": "seed_agg",
                "instruction": "Which part_name has the highest total repair cost?",
                "splits": {"l1": {"full": str(workspace)}},
                "deliverable_spec": {
                    "format": "csv",
                    "required_columns": ["part_name"],
                    "optional_columns": [],
                    "order_required": False,
                    "float_tolerance": 1e-6,
                },
                "gold_path": str(gold_path),
            },
        )
        _write_json(
            seed_dir / "variants" / "A" / "manifest_private.json",
            {
                "seed_id": "seed_agg",
                "gold_sql": "SELECT T1.part_name FROM Parts AS T1 JOIN Part_Faults AS T2 ON T1.part_id = T2.part_id GROUP BY T1.part_name ORDER BY SUM(T2.repair_cost) DESC LIMIT 1",
                "table_registry_by_split": {
                    "l1": {
                        "Parts": {
                            "storage_type": "csv",
                            "file": "Parts.csv",
                            "table_name": "Parts",
                            "canonical_columns": ["part_id", "part_name"],
                            "dirty_columns": ["part_id", "part_name"],
                        },
                        "Part_Faults": {
                            "storage_type": "csv",
                            "file": "Part_Faults.csv",
                            "table_name": "Part_Faults",
                            "canonical_columns": ["part_id", "severity_score", "repair_cost"],
                            "dirty_columns": ["part_id", "severity_score", "repair_cost"],
                        },
                    }
                },
                "column_mapping_by_split": {
                    "l1": {
                        "Parts": {"part_id": "part_id", "part_name": "part_name"},
                        "Part_Faults": {"part_id": "part_id", "severity_score": "severity_score", "repair_cost": "repair_cost"},
                    }
                },
            },
        )
        return bench_root


if __name__ == "__main__":
    unittest.main()
