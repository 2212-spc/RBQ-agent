from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from evaluation.llm_backend import LLMBackendSession
from evaluation.workspace_catalog import WorkspaceCatalog

from .types import AtomicObligation, ObligationSketch, ObservableSketch, RolePrior


_OBLIGATION_SYSTEM = """You are a requirement analyst for data queries.
Given a question and an observable sketch, infer latent answerability obligations.
Return JSON with keys:
- atomic_obligations: list of {name, probability, reason}
- role_priors: list of {role, target, probability, reason}
- family_labels: list of {label, probability, reason}

Valid obligation names:
support_relation, aggregation_support, filter_transfer, multihop, value_alignment, existence_check, intersection_requirement

Family labels are summaries only."""


_VALID_OBLIGATION_NAMES = (
    "support_relation",
    "aggregation_support",
    "filter_transfer",
    "multihop",
    "value_alignment",
    "existence_check",
    "intersection_requirement",
)


def _fallback_obligations(instruction: str, observable_sketch: ObservableSketch) -> ObligationSketch:
    lower = instruction.lower()
    aggregation_tokens = {"count", "sum", "avg", "average", "least", "fewest", "most", "highest", "lowest", "total"}
    has_aggregation = bool(aggregation_tokens & set(lower.split())) or "number of" in lower or "how many" in lower
    has_filters = bool(observable_sketch.filter_hints) or bool(observable_sketch.time_hints.get("years")) or bool(
        observable_sketch.time_hints.get("months")
    )
    has_exists = "exists" in observable_sketch.operator_hints
    has_intersection = "intersection" in observable_sketch.operator_hints
    support_prob = 0.8 if has_aggregation and any(slot.role in {"entity", "attribute", "location"} for slot in observable_sketch.output_slots) else 0.2
    if has_exists:
        support_prob = max(support_prob, 0.7)
    aggregation_prob = 0.9 if has_aggregation else 0.1
    filter_transfer_prob = 0.7 if has_filters and support_prob >= 0.5 else 0.2 if has_filters else 0.05
    multihop_prob = 0.4 if support_prob >= 0.5 and len(observable_sketch.output_slots) > 1 else 0.15
    value_alignment_prob = 0.35 if any(token in lower for token in ["code", "id", "number", "formatted"]) else 0.1
    existence_prob = 0.85 if has_exists else 0.05
    intersection_prob = 0.8 if has_intersection else 0.05

    obligations = [
        AtomicObligation("support_relation", support_prob, "aggregation over output-like entity usually needs latent support relation"),
        AtomicObligation("aggregation_support", aggregation_prob, "query requests aggregated evidence"),
        AtomicObligation("filter_transfer", filter_transfer_prob, "filters/time hints may live on support side rather than output side"),
        AtomicObligation("multihop", multihop_prob, "likely needs traversal beyond a single output source"),
        AtomicObligation("value_alignment", value_alignment_prob, "join may require non-identity normalization"),
        AtomicObligation("existence_check", existence_prob, "query asks whether related rows exist or asks for entities having any related rows"),
        AtomicObligation("intersection_requirement", intersection_prob, "query requires satisfying multiple related values simultaneously"),
    ]
    role_priors = [
        RolePrior("output_role", "dimension" if support_prob >= 0.5 else "mixed", 0.75 if support_prob >= 0.5 else 0.45, "text-like output columns usually live on dimension side"),
        RolePrior("support_role", "fact" if aggregation_prob >= 0.5 else "mixed", 0.8 if aggregation_prob >= 0.5 else 0.45, "aggregated evidence usually comes from event/fact-like relation"),
        RolePrior("evidence_role", "fact_or_event", 0.7 if aggregation_prob >= 0.5 else 0.4, "filters and measures often attach to evidence-bearing rows"),
    ]
    family_labels: List[Dict[str, Any]] = []
    if support_prob >= 0.5 and aggregation_prob >= 0.5:
        family_labels.append({"label": "AggregationJoin", "probability": 0.85, "reason": "aggregation + latent support relation"})
    elif has_exists:
        family_labels.append({"label": "SupportJoin", "probability": 0.75, "reason": "existence questions require related-row support"})
    elif has_filters and support_prob >= 0.5:
        family_labels.append({"label": "FilterJoin", "probability": 0.7, "reason": "filter likely transfers across a join"})
    else:
        family_labels.append({"label": "DirectJoin", "probability": 0.6, "reason": "no strong latent support evidence"})
    return ObligationSketch(obligations=obligations, role_priors=role_priors, family_labels=family_labels, raw_response={"fallback": True})


