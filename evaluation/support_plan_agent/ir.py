from __future__ import annotations

from typing import Any, Dict, List

from evaluation.workspace_catalog import WorkspaceCatalog

from .types import IRStep, ObligationSketch, ObservableSketch, SupportPlan, SupportPlanIR


def build_support_plan_ir(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    obligation_sketch: ObligationSketch,
    catalog: WorkspaceCatalog,
) -> SupportPlanIR:
    del obligation_sketch
    del catalog
    if not plan.output_bindings:
        return SupportPlanIR(kind="empty", compile_ready=False, compile_reason="missing_output_bindings")
    if plan.unmet_obligations:
        return SupportPlanIR(
            kind="blocked",
            compile_ready=False,
            compile_reason=f"unmet_obligations:{','.join(plan.unmet_obligations)}",
            metadata={"unmet_obligations": plan.unmet_obligations},
        )

    steps: List[IRStep] = []
    primary_output = plan.output_bindings[0]
    steps.append(IRStep(op="SCAN", args={"source_id": primary_output.source_id, "view_name": primary_output.view_name, "role": "output"}))

    for path in plan.output_join_paths:
        for edge in path.edges:
            steps.append(IRStep(op="JOIN", args={"edge": edge, "kind": "output_join"}))

    for path in plan.filter_join_paths:
        for edge in path.edges:
            steps.append(IRStep(op="JOIN", args={"edge": edge, "kind": "filter_path"}))

    if plan.support_binding is not None:
        steps.append(
            IRStep(
                op="SCAN",
                args={"source_id": plan.support_binding.source_id, "view_name": plan.support_binding.view_name, "role": "support"},
            )
        )
        if plan.anchor_binding is not None:
            for edge in plan.anchor_binding.edges:
                steps.append(IRStep(op="JOIN", args={"edge": edge, "kind": "support_path"}))

    for binding in plan.filter_bindings:
        steps.append(IRStep(op="FILTER", args=binding.to_dict()))

    if plan.operator_plan.get("aggregation"):
        steps.append(
            IRStep(
                op="AGG",
                args={
                    "aggregation": plan.operator_plan.get("aggregation"),
                    "measure_binding": plan.measure_binding.to_dict() if plan.measure_binding is not None else None,
                },
            )
        )
    if plan.operator_plan.get("direction"):
        steps.append(
            IRStep(
                op="RANK",
                args={"direction": plan.operator_plan.get("direction"), "limit": plan.operator_plan.get("limit", 1)},
            )
        )
    steps.append(IRStep(op="PROJECT", args={"columns": [binding.to_dict() for binding in plan.output_bindings]}))
    kind = plan.plan_kind or ("aggregation_support" if plan.support_binding is not None else "direct")
    return SupportPlanIR(
        kind=kind,
        compile_ready=True,
        steps=steps,
        metadata={
            "primary_output_source_id": primary_output.source_id,
            "support_source_id": plan.support_binding.source_id if plan.support_binding is not None else None,
            "filter_path_count": len(plan.filter_join_paths),
            "required_columns": [slot.label for slot in observable_sketch.output_slots],
            "aggregation": plan.operator_plan.get("aggregation"),
            "direction": plan.operator_plan.get("direction"),
            "limit": plan.operator_plan.get("limit"),
        },
    )
