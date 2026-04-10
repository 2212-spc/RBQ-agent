from __future__ import annotations

from typing import Any, Dict, List

from evaluation.workspace_catalog import WorkspaceCatalog

from .types import ObligationSketch, ObservableSketch, SupportPlan


def verify_support_plan(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    obligation_sketch: ObligationSketch,
    catalog: WorkspaceCatalog,
) -> List[Dict[str, Any]]:
    trace: List[Dict[str, Any]] = []

    output_score = sum(binding.score for binding in plan.output_bindings) / max(len(plan.output_bindings), 1)
    trace.append(
        {
            "check": "output_binding",
            "score": round(output_score, 4),
            "passed": bool(plan.output_bindings and output_score >= 7.5),
            "evidence": [binding.to_dict() for binding in plan.output_bindings],
        }
    )

    support_required = obligation_sketch.probability("support_relation") >= 0.45
    if support_required:
        support_score = plan.support_binding.score if plan.support_binding is not None else 0.0
        anchor_score = plan.anchor_binding.score if plan.anchor_binding is not None else 0.0
        trace.append(
            {
                "check": "support_relation",
                "score": round((support_score + anchor_score) / 2.0, 4),
                "passed": plan.support_binding is not None and plan.anchor_binding is not None and anchor_score >= 0.12,
                "evidence": {
                    "support_binding": plan.support_binding.to_dict() if plan.support_binding is not None else None,
                    "anchor_binding": plan.anchor_binding.to_dict() if plan.anchor_binding is not None else None,
                },
            }
        )
    if obligation_sketch.probability("existence_check") >= 0.45:
        trace.append(
            {
                "check": "existence_check",
                "score": round((plan.support_binding.score if plan.support_binding is not None else 0.0), 4),
                "passed": plan.support_binding is not None,
                "evidence": {
                    "support_binding": plan.support_binding.to_dict() if plan.support_binding is not None else None,
                    "exists": bool(plan.operator_plan.get("exists")),
                },
            }
        )

    if obligation_sketch.probability("aggregation_support") >= 0.45:
        measure_ok = (
            plan.operator_plan.get("aggregation") == "count"
            or plan.measure_binding is not None
            or any(b.role == "measure" for b in plan.output_bindings)
        )
        trace.append(
            {
                "check": "aggregation_support",
                "score": round((plan.measure_binding.score if plan.measure_binding is not None else 8.0 if plan.operator_plan.get("aggregation") == "count" else 0.0), 4),
                "passed": measure_ok,
                "evidence": {
                    "aggregation": plan.operator_plan.get("aggregation"),
                    "measure_binding": plan.measure_binding.to_dict() if plan.measure_binding is not None else None,
                },
            }
        )

    if observable_sketch.filter_hints or observable_sketch.time_hints.get("years") or observable_sketch.time_hints.get("months"):
        filter_score = sum(binding.score for binding in plan.filter_bindings) / max(len(plan.filter_bindings), 1) if plan.filter_bindings else 0.0
        trace.append(
            {
                "check": "filter_transfer",
                "score": round(filter_score, 4),
                "passed": bool(plan.filter_bindings),
                "evidence": [binding.to_dict() for binding in plan.filter_bindings],
            }
        )
    if obligation_sketch.probability("intersection_requirement") >= 0.45:
        trace.append(
            {
                "check": "intersection_requirement",
                "score": round(sum(binding.score for binding in plan.filter_bindings) / max(len(plan.filter_bindings), 1), 4) if plan.filter_bindings else 0.0,
                "passed": len(plan.filter_bindings) >= 2,
                "evidence": [binding.to_dict() for binding in plan.filter_bindings],
            }
        )

    if plan.anchor_binding is not None:
        trace.append(
            {
                "check": "value_alignment",
                "score": round(plan.anchor_binding.score, 4),
                "passed": any(
                    edge.get("left_transform") != "identity" or edge.get("right_transform") != "identity"
                    for edge in plan.anchor_binding.edges
                )
                or plan.anchor_binding.score >= 0.12,
                "evidence": plan.anchor_binding.to_dict(),
            }
        )

    role_consistency_score = 0.0
    if plan.support_binding is not None and plan.output_bindings:
        support_source = catalog.source(plan.support_binding.source_id)
        output_source = catalog.source(plan.output_bindings[0].source_id)
        if support_source.role_hint == "fact":
            role_consistency_score += 0.6
        if output_source.role_hint in {"dimension", "unknown"}:
            role_consistency_score += 0.4
    else:
        role_consistency_score = 0.5
    trace.append(
        {
            "check": "role_consistency",
            "score": round(role_consistency_score, 4),
            "passed": role_consistency_score >= 0.5,
            "evidence": {
                "support_source": plan.support_binding.source_id if plan.support_binding is not None else None,
                "output_source": plan.output_bindings[0].source_id if plan.output_bindings else None,
            },
        }
    )
    return trace


def obligations_from_trace(trace: List[Dict[str, Any]], obligation_sketch: ObligationSketch) -> tuple[List[str], List[str]]:
    satisfied: List[str] = []
    unmet: List[str] = []
    check_map = {
        "support_relation": "support_relation",
        "existence_check": "existence_check",
        "aggregation_support": "aggregation_support",
        "filter_transfer": "filter_transfer",
        "intersection_requirement": "intersection_requirement",
        "value_alignment": "value_alignment",
    }
    for obligation in obligation_sketch.obligations:
        if obligation.probability < 0.45:
            continue
        target_check = obligation.name
        passed = False
        for item in trace:
            if check_map.get(item["check"], item["check"]) == target_check and item["passed"]:
                passed = True
                break
        if obligation.name == "multihop":
            passed = any(item["check"] == "support_relation" and item["passed"] for item in trace)
        if passed:
            satisfied.append(obligation.name)
        else:
            unmet.append(obligation.name)
    return satisfied, unmet