def disable_obligation_reasoning(obligation_sketch: ObligationSketch) -> ObligationSketch:
    reason_by_name = {
        obligation.name: obligation.reason
        for obligation in obligation_sketch.obligations
    }
    obligations = [
        AtomicObligation(
            name=name,
            probability=0.0,
            reason=f"disabled_for_ablation:{reason_by_name.get(name, 'obligation_reasoning_off')}",
        )
        for name in _VALID_OBLIGATION_NAMES
    ]
    return ObligationSketch(
        obligations=obligations,
        role_priors=list(obligation_sketch.role_priors),
        family_labels=[],
        raw_response={
            "obligation_mode": "off",
            "base_raw_response": obligation_sketch.raw_response,
        },
    )


def _workspace_context_for_obligation(catalog: WorkspaceCatalog | None) -> str:
    """Build a compact workspace structure summary for the obligation LLM prompt."""
    if catalog is None or not catalog.sources:
        return ""

    lines = [f"\nWorkspace structure ({len(catalog.sources)} data sources):"]
    for source in catalog.sources.values():
        key_cols = source.key_columns[:3]
        text_cols = [c for c, p in source.column_profiles.items() if p.text_like][:3]
        measure_cols = [c for c, p in source.column_profiles.items() if p.measure_like][:3]
        parts = [f"  - {source.source_id} ({source.row_count} rows, role={source.role_hint})"]
        if key_cols:
            parts.append(f"    keys: {key_cols}")
        if text_cols:
            parts.append(f"    text: {text_cols}")
        if measure_cols:
            parts.append(f"    measures: {measure_cols}")
        lines.extend(parts)

    # Add top join edges
    seen = set()
    edges = []
    for source in catalog.sources.values():
        for edge in catalog.join_neighbors(source.source_id):
            if edge.edge_id not in seen:
                seen.add(edge.edge_id)
                edges.append(edge)
    edges.sort(key=lambda e: e.overlap, reverse=True)
    if edges:
        lines.append(f"\nJoin edges ({len(edges)} total, showing top {min(len(edges), 10)}):")
        for e in edges[:10]:
            lines.append(f"  {e.left_source_id}.{e.left_column} <-> {e.right_source_id}.{e.right_column} (overlap={e.overlap:.3f})")

    return "\n".join(lines)


