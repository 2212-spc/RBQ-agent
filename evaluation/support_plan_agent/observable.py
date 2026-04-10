from __future__ import annotations

from typing import Any, Dict, List

from evaluation.llm_backend import LLMBackendSession
from evaluation.workspace_catalog import extract_numeric_filters, extract_time_hints

from .types import ObservableSketch, ObservableSlot
from .utils import infer_operator_hints, infer_output_role, normalize_json_list


_OBSERVABLE_SYSTEM = """You are a query-structure analyst.
Return a JSON object with keys:
- output_slots: list of {label, role}
- filter_hints: list of {attribute, operator, value, value_text}
- time_hints: {years: [int], months: [int]}
- measure_hints: list of strings
- grouping_hints: list of strings
- operator_hints: list of strings
- order_hint: {target, direction, limit}

Only capture surface semantics. Do not infer hidden support tables or join plans.
Return valid JSON only."""

_ROLE_MAP = {
    "dimension": "entity",
    "fact": "measure",
    "group": "entity",
    "text": "attribute",
}


def _fallback_observable(instruction: str, deliverable_spec: Dict[str, Any]) -> ObservableSketch:
    required_columns = deliverable_spec.get("required_columns", [])
    output_slots = [
        ObservableSlot(label=str(column), role=infer_output_role(str(column), instruction))
        for column in required_columns
    ]
    operator = infer_operator_hints(instruction)
    operator_hints = []
    if operator["aggregation"]:
        operator_hints.append(operator["aggregation"])
    if operator["exists"]:
        operator_hints.append("exists")
    if operator.get("intersection"):
        operator_hints.append("intersection")
    if operator["group_by"]:
        operator_hints.append("group_by")
    if operator["direction"]:
        operator_hints.append(f"top_{operator['direction']}")
    return ObservableSketch(
        output_slots=output_slots,
        filter_hints=extract_numeric_filters(instruction),
        time_hints=extract_time_hints(instruction),
        measure_hints=[operator["aggregation"]] if operator["aggregation"] else [],
        grouping_hints=["group_by"] if operator["group_by"] else [],
        operator_hints=operator_hints,
        order_hint={key: value for key, value in operator.items() if key in {"direction", "limit", "target"} and value is not None},
        raw_response={"fallback": True},
    )


def build_observable_sketch(
    instruction: str,
    deliverable_spec: Dict[str, Any],
    session: LLMBackendSession | None = None,
) -> ObservableSketch:
    required_columns = [str(column) for column in deliverable_spec.get("required_columns", [])]
    fallback = _fallback_observable(instruction, deliverable_spec)
    if session is None or session.remaining_calls <= 0:
        return fallback
    prompt = (
        f"Question:\n{instruction}\n\n"
        f"Required output columns: {required_columns}\n\n"
        "Assign the role for each required output column and recover only observable query hints."
    )
    try:
        raw = session.chat_json(_OBSERVABLE_SYSTEM, prompt, cache_namespace="observable_sketch")
    except Exception:
        return fallback

    output_slots: List[ObservableSlot] = []
    for item in normalize_json_list(raw.get("output_slots", [])):
        label = str(item.get("label", ""))
        if label not in required_columns:
            continue
        output_slots.append(
            ObservableSlot(
                label=label,
                role=_ROLE_MAP.get(str(item.get("role", "")).lower(), str(item.get("role", infer_output_role(label, instruction)))),
                metadata={key: value for key, value in item.items() if key not in {"label", "role"}},
            )
        )
    seen = {slot.label for slot in output_slots}
    for column in required_columns:
        if column not in seen:
            output_slots.append(ObservableSlot(label=column, role=infer_output_role(column, instruction)))

    return ObservableSketch(
        output_slots=output_slots,
        filter_hints=normalize_json_list(raw.get("filter_hints", [])) or fallback.filter_hints,
        time_hints=dict(raw.get("time_hints", fallback.time_hints) or fallback.time_hints),
        measure_hints=[str(item) for item in raw.get("measure_hints", fallback.measure_hints) if str(item).strip()],
        grouping_hints=[str(item) for item in raw.get("grouping_hints", fallback.grouping_hints) if str(item).strip()],
        operator_hints=[str(item) for item in raw.get("operator_hints", fallback.operator_hints) if str(item).strip()],
        order_hint=dict(raw.get("order_hint", fallback.order_hint) or fallback.order_hint),
        raw_response=raw,
    )
