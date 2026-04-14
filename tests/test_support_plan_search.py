from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.support_plan_agent.observable import _fallback_observable
from evaluation.support_plan_agent.compiler import compile_support_plan
from evaluation.support_plan_agent.ir import build_support_plan_ir
from evaluation.support_plan_agent.grounding import (
    build_validated_overlay_edges,
    calibrate_grounding_hints,
    extract_suggested_join_specs,
    grounding_to_search_hints,
    is_overlay_edge,
)
from evaluation.support_plan_agent.search import (
    _hard_invalid_reasons,
    _joint_rerank_adjustment,
    _ordered_path_source_ids,
    _plan_sort_key,
    _score_order_binding,
    _score_output_binding,
    _score_filter_binding,
    _semantic_complete_reasons,
    search_support_plans,
)
from evaluation.support_plan_agent.types import AnchorPath, AtomicObligation, Binding, ObligationSketch, ObservableSketch, ObservableSlot, PlanScore, SupportPlan
from evaluation.support_plan_agent.utils import extract_order_target, infer_operator_hints
from evaluation.workspace_catalog import build_workspace_catalog


class SupportPlanSearchTests(unittest.TestCase):
    def test_grounding_to_search_hints_tracks_uncertainty_and_multisource(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"city": ["A", "B"], "address_id": [1, 2]}).to_csv(workspace / "addresses.csv", index=False)
            pd.DataFrame({"aircraft": ["Jet", "Plane"], "aircraft_id": [1, 2]}).to_csv(workspace / "aircraft.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            addresses = next(source for source in catalog.sources.values() if source.file_name == "addresses.csv")
            aircraft = next(source for source in catalog.sources.values() if source.file_name == "aircraft.csv")

            hints = grounding_to_search_hints(
                {
                    "output_hypotheses": [
                        {
                            "slot_label": "Location",
                            "binding": {"source_id": addresses.source_id, "column_name": "city", "confidence": 0.95},
                            "confidence": 0.95,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "top_alternatives": [],
                        },
                        {
                            "slot_label": "Aircraft",
                            "binding": {"source_id": aircraft.source_id, "column_name": "aircraft", "confidence": 0.9},
                            "confidence": 0.9,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "top_alternatives": [
                                {"source_id": addresses.source_id, "column_name": "city", "confidence": 0.2}
                            ],
                        },
                    ],
                    "query_family": "direct_join",
                    "query_family_confidence": 0.8,
                }
            )

            self.assertTrue(hints["strong_multi_source_output"])
            self.assertAlmostEqual(0.8, hints["query_family_confidence"])
            self.assertIn((aircraft.source_id, "aircraft"), hints["output_priors_by_slot"]["Aircraft"])
            self.assertIn((addresses.source_id, "city"), hints["output_priors_by_slot"]["Aircraft"])

    def test_calibrate_grounding_hints_downgrades_numeric_order_target_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Title": ["A", "B"], "Issues": ["Jan", "Feb"], "publication_price": [10, 20]}).to_csv(workspace / "books.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            hints = {
                "output_priors_by_slot": {
                    "Title": {
                        (source.source_id, "Title"): {
                            "source_id": source.source_id,
                            "column_name": "Title",
                            "raw_confidence": 0.95,
                            "confidence": 0.95,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "why_not": "Looks like titles",
                            "confidence_reason": "",
                            "no_reliable_binding": False,
                            "cross_source_join_risk": False,
                            "calibration_rules": [],
                        }
                    }
                },
                "filter_priors_by_attribute": {
                    "publication price": {
                        (source.source_id, "Issues"): {
                            "source_id": source.source_id,
                            "column_name": "Issues",
                            "raw_confidence": 0.9,
                            "confidence": 0.9,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "why_not": "",
                            "confidence_reason": "",
                            "no_reliable_binding": False,
                            "cross_source_join_risk": False,
                            "calibration_rules": [],
                        },
                        (source.source_id, "publication_price"): {
                            "source_id": source.source_id,
                            "column_name": "publication_price",
                            "raw_confidence": 0.7,
                            "confidence": 0.7,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "rank": 1,
                            "is_primary": True,
                            "why_not": "",
                            "confidence_reason": "",
                            "no_reliable_binding": False,
                            "cross_source_join_risk": False,
                            "calibration_rules": [],
                        },
                    }
                },
                "order_priors_by_target": {},
                "query_family": "aggregation_join",
                "query_family_confidence": 0.8,
                "strong_multi_source_output": False,
                "cross_source_join_risk": False,
                "calibration_rules_fired": [],
            }
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Title", role="entity")],
                order_hint={"direction": "desc", "target": "publication price"},
            )

            calibrated = calibrate_grounding_hints(hints, catalog, observable, "Show titles by publication price descending", [])
            order_prior = calibrated["order_priors_by_target"]["publication price"][(source.source_id, "Issues")]

            self.assertTrue(order_prior["is_uncertain"])
            self.assertTrue(order_prior["is_dummy_likely"])
            self.assertLessEqual(order_prior["confidence"], 0.35)
            self.assertIn("rule_order_target_type_mismatch", calibrated["calibration_rules_fired"])

    def test_cross_source_join_risk_does_not_zero_family_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"city": ["A", "B"]}).to_csv(workspace / "addresses.csv", index=False)
            pd.DataFrame({"aircraft": ["Jet", "Plane"]}).to_csv(workspace / "aircraft.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            addresses = next(source for source in catalog.sources.values() if source.file_name == "addresses.csv")
            aircraft = next(source for source in catalog.sources.values() if source.file_name == "aircraft.csv")
            hints = {
                "output_priors_by_slot": {
                    "Location": {
                        (addresses.source_id, "city"): {
                            "source_id": addresses.source_id,
                            "column_name": "city",
                            "raw_confidence": 0.95,
                            "confidence": 0.95,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "why_not": "Looks right",
                            "confidence_reason": "",
                            "no_reliable_binding": False,
                            "cross_source_join_risk": False,
                            "calibration_rules": [],
                        }
                    },
                    "Aircraft": {
                        (aircraft.source_id, "aircraft"): {
                            "source_id": aircraft.source_id,
                            "column_name": "aircraft",
                            "raw_confidence": 0.9,
                            "confidence": 0.9,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "why_not": "Looks right",
                            "confidence_reason": "",
                            "no_reliable_binding": False,
                            "cross_source_join_risk": False,
                            "calibration_rules": [],
                        }
                    },
                },
                "filter_priors_by_attribute": {},
                "order_priors_by_target": {},
                "query_family": "direct_join",
                "query_family_confidence": 0.9,
                "strong_multi_source_output": True,
                "cross_source_join_risk": False,
                "calibration_rules_fired": [],
            }
            observable = ObservableSketch(
                output_slots=[
                    ObservableSlot(label="Location", role="location"),
                    ObservableSlot(label="Aircraft", role="entity"),
                ]
            )

            calibrated = calibrate_grounding_hints(hints, catalog, observable, "List location and aircraft", [])

            self.assertTrue(calibrated["cross_source_join_risk"])
            self.assertAlmostEqual(0.9, calibrated["query_family_confidence"])

    def test_duplicate_slot_collapse_requires_exact_same_binding_not_same_column_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Location": ["A", "B"]}).to_csv(workspace / "matches.csv", index=False)
            pd.DataFrame({"Location": ["X", "Y"]}).to_csv(workspace / "other.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            matches = next(source for source in catalog.sources.values() if source.file_name == "matches.csv")
            other = next(source for source in catalog.sources.values() if source.file_name == "other.csv")
            hints = {
                "output_priors_by_slot": {
                    "Location": {
                        (matches.source_id, "Location"): {
                            "source_id": matches.source_id,
                            "column_name": "Location",
                            "raw_confidence": 0.95,
                            "confidence": 0.95,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "why_not": "",
                            "confidence_reason": "",
                            "no_reliable_binding": False,
                            "cross_source_join_risk": False,
                            "calibration_rules": [],
                        }
                    },
                    "AltLocation": {
                        (other.source_id, "Location"): {
                            "source_id": other.source_id,
                            "column_name": "Location",
                            "raw_confidence": 0.9,
                            "confidence": 0.9,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "why_not": "",
                            "confidence_reason": "",
                            "no_reliable_binding": False,
                            "cross_source_join_risk": False,
                            "calibration_rules": [],
                        }
                    },
                },
                "filter_priors_by_attribute": {},
                "order_priors_by_target": {},
                "query_family": "direct_join",
                "query_family_confidence": 0.8,
                "strong_multi_source_output": True,
                "cross_source_join_risk": False,
                "calibration_rules_fired": [],
            }
            observable = ObservableSketch(
                output_slots=[
                    ObservableSlot(label="Location", role="location"),
                    ObservableSlot(label="AltLocation", role="location"),
                ]
            )

            calibrated = calibrate_grounding_hints(hints, catalog, observable, "List both locations", [])

            self.assertNotIn("rule_duplicate_slot_collapse", calibrated["calibration_rules_fired"])

    def test_selected_low_confidence_order_binding_becomes_hard_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Title": ["A", "B"], "Issues": ["Jan", "Feb"]}).to_csv(workspace / "books.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Title", role="entity")],
                order_hint={"direction": "desc", "target": "publication price"},
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="Title",
                        role="entity",
                        score=10.0,
                        metadata={"slot_label": "Title"},
                    )
                ],
                plan_kind="direct_join",
                order_binding=Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name="Issues",
                    role="order",
                    score=8.0,
                    reasons=["order_numeric_mismatch"],
                    metadata={"target": "publication price", "direction": "desc"},
                ),
                operator_plan={"direction": "desc", "target": "publication price"},
            )
            grounding_hints = {
                "order_priors_by_target": {
                    "publication price": {
                        (source.source_id, "Issues"): {
                            "source_id": source.source_id,
                            "column_name": "Issues",
                            "confidence": 0.3,
                            "raw_confidence": 0.9,
                            "is_uncertain": True,
                            "is_dummy_likely": True,
                            "rank": 0,
                            "is_primary": True,
                            "cross_source_join_risk": False,
                            "calibration_rules": ["rule_order_target_type_mismatch"],
                        }
                    }
                },
                "output_priors_by_slot": {},
                "filter_priors_by_attribute": {},
                "strong_multi_source_output": False,
            }

            reasons = _hard_invalid_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            self.assertIn("selected_low_confidence_order_binding", reasons)

    def test_selected_order_binding_unsupported_by_calibrated_prior_is_hard_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Title": ["A", "B"], "Issues": [1, 2], "value": [10, 20]}).to_csv(workspace / "books.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Title", role="entity")],
                order_hint={"direction": "desc", "target": "publication price"},
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="Title",
                        role="entity",
                        score=10.0,
                        metadata={"slot_label": "Title"},
                    )
                ],
                plan_kind="direct_join",
                order_binding=Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name="Issues",
                    role="order",
                    score=8.0,
                    reasons=["order_numeric_compatible"],
                    metadata={"target": "publication price", "direction": "desc"},
                ),
                operator_plan={"direction": "desc", "target": "publication price"},
            )
            grounding_hints = {
                "order_priors_by_target": {
                    "publication price": {
                        (source.source_id, "value"): {
                            "source_id": source.source_id,
                            "column_name": "value",
                            "confidence": 0.4,
                            "raw_confidence": 0.9,
                            "is_uncertain": True,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "cross_source_join_risk": True,
                            "calibration_rules": ["rule_cross_source_without_join_evidence"],
                        }
                    }
                },
                "output_priors_by_slot": {},
                "filter_priors_by_attribute": {},
                "strong_multi_source_output": False,
            }

            hard_reasons = _hard_invalid_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            semantic_reasons = _semantic_complete_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            self.assertIn("selected_order_binding_unsupported_by_calibrated_prior", hard_reasons)
            self.assertIn("order_binding_not_supported_by_calibrated_prior", semantic_reasons)

    def test_no_calibration_mode_skips_calibrated_order_guardrails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Title": ["A", "B"], "Issues": [1, 2], "value": [10, 20]}).to_csv(workspace / "books.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Title", role="entity")],
                order_hint={"direction": "desc", "target": "publication price"},
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="Title",
                        role="entity",
                        score=10.0,
                        metadata={"slot_label": "Title"},
                    )
                ],
                plan_kind="direct_join",
                order_binding=Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name="Issues",
                    role="order",
                    score=8.0,
                    reasons=["order_numeric_mismatch"],
                    metadata={"target": "publication price", "direction": "desc"},
                ),
                operator_plan={"direction": "desc", "target": "publication price"},
            )
            grounding_hints = {
                "order_priors_by_target": {
                    "publication price": {
                        (source.source_id, "value"): {
                            "source_id": source.source_id,
                            "column_name": "value",
                            "confidence": 0.4,
                            "raw_confidence": 0.9,
                            "is_uncertain": True,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "cross_source_join_risk": True,
                            "calibration_rules": ["rule_cross_source_without_join_evidence"],
                        }
                    }
                },
                "output_priors_by_slot": {},
                "filter_priors_by_attribute": {},
                "strong_multi_source_output": False,
                "calibration_mode": "no_calibration",
            }

            hard_reasons = _hard_invalid_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            semantic_reasons = _semantic_complete_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            self.assertNotIn("selected_order_binding_unsupported_by_calibrated_prior", hard_reasons)
            self.assertNotIn("selected_order_binding_without_join_evidence", hard_reasons)
            self.assertNotIn("low_confidence_order_binding", semantic_reasons)

    def test_missing_order_binding_with_strong_calibrated_prior_is_hard_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Title": ["A", "B"], "value": [10, 20]}).to_csv(workspace / "books.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Title", role="entity")],
                order_hint={"direction": "desc", "target": "publication price"},
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="Title",
                        role="entity",
                        score=10.0,
                        metadata={"slot_label": "Title"},
                    )
                ],
                plan_kind="direct_join",
                operator_plan={"direction": "desc", "target": "publication price"},
            )
            grounding_hints = {
                "order_priors_by_target": {
                    "publication price": {
                        (source.source_id, "value"): {
                            "source_id": source.source_id,
                            "column_name": "value",
                            "confidence": 0.9,
                            "raw_confidence": 0.9,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "cross_source_join_risk": False,
                            "calibration_rules": [],
                        }
                    }
                },
                "output_priors_by_slot": {},
                "filter_priors_by_attribute": {},
                "strong_multi_source_output": False,
            }

            reasons = _hard_invalid_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            self.assertIn("missing_order_binding_despite_calibrated_prior", reasons)

    def test_empty_filter_prior_does_not_hard_invalid_filter_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"facility_code": ["gym", "pool"], "apt_id": [1, 2]}).to_csv(workspace / "facilities.csv", index=False)
            pd.DataFrame({"bedroom_count": [5, 2], "apt_id": [1, 2]}).to_csv(workspace / "apartments.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            facilities = next(source for source in catalog.sources.values() if source.file_name == "facilities.csv")
            apartments = next(source for source in catalog.sources.values() if source.file_name == "apartments.csv")
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="facility_code", role="attribute")],
                filter_hints=[{"attribute": "bedroom_count", "operator": ">", "value": 4}],
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=facilities.source_id,
                        file_name=facilities.file_name,
                        view_name=facilities.raw_view_name,
                        column_name="facility_code",
                        role="attribute",
                        score=10.0,
                        metadata={"slot_label": "facility_code"},
                    )
                ],
                plan_kind="filter_join",
                filter_bindings=[
                    Binding(
                        source_id=apartments.source_id,
                        file_name=apartments.file_name,
                        view_name=apartments.raw_view_name,
                        column_name="bedroom_count",
                        role="filter",
                        score=8.0,
                        metadata={"attribute": "bedroom_count", "operator": ">", "value": 4},
                    )
                ],
                filter_join_paths=[
                    AnchorPath(
                        path_source_ids=[facilities.source_id, apartments.source_id],
                        edges=[{"left_source_id": facilities.source_id, "right_source_id": apartments.source_id, "left_column": "apt_id", "right_column": "apt_id", "left_transform": "identity", "right_transform": "identity", "overlap": 1.0}],
                        score=1.0,
                    )
                ],
            )

            reasons = _hard_invalid_reasons(
                plan,
                observable,
                obligations,
                catalog,
                grounding_hints={"filter_priors_by_attribute": {}, "output_priors_by_slot": {}, "order_priors_by_target": {}, "strong_multi_source_output": False},
            )
            self.assertNotIn("selected_low_confidence_filter_binding", reasons)

    def test_output_binding_unsupported_by_priors_and_low_overlap_is_hard_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Location": ["A"], "name": ["Jet"]}).to_csv(workspace / "facts.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Aircraft", role="entity")]
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="name",
                        role="entity",
                        score=8.0,
                        metadata={"slot_label": "Aircraft"},
                    )
                ],
                plan_kind="direct_join",
            )
            grounding_hints = {
                "output_priors_by_slot": {
                    "Aircraft": {
                        (source.source_id, "Location"): {
                            "source_id": source.source_id,
                            "column_name": "Location",
                            "confidence": 0.4,
                            "raw_confidence": 0.9,
                            "is_uncertain": True,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "cross_source_join_risk": True,
                            "calibration_rules": ["rule_cross_source_without_join_evidence"],
                        }
                    }
                },
                "filter_priors_by_attribute": {},
                "order_priors_by_target": {},
                "strong_multi_source_output": False,
            }

            hard_reasons = _hard_invalid_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            semantic_reasons = _semantic_complete_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            self.assertIn("selected_output_binding_unsupported_by_calibrated_prior", hard_reasons)
            self.assertIn("output_binding_not_supported_by_calibrated_prior", semantic_reasons)

    def test_no_calibration_mode_skips_calibrated_output_guardrails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Location": ["A"], "name": ["Jet"]}).to_csv(workspace / "facts.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Aircraft", role="entity")]
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="name",
                        role="entity",
                        score=10.0,
                        metadata={"slot_label": "Aircraft"},
                    )
                ],
                plan_kind="direct_join",
            )
            grounding_hints = {
                "output_priors_by_slot": {
                    "Aircraft": {
                        (source.source_id, "Location"): {
                            "source_id": source.source_id,
                            "column_name": "Location",
                            "confidence": 0.4,
                            "raw_confidence": 0.9,
                            "is_uncertain": True,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "cross_source_join_risk": True,
                            "calibration_rules": ["rule_cross_source_without_join_evidence"],
                        }
                    }
                },
                "filter_priors_by_attribute": {},
                "order_priors_by_target": {},
                "strong_multi_source_output": False,
                "calibration_mode": "no_calibration",
            }

            hard_reasons = _hard_invalid_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            semantic_reasons = _semantic_complete_reasons(plan, observable, obligations, catalog, grounding_hints=grounding_hints)
            self.assertNotIn("selected_output_binding_unsupported_by_calibrated_prior", hard_reasons)
            self.assertNotIn("selected_output_binding_without_join_evidence", hard_reasons)
            self.assertNotIn("output_binding_not_supported_by_calibrated_prior", semantic_reasons)
            self.assertNotIn("low_confidence_output_binding", semantic_reasons)

    def test_safe_fallback_restores_all_dummy_order_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"value": [10, 20]}).to_csv(workspace / "prices.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(output_slots=[ObservableSlot(label="Title", role="entity")], order_hint={"direction": "desc", "target": "publication price"})
            hints = {
                "output_priors_by_slot": {},
                "filter_priors_by_attribute": {
                    "publication price": {
                        (source.source_id, "value"): {
                            "source_id": source.source_id,
                            "column_name": "value",
                            "raw_confidence": 0.8,
                            "confidence": 0.8,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "rank": 0,
                            "is_primary": True,
                            "why_not": "",
                            "confidence_reason": "",
                            "no_reliable_binding": False,
                            "cross_source_join_risk": False,
                            "calibration_rules": [],
                        }
                    }
                },
                "order_priors_by_target": {
                    "publication price": {
                        (source.source_id, "value"): {
                            "source_id": source.source_id,
                            "column_name": "value",
                            "raw_confidence": 0.8,
                            "confidence": 0.0,
                            "is_uncertain": True,
                            "is_dummy_likely": True,
                            "rank": 0,
                            "is_primary": True,
                            "why_not": "",
                            "confidence_reason": "",
                            "no_reliable_binding": False,
                            "cross_source_join_risk": False,
                            "calibration_rules": ["dummy"],
                        }
                    }
                },
                "query_family": "direct_join",
                "query_family_confidence": 0.7,
                "strong_multi_source_output": False,
                "cross_source_join_risk": False,
                "calibration_rules_fired": [],
            }

            calibrated = calibrate_grounding_hints(hints, catalog, observable, "Show titles by publication price", [])
            restored = calibrated["order_priors_by_target"]["publication price"][(source.source_id, "value")]
            self.assertFalse(restored["is_dummy_likely"])

    def test_extract_suggested_join_specs_normalizes_left_right_keys(self) -> None:
        specs = extract_suggested_join_specs(
            {
                "suggested_joins": [
                    {
                        "left_source": "s1",
                        "left_column": "a_id",
                        "right_source": "s2",
                        "right_column": "b_id",
                        "confidence": 0.9,
                        "reason": "join",
                    }
                ]
            }
        )
        self.assertEqual(
            [
                {
                    "from_source": "s1",
                    "from_column": "a_id",
                    "to_source": "s2",
                    "to_column": "b_id",
                    "confidence": 0.9,
                    "reason": "join",
                }
            ],
            specs,
        )

    def test_build_validated_overlay_edges_rejects_invalid_and_penalizes_type_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"book_id": [1, 2], "Title": ["A", "B"]}).to_csv(workspace / "books.csv", index=False)
            pd.DataFrame({"metric_code": ["m1", "m2"], "total_cost": [10, 10]}).to_csv(workspace / "metrics.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            books = next(source for source in catalog.sources.values() if source.file_name == "books.csv")
            metrics = next(source for source in catalog.sources.values() if source.file_name == "metrics.csv")

            edges = build_validated_overlay_edges(
                {
                    "suggested_joins": [
                        {
                            "from_source": books.source_id,
                            "from_column": "Title",
                            "to_source": metrics.source_id,
                            "to_column": "total_cost",
                            "confidence": 0.8,
                        },
                        {
                            "from_source": books.source_id,
                            "from_column": "missing_col",
                            "to_source": metrics.source_id,
                            "to_column": "metric_id",
                            "confidence": 0.9,
                        },
                    ]
                },
                catalog,
            )

            self.assertEqual(1, len(edges))
            self.assertTrue(is_overlay_edge(edges[0].edge_id))
            self.assertLess(edges[0].overlap, 0.25 + 0.5 * 0.8)

    def test_overlay_edges_enable_two_hop_path_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"match_id": [1, 2], "winning_aircraft": [1, 2], "location": ["A", "B"]}).to_csv(workspace / "matches.csv", index=False)
            pd.DataFrame({"aircraft_id": [1, 2], "aircraft": ["Jet", "Plane"]}).to_csv(workspace / "bridge.csv", index=False)
            pd.DataFrame({"aircraft": ["Jet", "Plane"], "kind": ["X", "Y"]}).to_csv(workspace / "aircrafts.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            matches = next(source for source in catalog.sources.values() if source.file_name == "matches.csv")
            bridge = next(source for source in catalog.sources.values() if source.file_name == "bridge.csv")
            aircrafts = next(source for source in catalog.sources.values() if source.file_name == "aircrafts.csv")
            self.assertEqual([], catalog.find_best_path(matches.source_id, aircrafts.source_id, max_hops=2))

            overlay_edges = build_validated_overlay_edges(
                {
                    "suggested_joins": [
                        {
                            "from_source": matches.source_id,
                            "from_column": "winning_aircraft",
                            "to_source": bridge.source_id,
                            "to_column": "aircraft_id",
                            "confidence": 0.9,
                        },
                        {
                            "from_source": bridge.source_id,
                            "from_column": "aircraft",
                            "to_source": aircrafts.source_id,
                            "to_column": "aircraft",
                            "confidence": 0.9,
                        },
                    ]
                },
                catalog,
            )
            catalog.join_edges.extend(overlay_edges)
            path = catalog.find_best_path(matches.source_id, aircrafts.source_id, max_hops=2)
            self.assertEqual(2, len(path))
            self.assertTrue(any(is_overlay_edge(edge.edge_id) for edge in path))

    def test_uncertain_dummy_llm_output_prior_does_not_outscore_clear_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Issues": [1, 2], "publication_price": [10, 20]}).to_csv(workspace / "books.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            slot = ObservableSlot(label="publication price", role="attribute")

            issues_score, _ = _score_output_binding(
                slot,
                source,
                "Issues",
                ["publication", "price"],
                llm_output_set={(source.source_id, "Issues")},
                slot_grounding_priors={
                    (source.source_id, "Issues"): {
                        "confidence": 0.3,
                        "is_uncertain": True,
                        "is_dummy_likely": True,
                        "rank": 0,
                    }
                },
            )
            price_score, _ = _score_output_binding(
                slot,
                source,
                "publication_price",
                ["publication", "price"],
            )

            self.assertLess(issues_score, price_score)

    def test_infer_operator_hints_extracts_descending_order_target(self) -> None:
        operator = infer_operator_hints("Show the titles of books in descending order of publication price.")
        self.assertEqual("desc", operator["direction"])
        self.assertEqual("publication price", operator["target"])
        self.assertIsNone(operator["limit"])

    def test_infer_operator_hints_detects_exists_and_intersection(self) -> None:
        operator = infer_operator_hints("List browser names compatible with both CACHEbox and Fasterfox and whether any account exists.")
        self.assertTrue(operator["exists"])
        self.assertTrue(operator["intersection"])

    def test_extract_order_target_shortest_earliest_latest_longest(self) -> None:
        # shortest / earliest / latest / longest / fastest - these are the new patterns
        self.assertEqual("trip", extract_order_target("Which rider has the shortest trip?"))
        self.assertEqual("date of birth", extract_order_target("Show the earliest date of birth"))
        self.assertEqual("transaction", extract_order_target("Find the latest transaction"))
        self.assertEqual("name", extract_order_target("Which product has the longest name"))
        self.assertEqual("runner", extract_order_target("Select the fastest runner"))
        self.assertEqual("duration", extract_order_target("Which route has the longest duration"))
        # original patterns still work
        self.assertEqual("salary", extract_order_target("Show highest salary"))

    def test_infer_operator_hints_shortest_direction_and_limit(self) -> None:
        operator = infer_operator_hints("Which rider has the shortest trip?")
        self.assertEqual("asc", operator["direction"])
        self.assertEqual(1, operator["limit"])
        self.assertEqual("trip", operator["target"])

    def test_infer_operator_hints_latest_direction_and_limit(self) -> None:
        operator = infer_operator_hints("Find the latest transaction")
        self.assertEqual("desc", operator["direction"])
        self.assertEqual(1, operator["limit"])
        self.assertEqual("transaction", operator["target"])

    def test_fallback_observable_includes_order_target(self) -> None:
        observable = _fallback_observable(
            "Show the titles of books in descending order of publication price.",
            {"required_columns": ["Title"]},
        )
        self.assertEqual("desc", observable.order_hint["direction"])
        self.assertEqual("publication price", observable.order_hint["target"])
        self.assertNotIn("limit", observable.order_hint)

    def test_numeric_filter_prefers_numeric_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame(
                {
                    "amount": [10, 20, 30],
                    "description": ["10", "20", "30"],
                    "event_date": ["2020-01-01", "2020-01-02", "2020-01-03"],
                }
            ).to_csv(workspace / "facts.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            filter_hint = {"attribute": "amount", "operator": ">", "value": 15}
            question_tokens = ["amount", "greater", "than"]

            amount_score, _ = _score_filter_binding(filter_hint, source, "amount", question_tokens)
            desc_score, _ = _score_filter_binding(filter_hint, source, "description", question_tokens)
            date_score, _ = _score_filter_binding(filter_hint, source, "event_date", question_tokens)

            self.assertGreater(amount_score, desc_score)
            self.assertGreater(amount_score, date_score)

    def test_joint_rerank_prefers_dimension_fact_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"part_id": [1, 2, 3], "part_name": ["A", "B", "C"]}).to_csv(workspace / "parts.csv", index=False)
            pd.DataFrame({"part_id": [1, 1, 2, 3], "repair_cost": [10, 5, 100, 1]}).to_csv(workspace / "faults.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            parts_source = next(source for source in catalog.sources.values() if source.file_name == "parts.csv")
            faults_source = next(source for source in catalog.sources.values() if source.file_name == "faults.csv")

            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="part_name", role="entity")],
                measure_hints=["sum"],
                operator_hints=["sum", "top_desc"],
                order_hint={"direction": "desc", "limit": 1},
            )
            obligations = ObligationSketch(
                obligations=[
                    AtomicObligation("support_relation", 0.9, "needs support"),
                    AtomicObligation("aggregation_support", 0.9, "needs measure"),
                    AtomicObligation("value_alignment", 0.8, "needs anchor"),
                ]
            )

            good_plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=parts_source.source_id,
                        file_name=parts_source.file_name,
                        view_name=parts_source.raw_view_name,
                        column_name="part_name",
                        role="entity",
                        score=12.0,
                    )
                ],
                support_binding=Binding(
                    source_id=faults_source.source_id,
                    file_name=faults_source.file_name,
                    view_name=faults_source.raw_view_name,
                    column_name="part_id",
                    role="support",
                    score=9.0,
                ),
                anchor_binding=AnchorPath(
                    path_source_ids=[parts_source.source_id, faults_source.source_id],
                    edges=[
                        {
                            "left_source_id": parts_source.source_id,
                            "right_source_id": faults_source.source_id,
                            "left_column": "part_id",
                            "right_column": "part_id",
                            "left_transform": "identity",
                            "right_transform": "identity",
                        }
                    ],
                    score=0.8,
                ),
                measure_binding=Binding(
                    source_id=faults_source.source_id,
                    file_name=faults_source.file_name,
                    view_name=faults_source.raw_view_name,
                    column_name="repair_cost",
                    role="measure",
                    score=11.0,
                ),
                operator_plan={"aggregation": "sum", "direction": "desc", "limit": 1},
                satisfied_obligations=["support_relation", "aggregation_support", "value_alignment"],
            )

            bad_plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=faults_source.source_id,
                        file_name=faults_source.file_name,
                        view_name=faults_source.raw_view_name,
                        column_name="part_id",
                        role="entity",
                        score=9.0,
                    )
                ],
                support_binding=Binding(
                    source_id=faults_source.source_id,
                    file_name=faults_source.file_name,
                    view_name=faults_source.raw_view_name,
                    column_name="part_id",
                    role="support",
                    score=6.0,
                ),
                anchor_binding=AnchorPath(path_source_ids=[faults_source.source_id], edges=[], score=0.05),
                measure_binding=Binding(
                    source_id=faults_source.source_id,
                    file_name=faults_source.file_name,
                    view_name=faults_source.raw_view_name,
                    column_name="part_id",
                    role="measure",
                    score=5.0,
                ),
                operator_plan={"aggregation": "sum", "direction": "desc", "limit": 1},
                unmet_obligations=["value_alignment"],
            )

            good_score, _ = _joint_rerank_adjustment(good_plan, observable, obligations, catalog)
            bad_score, _ = _joint_rerank_adjustment(bad_plan, observable, obligations, catalog)

            self.assertGreater(good_score, bad_score)

    def test_filter_join_family_generates_explicit_filter_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"apt_id": [1, 2], "facility_code": ["gym", "pool"]}).to_csv(workspace / "facilities.csv", index=False)
            pd.DataFrame({"apt_id": [1, 2], "bedroom_count": [5, 2]}).to_csv(workspace / "apartments.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="facility_code", role="attribute")],
                filter_hints=[{"attribute": "bedroom_count", "operator": ">", "value": 4}],
            )
            obligations = ObligationSketch(obligations=[])

            summary = search_support_plans(
                instruction="Show the facility code of apartments with more than 4 bedrooms.",
                observable_sketch=observable,
                obligation_sketch=obligations,
                catalog=catalog,
            )

            top_candidates = summary["top_plan_candidates"]
            self.assertTrue(summary["family_best_candidates"])
            self.assertTrue(any(plan.plan_kind == "filter_join" for plan in top_candidates))
            filter_plan = next(plan for plan in top_candidates if plan.plan_kind == "filter_join")
            self.assertTrue(filter_plan.filter_bindings)
            self.assertTrue(filter_plan.filter_join_paths)

    def test_exists_query_generates_support_family_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"customer_id": [1, 2], "customer_name": ["A", "B"]}).to_csv(workspace / "customers.csv", index=False)
            pd.DataFrame({"account_id": [10], "customer_id": [1]}).to_csv(workspace / "accounts.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="customer_name", role="entity")],
                operator_hints=["exists"],
            )
            obligations = ObligationSketch(obligations=[AtomicObligation("existence_check", 0.9, "requires related rows")])

            summary = search_support_plans(
                instruction="List customer_name with any account.",
                observable_sketch=observable,
                obligation_sketch=obligations,
                catalog=catalog,
            )

            self.assertTrue(any(plan.plan_kind == "support_join" for plan in summary["top_plan_candidates"]))

    def test_exists_without_support_is_hard_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"customer_name": ["A", "B"]}).to_csv(workspace / "customers.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="customer_name", role="entity")],
                operator_hints=["exists"],
            )
            obligations = ObligationSketch(obligations=[AtomicObligation("existence_check", 0.9, "requires related rows")])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="customer_name",
                        role="entity",
                        score=10.0,
                        metadata={"slot_label": "customer_name"},
                    )
                ],
                plan_kind="direct_join",
                operator_plan={"exists": True},
            )

            reasons = _hard_invalid_reasons(plan, observable, obligations, catalog)
            self.assertIn("missing_existence_support", reasons)

    def test_llm_family_high_confidence_enables_support_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"part_id": [1, 2], "part_name": ["A", "B"]}).to_csv(workspace / "parts.csv", index=False)
            pd.DataFrame({"part_id": [1, 1, 2], "repair_cost": [10, 20, 1]}).to_csv(workspace / "faults.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            parts_source = next(source for source in catalog.sources.values() if source.file_name == "parts.csv")
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="part_name", role="entity")],
                measure_hints=["sum"],
                operator_hints=["sum", "top_desc"],
                order_hint={"direction": "desc", "target": "repair cost"},
            )
            obligations = ObligationSketch(obligations=[])

            summary = search_support_plans(
                instruction="Which part name has the highest total repair cost?",
                observable_sketch=observable,
                obligation_sketch=obligations,
                catalog=catalog,
                llm_grounding={
                    "output_hypotheses": [
                        {
                            "slot_label": "part_name",
                            "binding": {
                                "source_id": parts_source.source_id,
                                "column_name": "part_name",
                                "confidence": 0.95,
                            },
                            "confidence": 0.95,
                            "is_uncertain": False,
                            "is_dummy_likely": False,
                            "top_alternatives": [],
                        }
                    ],
                    "output_bindings": [
                        {
                            "slot_label": "part_name",
                            "source_id": parts_source.source_id,
                            "column_name": "part_name",
                            "confidence": 0.95,
                        }
                    ],
                    "query_family": "aggregation_join",
                    "query_family_confidence": 0.9,
                },
            )

            self.assertTrue(any(plan.plan_kind == "aggregation_join" for plan in summary["top_plan_candidates"]))

    def test_aggregation_family_present_in_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"part_id": [1, 2], "part_name": ["A", "B"]}).to_csv(workspace / "parts.csv", index=False)
            pd.DataFrame({"part_id": [1, 1, 2], "repair_cost": [10, 20, 1]}).to_csv(workspace / "faults.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="part_name", role="entity")],
                measure_hints=["sum"],
                operator_hints=["sum"],
            )
            obligations = ObligationSketch(
                obligations=[
                    AtomicObligation("support_relation", 0.9, "needs support"),
                    AtomicObligation("aggregation_support", 0.9, "needs aggregation"),
                ]
            )

            summary = search_support_plans(
                instruction="Which part name has the highest total repair cost?",
                observable_sketch=observable,
                obligation_sketch=obligations,
                catalog=catalog,
            )

            self.assertTrue(any(plan.plan_kind == "aggregation_join" for plan in summary["top_plan_candidates"]))

    def test_count_star_support_family_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"part_id": [1, 2], "part_name": ["A", "B"]}).to_csv(workspace / "parts.csv", index=False)
            pd.DataFrame({"part_id": [1, 1, 2], "fault_id": [10, 11, 20]}).to_csv(workspace / "faults.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="part_name", role="entity")],
                operator_hints=["count", "top_asc"],
                order_hint={"direction": "asc", "limit": 1},
            )
            obligations = ObligationSketch(
                obligations=[
                    AtomicObligation("support_relation", 0.9, "needs support"),
                    AtomicObligation("aggregation_support", 0.9, "needs aggregation"),
                ]
            )

            summary = search_support_plans(
                instruction="Which part name has the least number of faults?",
                observable_sketch=observable,
                obligation_sketch=obligations,
                catalog=catalog,
            )

            self.assertTrue(any(plan.plan_kind == "count_star_support" for plan in summary["top_plan_candidates"]))

    def test_hard_invalid_flags_same_source_count_star(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"part_id": [1, 1, 2], "part_name": ["A", "A", "B"]}).to_csv(workspace / "parts.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="part_name", role="entity")],
                operator_hints=["count"],
            )
            obligations = ObligationSketch(
                obligations=[
                    AtomicObligation("support_relation", 0.9, "needs support"),
                    AtomicObligation("aggregation_support", 0.9, "needs aggregation"),
                ]
            )
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="part_name",
                        role="entity",
                        score=10.0,
                    )
                ],
                plan_kind="count_star_support",
                support_binding=Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name="part_id",
                    role="support",
                    score=8.0,
                ),
                operator_plan={"aggregation": "count"},
                evidence_source_ids=[source.source_id],
                aggregation_mode="count_star_support",
                aggregation_unit_kind="evidence_rows",
                aggregation_anchor_source_id=source.source_id,
                ranking_target_kind="aggregation_value",
            )

            reasons = _hard_invalid_reasons(plan, observable, obligations, catalog)
            self.assertIn("count_star_missing_anchor", reasons)
            self.assertIn("count_star_same_source_support", reasons)

    def test_semantic_completeness_flags_weak_filter_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"facility_code": ["gym", "pool"], "facility_name": ["Gym", "Pool"]}).to_csv(workspace / "facilities.csv", index=False)
            pd.DataFrame({"bedroom_count": [5, 2], "facility_code": ["gym", "pool"]}).to_csv(workspace / "apartments.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            facilities = next(source for source in catalog.sources.values() if source.file_name == "facilities.csv")
            apartments = next(source for source in catalog.sources.values() if source.file_name == "apartments.csv")
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="facility_name", role="attribute")],
                filter_hints=[{"attribute": "bedroom_count", "operator": ">", "value": 4}],
            )
            obligations = ObligationSketch(obligations=[AtomicObligation("filter_transfer", 0.9, "needs transferred filter")])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=facilities.source_id,
                        file_name=facilities.file_name,
                        view_name=facilities.raw_view_name,
                        column_name="facility_name",
                        role="attribute",
                        score=10.0,
                    )
                ],
                plan_kind="filter_join",
                filter_bindings=[
                    Binding(
                        source_id=apartments.source_id,
                        file_name=apartments.file_name,
                        view_name=apartments.raw_view_name,
                        column_name="bedroom_count",
                        role="filter",
                        score=8.0,
                        reasons=["numeric_filter_compatible"],
                        metadata={"attribute": "bedroom_count", "operator": ">", "value": 4},
                    )
                ],
                filter_join_paths=[
                    AnchorPath(
                        path_source_ids=[facilities.source_id, apartments.source_id],
                        edges=[
                            {
                                "left_source_id": facilities.source_id,
                                "right_source_id": apartments.source_id,
                                "left_column": "facility_name",
                                "right_column": "facility_code",
                                "left_transform": "identity",
                                "right_transform": "identity",
                                "overlap": 0.2,
                            }
                        ],
                        score=0.2,
                        notes=["filter_join_path"],
                    )
                ],
                confidence=5.0,
            )

            reasons = _semantic_complete_reasons(plan, observable, obligations, catalog)
            self.assertIn("weak_filter_path:attribute_echo_path", reasons)

    def test_plan_sort_key_prefers_fewer_semantic_gaps(self) -> None:
        better = SupportPlan(
            output_bindings=[],
            confidence=9.0,
            plan_score=PlanScore(
                family_name="aggregation_join",
                base_retrieval_score=6.0,
                output_consistency=1.0,
                filter_consistency=0.0,
                aggregation_consistency=1.0,
                ordering_consistency=0.0,
                obligation_consistency=1.0,
                shape_sanity=0.5,
                semantic_complete=False,
                semantic_gap_count=1,
                semantic_complete_reasons=["missing_anchor"],
                total=9.0,
            ),
        )
        worse = SupportPlan(
            output_bindings=[],
            confidence=15.0,
            plan_score=PlanScore(
                family_name="aggregation_join",
                base_retrieval_score=8.0,
                output_consistency=1.0,
                filter_consistency=0.0,
                aggregation_consistency=1.0,
                ordering_consistency=0.0,
                obligation_consistency=1.0,
                shape_sanity=0.5,
                semantic_complete=False,
                semantic_gap_count=3,
                semantic_complete_reasons=["missing_anchor", "measure_off_support_source", "wrong_ranking_target"],
                total=15.0,
            ),
        )

        self.assertLess(_plan_sort_key(better), _plan_sort_key(worse))

    def test_semantic_complete_flags_collapsed_output_sources_against_multisource_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Location": ["A"], "Aircraft": ["Jet"]}).to_csv(workspace / "facts.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[
                    ObservableSlot(label="Location", role="location"),
                    ObservableSlot(label="Aircraft", role="entity"),
                ]
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="Aircraft",
                        role="location",
                        score=10.0,
                        metadata={"slot_label": "Location"},
                    ),
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="Aircraft",
                        role="entity",
                        score=10.0,
                        metadata={"slot_label": "Aircraft"},
                    ),
                ],
                plan_kind="direct_join",
            )

            reasons = _semantic_complete_reasons(
                plan,
                observable,
                obligations,
                catalog,
                grounding_hints={"strong_multi_source_output": True, "output_priors_by_slot": {}},
            )

            self.assertIn("duplicate_output_binding", reasons)
            self.assertIn("collapsed_output_sources_against_llm_hint", reasons)

    def test_direct_join_prefers_source_that_can_ground_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"book_id": [1, 2], "Title": ["A", "B"]}).to_csv(workspace / "books.csv", index=False)
            pd.DataFrame({"Title": ["A", "B"]}).to_csv(workspace / "book_titles.csv", index=False)
            pd.DataFrame({"book_id": [1, 2], "publication_price": [10, 20]}).to_csv(workspace / "publication.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Title", role="entity")],
                order_hint={"direction": "desc", "target": "publication price"},
            )
            obligations = ObligationSketch(obligations=[])

            summary = search_support_plans(
                instruction="Show the titles of books in descending order of publication price.",
                observable_sketch=observable,
                obligation_sketch=obligations,
                catalog=catalog,
            )

            best_plan = summary["best_plan"]
            self.assertEqual("direct_join", best_plan.plan_kind)
            self.assertIsNotNone(best_plan.order_binding)
            self.assertEqual("publication.csv", best_plan.order_binding.file_name)
            self.assertEqual("books.csv", best_plan.output_bindings[0].file_name)

    def test_direct_join_with_unresolved_order_target_is_not_semantically_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Title": ["A", "B"]}).to_csv(workspace / "books.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            source = next(iter(catalog.sources.values()))
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Title", role="entity")],
                order_hint={"direction": "desc", "target": "publication price"},
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name="Title",
                        role="entity",
                        score=12.0,
                    )
                ],
                plan_kind="direct_join",
                operator_plan={"direction": "desc", "target": "publication price"},
                confidence=5.0,
            )

            reasons = _semantic_complete_reasons(plan, observable, obligations, catalog)
            self.assertIn("missing_order_binding", reasons)

    def test_cross_source_order_without_path_is_hard_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"Title": ["A", "B"]}).to_csv(workspace / "books.csv", index=False)
            pd.DataFrame({"publication_price": [10, 20]}).to_csv(workspace / "publication.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            books = next(source for source in catalog.sources.values() if source.file_name == "books.csv")
            publication = next(source for source in catalog.sources.values() if source.file_name == "publication.csv")
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Title", role="entity")],
                order_hint={"direction": "desc", "target": "publication price"},
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=books.source_id,
                        file_name=books.file_name,
                        view_name=books.raw_view_name,
                        column_name="Title",
                        role="entity",
                        score=12.0,
                    )
                ],
                plan_kind="direct_join",
                order_binding=Binding(
                    source_id=publication.source_id,
                    file_name=publication.file_name,
                    view_name=publication.raw_view_name,
                    column_name="publication_price",
                    role="order",
                    score=8.0,
                    reasons=["order_numeric_compatible"],
                    metadata={"target": "publication price", "direction": "desc"},
                ),
                operator_plan={"direction": "desc", "target": "publication price"},
                confidence=5.0,
            )

            reasons = _hard_invalid_reasons(plan, observable, obligations, catalog)
            self.assertIn("order_source_not_connected", reasons)

    def test_compile_support_join_exists_uses_distinct_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"customer_id": [1, 2], "customer_name": ["A", "B"]}).to_csv(workspace / "customers.csv", index=False)
            pd.DataFrame({"account_id": [10, 11], "customer_id": [1, 1]}).to_csv(workspace / "accounts.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            customers = next(source for source in catalog.sources.values() if source.file_name == "customers.csv")
            accounts = next(source for source in catalog.sources.values() if source.file_name == "accounts.csv")
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=customers.source_id,
                        file_name=customers.file_name,
                        view_name=customers.raw_view_name,
                        column_name="customer_name",
                        role="entity",
                        score=10.0,
                        metadata={"slot_label": "customer_name"},
                    )
                ],
                plan_kind="support_join",
                support_binding=Binding(
                    source_id=accounts.source_id,
                    file_name=accounts.file_name,
                    view_name=accounts.raw_view_name,
                    column_name="customer_id",
                    role="support",
                    score=8.0,
                ),
                anchor_binding=AnchorPath(
                    path_source_ids=[accounts.source_id, customers.source_id],
                    edges=[
                        {
                            "edge_id": "e1",
                            "left_source_id": customers.source_id,
                            "right_source_id": accounts.source_id,
                            "left_column": "customer_id",
                            "right_column": "customer_id",
                            "left_transform": "identity",
                            "right_transform": "identity",
                            "overlap": 1.0,
                        }
                    ],
                    score=1.0,
                ),
                operator_plan={"exists": True},
            )
            observable = ObservableSketch(output_slots=[ObservableSlot(label="customer_name", role="entity")], operator_hints=["exists"])
            obligations = ObligationSketch(obligations=[AtomicObligation("existence_check", 0.9, "requires related rows")])
            ir = build_support_plan_ir(plan, observable, obligations, catalog)
            out_csv = Path(tmp_dir) / "out.csv"
            meta = compile_support_plan(plan, ir, catalog, {"required_columns": ["customer_name"]}, out_csv)

            self.assertTrue(meta["compiled"])
            self.assertIn("SELECT DISTINCT", meta["final_sql"])

    def test_weak_order_path_scores_below_strong_order_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"book_id": [1, 2], "Title": ["A", "B"]}).to_csv(workspace / "books.csv", index=False)
            pd.DataFrame({"book_id": [1, 2], "publication_price": [10, 20]}).to_csv(workspace / "publication.csv", index=False)
            pd.DataFrame({"Title": ["A", "B"], "publication_price": [10, 20]}).to_csv(workspace / "projection.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            books = next(source for source in catalog.sources.values() if source.file_name == "books.csv")
            publication = next(source for source in catalog.sources.values() if source.file_name == "publication.csv")
            projection = next(source for source in catalog.sources.values() if source.file_name == "projection.csv")
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="Title", role="entity")],
                order_hint={"direction": "desc", "target": "publication price"},
            )
            obligations = ObligationSketch(obligations=[])
            strong_plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=books.source_id,
                        file_name=books.file_name,
                        view_name=books.raw_view_name,
                        column_name="Title",
                        role="entity",
                        score=12.0,
                    )
                ],
                plan_kind="direct_join",
                order_binding=Binding(
                    source_id=publication.source_id,
                    file_name=publication.file_name,
                    view_name=publication.raw_view_name,
                    column_name="publication_price",
                    role="order",
                    score=8.0,
                    reasons=["order_numeric_compatible"],
                    metadata={"target": "publication price", "direction": "desc"},
                ),
                order_join_path=AnchorPath(
                    path_source_ids=[books.source_id, publication.source_id],
                    edges=[
                        {
                            "left_source_id": books.source_id,
                            "right_source_id": publication.source_id,
                            "left_column": "book_id",
                            "right_column": "book_id",
                            "left_transform": "identity",
                            "right_transform": "identity",
                            "overlap": 0.9,
                        }
                    ],
                    score=0.9,
                    notes=["order_join_path"],
                ),
                operator_plan={"direction": "desc", "target": "publication price"},
            )
            weak_plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=books.source_id,
                        file_name=books.file_name,
                        view_name=books.raw_view_name,
                        column_name="Title",
                        role="entity",
                        score=12.0,
                    )
                ],
                plan_kind="direct_join",
                order_binding=Binding(
                    source_id=publication.source_id,
                    file_name=publication.file_name,
                    view_name=publication.raw_view_name,
                    column_name="publication_price",
                    role="order",
                    score=8.0,
                    reasons=["order_numeric_compatible"],
                    metadata={"target": "publication price", "direction": "desc"},
                ),
                order_join_path=AnchorPath(
                    path_source_ids=[books.source_id, projection.source_id, publication.source_id],
                    edges=[
                        {
                            "left_source_id": books.source_id,
                            "right_source_id": projection.source_id,
                            "left_column": "Title",
                            "right_column": "Title",
                            "left_transform": "identity",
                            "right_transform": "identity",
                            "overlap": 1.0,
                        },
                        {
                            "left_source_id": projection.source_id,
                            "right_source_id": publication.source_id,
                            "left_column": "publication_price",
                            "right_column": "publication_price",
                            "left_transform": "identity",
                            "right_transform": "identity",
                            "overlap": 1.0,
                        },
                    ],
                    score=2.0,
                    notes=["order_join_path"],
                ),
                operator_plan={"direction": "desc", "target": "publication price"},
            )

            strong_score, _ = _joint_rerank_adjustment(strong_plan, observable, obligations, catalog)
            weak_score, _ = _joint_rerank_adjustment(weak_plan, observable, obligations, catalog)
            self.assertGreater(strong_score, weak_score)

    def test_ordered_path_source_ids_preserves_multihop_sequence(self) -> None:
        start = "s_out"
        edges = [
            {"left_source_id": "s_out", "right_source_id": "s_mid", "left_column": "facility_code", "right_column": "facility_code"},
            {"left_source_id": "s_fact", "right_source_id": "s_mid", "left_column": "apt_id", "right_column": "apt_id"},
        ]
        self.assertEqual(["s_out", "s_mid", "s_fact"], _ordered_path_source_ids(start, edges))

    def test_semantic_completeness_flags_output_projection_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            pd.DataFrame({"apt_id": [1, 2], "facility_code": ["gym", "pool"]}).to_csv(workspace / "dim_a.csv", index=False)
            pd.DataFrame({"apt_id": [1, 2], "facility_code": ["gym", "pool"]}).to_csv(workspace / "dim_b.csv", index=False)
            pd.DataFrame({"apt_id": [1, 2], "bedroom_count": [5, 2]}).to_csv(workspace / "fact.csv", index=False)
            catalog = build_workspace_catalog(workspace)
            dim_a = next(source for source in catalog.sources.values() if source.file_name == "dim_a.csv")
            dim_b = next(source for source in catalog.sources.values() if source.file_name == "dim_b.csv")
            fact = next(source for source in catalog.sources.values() if source.file_name == "fact.csv")
            observable = ObservableSketch(
                output_slots=[ObservableSlot(label="facility_code", role="code")],
                filter_hints=[{"attribute": "bedroom_count", "operator": ">", "value": 4}],
            )
            obligations = ObligationSketch(obligations=[])
            plan = SupportPlan(
                output_bindings=[
                    Binding(
                        source_id=dim_a.source_id,
                        file_name=dim_a.file_name,
                        view_name=dim_a.raw_view_name,
                        column_name="facility_code",
                        role="code",
                        score=12.0,
                    )
                ],
                plan_kind="filter_join",
                filter_bindings=[
                    Binding(
                        source_id=fact.source_id,
                        file_name=fact.file_name,
                        view_name=fact.raw_view_name,
                        column_name="bedroom_count",
                        role="filter",
                        score=8.0,
                        reasons=["numeric_filter_compatible"],
                        metadata={"attribute": "bedroom_count", "operator": ">", "value": 4},
                    )
                ],
                filter_join_paths=[
                    AnchorPath(
                        path_source_ids=[dim_a.source_id, dim_b.source_id, fact.source_id],
                        edges=[
                            {
                                "left_source_id": dim_a.source_id,
                                "right_source_id": dim_b.source_id,
                                "left_column": "facility_code",
                                "right_column": "facility_code",
                                "left_transform": "identity",
                                "right_transform": "identity",
                                "overlap": 1.0,
                            },
                            {
                                "left_source_id": fact.source_id,
                                "right_source_id": dim_b.source_id,
                                "left_column": "apt_id",
                                "right_column": "apt_id",
                                "left_transform": "identity",
                                "right_transform": "identity",
                                "overlap": 0.9,
                            },
                        ],
                        score=1.9,
                        notes=["filter_join_path"],
                    )
                ],
                confidence=5.0,
            )

            reasons = _semantic_complete_reasons(plan, observable, obligations, catalog)
            self.assertIn("filter_path_via_output_projection", reasons)


if __name__ == "__main__":
    unittest.main()