def build_obligation_sketch(
    instruction: str,
    observable_sketch: ObservableSketch,
    session: LLMBackendSession | None = None,
    catalog: WorkspaceCatalog | None = None,
) -> ObligationSketch:
    fallback = _fallback_obligations(instruction, observable_sketch)
    if session is None or session.remaining_calls <= 0:
        return fallback

    workspace_ctx = _workspace_context_for_obligation(catalog)
    prompt = (
        f"Question:\n{instruction}\n\n"
        f"Observable sketch:\n{json.dumps(observable_sketch.to_dict(), ensure_ascii=False)}\n"
        f"{workspace_ctx}\n\n"
        "Based on the question AND the workspace structure, infer latent answerability obligations.\n"
        "Key considerations:\n"
        "- If the output columns and filter columns appear to be in DIFFERENT sources, filter_transfer is likely needed.\n"
        "- If answering requires counting/summing rows from a different source than the output, support_relation is needed.\n"
        "- If there is only 1 source, support_relation is unlikely.\n"
        "- Look at the join edges to determine if multi-hop paths are needed."
    )
    try:
        raw = session.chat_json(_OBLIGATION_SYSTEM, prompt, cache_namespace="obligation_sketch")
    except Exception:
        return fallback

    has_explicit_filters = bool(observable_sketch.filter_hints) or bool(observable_sketch.time_hints.get("years")) or bool(
        observable_sketch.time_hints.get("months")
    )
    _agg_text = instruction.lower()

    # TEXT-ONLY aggregation signal.  LLMs frequently leave operator_hints /
    # measure_hints empty even when the question asks for aggregation, so we
    # derive this independently from the raw instruction to be deterministic.
    _text_requires_agg = (
        "number of" in _agg_text
        or "how many" in _agg_text
        or any(bool(re.search(r"\b" + t + r"\b", _agg_text)) for t in (
            "count", "sum", "average", "total", "fewest", "least", "most",
            "highest", "lowest",
        ))
    )

    has_explicit_aggregation = (
        bool(observable_sketch.measure_hints)
        or any(
            item in {"count", "sum", "avg", "average", "max", "min"}
            for item in observable_sketch.operator_hints
        )
        or _text_requires_agg
    )

    # True when an output slot label already encodes the aggregation function
    # (e.g. "avg(amount_of_transaction)") — these are direct GROUP-BY queries
    # that do not need a support CTE.
    _AGG_FN_PREFIXES = ("avg(", "count(", "sum(", "max(", "min(")
    has_agg_in_output_labels = any(
        any(slot.label.lower().startswith(fn) or f" {fn}" in slot.label.lower() for fn in _AGG_FN_PREFIXES)
        for slot in observable_sketch.output_slots
    )

    # Decide whether to suppress support_relation / multihop / value_alignment.
    # We suppress them for:
    #   (a) pure JOIN questions  → no aggregation words in text at all
    #   (b) direct GROUP-BY questions → aggregation already encoded in output labels
    # This uses TEXT-only signals to be robust against LLM observable-sketch
    # non-determinism (operator_hints / measure_hints can be empty even for
    # genuine aggregation questions depending on the LLM call outcome).
    _suppress_support_obligations = not _text_requires_agg or has_agg_in_output_labels

    obligations = []
    for item in raw.get("atomic_obligations", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name not in _VALID_OBLIGATION_NAMES:
            continue
        probability = float(item.get("probability", 0.0))
        if name == "filter_transfer" and not has_explicit_filters:
            probability = min(probability, 0.25)
        if name == "aggregation_support" and not has_explicit_aggregation:
            probability = min(probability, 0.2)
        if name == "multihop" and not has_explicit_filters and len(observable_sketch.output_slots) <= 1:
            probability = min(probability, 0.25)
        # Guard against LLM over-firing support-plan obligations on direct JOIN /
        # direct GROUP-BY queries.  When suppressed, all three caps land at 0.44
        # (just below the 0.45 activation threshold) so the planner uses a plain
        # JOIN plan instead of a support CTE.
        if name in {"support_relation", "multihop", "value_alignment"} and _suppress_support_obligations:
            probability = min(probability, 0.44)
        obligations.append(
            AtomicObligation(
                name=name,
                probability=probability,
                reason=str(item.get("reason", "")),
            )
        )
    if not obligations:
        return fallback

    role_priors = []
    for item in raw.get("role_priors", []):
        if not isinstance(item, dict):
            continue
        role_priors.append(
            RolePrior(
                role=str(item.get("role", "")),
                target=str(item.get("target", "")),
                probability=float(item.get("probability", 0.0)),
                reason=str(item.get("reason", "")),
            )
        )
    family_labels = [dict(item) for item in raw.get("family_labels", []) if isinstance(item, dict)]
    return ObligationSketch(
        obligations=obligations,
        role_priors=role_priors or fallback.role_priors,
        family_labels=family_labels or fallback.family_labels,
        raw_response=raw,
    )
