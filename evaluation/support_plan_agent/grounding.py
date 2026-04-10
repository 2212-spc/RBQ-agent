"""LLM-driven pre-grounding: let the LLM look at workspace schema + sample values
and recommend the best (source_id, column_name) bindings for each output slot and
filter hint.

This module is the single highest-ROI improvement to the support_plan_agent because
it replaces the weak name_overlap_score heuristic with LLM semantic reasoning over
actual data samples -- critical for L1 (obfuscated file names) and L2 (obfuscated
column names) workspaces.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
import json
import re
from typing import Any, Dict, List

from evaluation.llm_backend import LLMBackendSession
from evaluation.workspace_catalog import JoinEdge, WorkspaceCatalog, slugify, tokenize

from .types import ObservableSketch

_GROUNDING_SYSTEM = """You are a schema-matching expert for data analysis tasks.
Given a natural language question and a workspace of heterogeneous data sources,
identify which source and column best matches each required output and each filter.

CRITICAL RULES:
1. Look at SAMPLE VALUES carefully - column names may be obfuscated (e.g. col_3, fk_782).
2. For filters, the column's actual values must be compatible with the filter condition.
   Example: "bedrooms > 4" needs a column whose values look like bedroom counts (1,2,3,4,5,6), NOT an ID column (101,102,103...).
3. For outputs, the column's values should look like what the question asks for.
   Example: "facility_code" should match a column with values like "Gym", "Pool", "Cable TV".
4. If output and filter come from different sources, identify the join path between them.
5. Return your best recommendation with confidence scores.
6. If no reliable binding exists, say so explicitly instead of guessing.
7. Include why strong-looking alternatives are wrong when you are unsure.

Return valid JSON only."""


def _normalized_confidence(value: Any, default: float = 0.5) -> float:
    try:
        conf = float(value)
    except Exception:
        conf = default
    return max(0.0, min(conf, 1.0))


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return default


def _semantic_key(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _target_expects_numeric(text: str) -> bool:
    lower = _semantic_key(text)
    return any(token in lower for token in ["price", "amount", "cost", "score", "rating", "total", "number", "count", "value"])


def _target_expects_time(text: str) -> bool:
    lower = _semantic_key(text)
    return any(token in lower for token in ["date", "year", "month", "time", "day"])


def _is_obfuscated_name(name: str) -> bool:
    lower = str(name or "").strip().lower()
    return bool(
        re.fullmatch(r"(?:col|field|extra|dump|tmp|data|export)[_\-]?\d+", lower)
        or re.fullmatch(r"[kf]\d+", lower)
        or re.fullmatch(r"col_\d+", lower)
        or re.fullmatch(r"field_\d+", lower)
    )


def _workspace_obfuscation_metrics(catalog: WorkspaceCatalog) -> Dict[str, float]:
    file_like = 0
    obfuscated_file_like = 0
    column_count = 0
    obfuscated_columns = 0
    for source in catalog.sources.values():
        file_like += 1
        if _is_obfuscated_name(source.file_name.rsplit(".", 1)[0]) or _is_obfuscated_name(source.table_name or ""):
            obfuscated_file_like += 1
        for column_name in source.columns:
            column_count += 1
            if _is_obfuscated_name(column_name):
                obfuscated_columns += 1
    return {
        "file_ratio": (obfuscated_file_like / max(file_like, 1)),
        "column_ratio": (obfuscated_columns / max(column_count, 1)),
    }


def _compress_source_for_prompt(source, catalog: WorkspaceCatalog, max_cols: int = 12) -> Dict[str, Any]:
    """Compress a SourceProfile into a prompt-friendly dict."""
    # Prioritize informative columns: key_like first, then text_like, then measure_like
    cols = list(source.column_profiles.items())

    def _col_priority(item):
        _, p = item
        score = 0
        if p.key_like:
            score += 3
        if p.text_like:
            score += 2
        if p.measure_like:
            score += 2
        if p.time_like:
            score += 1
        return -score

    cols.sort(key=_col_priority)
    cols = cols[:max_cols]

    col_infos = []
    for col_name, profile in cols:
        # Truncate sample values for token budget
        samples = [str(v)[:30] for v in profile.sample_values[:5]]
        type_tags = []
        if profile.key_like:
            type_tags.append("key")
        if profile.text_like:
            type_tags.append("text")
        if profile.measure_like:
            type_tags.append("numeric/measure")
        if profile.time_like:
            type_tags.append("time/date")
        if profile.numeric_ratio >= 0.7 and not profile.measure_like and not profile.key_like:
            type_tags.append("numeric")
        if not type_tags:
            type_tags.append("other")

        col_infos.append({
            "col": col_name,
            "samples": samples,
            "type": ", ".join(type_tags),
            "unique_ratio": round(profile.unique_ratio, 2),
        })

    return {
        "source_id": source.source_id,
        "file": source.file_name,
        "rows": source.row_count,
        "role": source.role_hint,
        "columns": col_infos,
    }


def _compress_join_edges_for_prompt(catalog: WorkspaceCatalog, max_edges: int = 20) -> List[Dict[str, str]]:
    """Extract top join edges for the prompt."""
    edges = []
    seen = set()
    for source in catalog.sources.values():
        for edge in catalog.join_neighbors(source.source_id):
            eid = edge.edge_id
            if eid in seen:
                continue
            seen.add(eid)
            edges.append(edge)

    # Sort by overlap descending, take top
    edges.sort(key=lambda e: e.overlap, reverse=True)
    edges = edges[:max_edges]

    result = []
    for e in edges:
        result.append({
            "left": f"{e.left_source_id}.{e.left_column}",
            "right": f"{e.right_source_id}.{e.right_column}",
            "overlap": round(e.overlap, 3),
        })
    return result


def _prefilter_sources(
    catalog: WorkspaceCatalog,
    instruction: str,
    observable_sketch: ObservableSketch,
    max_sources: int = 10,
) -> List[str]:
    """When workspace is large, pre-filter to the most relevant sources using
    lightweight token overlap. This keeps the prompt within token budget."""
    if len(catalog.sources) <= max_sources:
        return list(catalog.sources.keys())

    question_tokens = set(tokenize(instruction))
    # Also add tokens from output slot labels and filter attributes
    for slot in observable_sketch.output_slots:
        question_tokens.update(tokenize(slot.label))
    for fh in observable_sketch.filter_hints:
        question_tokens.update(tokenize(str(fh.get("attribute", ""))))

    scored: List[tuple[float, str]] = []
    for source_id, source in catalog.sources.items():
        source_text = f"{source.file_name} {source.table_name or ''} {' '.join(source.columns)}"
        source_tokens = set(tokenize(source_text))
        # Add sample value tokens for L2 robustness
        for profile in source.column_profiles.values():
            for sv in profile.sample_values[:3]:
                source_tokens.update(tokenize(str(sv)))

        overlap = len(question_tokens & source_tokens)
        # Bonus for sources with join connectivity
        neighbor_count = len(catalog.join_neighbors(source_id))
        score = overlap + neighbor_count * 0.5
        scored.append((score, source_id))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [sid for _, sid in scored[:max_sources]]


def _normalize_binding_candidate(raw_item: Dict[str, Any], catalog: WorkspaceCatalog) -> Dict[str, Any] | None:
    if not isinstance(raw_item, dict):
        return None
    payload = raw_item.get("binding") if isinstance(raw_item.get("binding"), dict) else raw_item
    sid = str(payload.get("source_id", "")).strip()
    col = str(payload.get("column_name", "")).strip()
    if not sid or not col or sid not in catalog.sources:
        return None
    source = catalog.source(sid)
    resolved = _resolved_column_name(source, col)
    if resolved is None:
        return None
    return {
        "source_id": sid,
        "column_name": resolved,
        "confidence": _normalized_confidence(raw_item.get("confidence", payload.get("confidence", 0.5))),
        "reason": str(raw_item.get("reason", payload.get("reason", ""))),
    }


def _normalize_top_alternatives(items: Any, catalog: WorkspaceCatalog) -> List[Dict[str, Any]]:
    alternatives: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    if not isinstance(items, list):
        return alternatives
    for item in items:
        candidate = _normalize_binding_candidate(item, catalog)
        if candidate is None:
            continue
        key = (candidate["source_id"], candidate["column_name"])
        if key in seen:
            continue
        alternatives.append(candidate)
        seen.add(key)
    return alternatives


def _normalize_output_hypothesis(raw_item: Dict[str, Any], catalog: WorkspaceCatalog) -> Dict[str, Any] | None:
    slot_label = str(raw_item.get("slot_label", raw_item.get("label", ""))).strip()
    if not slot_label:
        return None
    binding = _normalize_binding_candidate(raw_item, catalog)
    top_alternatives = _normalize_top_alternatives(raw_item.get("top_alternatives", []), catalog)
    if binding is not None:
        primary_key = (binding["source_id"], binding["column_name"])
        top_alternatives = [
            item for item in top_alternatives
            if (item["source_id"], item["column_name"]) != primary_key
        ]
    confidence = _normalized_confidence(raw_item.get("confidence", binding["confidence"] if binding is not None else 0.0), default=0.0)
    is_uncertain = _coerce_bool(raw_item.get("is_uncertain"), default=(binding is None or confidence < 0.5))
    is_dummy_likely = _coerce_bool(raw_item.get("is_dummy_likely"), default=False)
    no_reliable_binding = _coerce_bool(raw_item.get("no_reliable_binding"), default=(binding is None and not top_alternatives))
    return {
        "slot_label": slot_label,
        "binding": binding,
        "confidence": confidence,
        "is_uncertain": is_uncertain,
        "is_dummy_likely": is_dummy_likely,
        "no_reliable_binding": no_reliable_binding,
        "why_not": str(raw_item.get("why_not", "")),
        "confidence_reason": str(raw_item.get("confidence_reason", "")),
        "top_alternatives": top_alternatives,
    }


def _normalize_filter_hypothesis(raw_item: Dict[str, Any], catalog: WorkspaceCatalog) -> Dict[str, Any] | None:
    filter_attribute = str(raw_item.get("filter_attribute", raw_item.get("attribute", ""))).strip()
    binding = _normalize_binding_candidate(raw_item, catalog)
    top_alternatives = _normalize_top_alternatives(raw_item.get("top_alternatives", []), catalog)
    if not filter_attribute and binding is None and not top_alternatives:
        return None
    if binding is not None:
        primary_key = (binding["source_id"], binding["column_name"])
        top_alternatives = [
            item for item in top_alternatives
            if (item["source_id"], item["column_name"]) != primary_key
        ]
    confidence = _normalized_confidence(raw_item.get("confidence", binding["confidence"] if binding is not None else 0.0), default=0.0)
    is_uncertain = _coerce_bool(raw_item.get("is_uncertain"), default=(binding is None or confidence < 0.5))
    is_dummy_likely = _coerce_bool(raw_item.get("is_dummy_likely"), default=False)
    no_reliable_binding = _coerce_bool(raw_item.get("no_reliable_binding"), default=(binding is None and not top_alternatives))
    return {
        "filter_attribute": filter_attribute,
        "binding": binding,
        "confidence": confidence,
        "is_uncertain": is_uncertain,
        "is_dummy_likely": is_dummy_likely,
        "no_reliable_binding": no_reliable_binding,
        "why_not": str(raw_item.get("why_not", "")),
        "confidence_reason": str(raw_item.get("confidence_reason", "")),
        "top_alternatives": top_alternatives,
    }


def build_llm_grounding(
    instruction: str,
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
    session: LLMBackendSession | None,
) -> Dict[str, Any]:
    """Ask the LLM to ground output slots and filter hints to specific
    (source_id, column_name) pairs by examining workspace schema and sample values.

    Returns a dict with keys:
    - output_bindings: List[{slot_label, source_id, column_name, confidence, reason}]
    - filter_bindings: List[{filter_attribute, source_id, column_name, confidence, reason}]
    - output_hypotheses: List[{slot_label, binding, confidence, is_uncertain, is_dummy_likely, why_not, top_alternatives}]
    - filter_hypotheses: List[{filter_attribute, binding, confidence, is_uncertain, is_dummy_likely, why_not, top_alternatives}]
    - suggested_joins: List[{from_source, to_source, reason}]
    - query_family: str
    - query_family_confidence: float
    - reasoning: str

    Falls back to empty dict if LLM is unavailable.
    """
    empty_result: Dict[str, Any] = {
        "output_bindings": [],
        "filter_bindings": [],
        "output_hypotheses": [],
        "filter_hypotheses": [],
        "suggested_joins": [],
        "query_family": None,
        "query_family_confidence": 0.0,
        "reasoning": "llm_unavailable",
    }

    if session is None or session.remaining_calls <= 0:
        return empty_result

    # Pre-filter sources for large workspaces
    relevant_source_ids = _prefilter_sources(catalog, instruction, observable_sketch, max_sources=10)

    # Build workspace description
    source_descriptions = []
    for sid in relevant_source_ids:
        source = catalog.source(sid)
        source_descriptions.append(_compress_source_for_prompt(source, catalog))

    join_edges = _compress_join_edges_for_prompt(catalog, max_edges=15)

    # Build query description
    output_slots = [{"label": s.label, "role": s.role} for s in observable_sketch.output_slots]
    filter_hints = list(observable_sketch.filter_hints)
    operator_hints = list(observable_sketch.operator_hints)
    measure_hints = list(observable_sketch.measure_hints)

    user_prompt = (
        f"Question: {instruction}\n\n"
        f"Required output columns: {json.dumps(output_slots, ensure_ascii=False)}\n"
    )
    if filter_hints:
        user_prompt += f"Detected filters: {json.dumps(filter_hints, ensure_ascii=False)}\n"
    if operator_hints:
        user_prompt += f"Aggregation/operator hints: {operator_hints}\n"
    if measure_hints:
        user_prompt += f"Measure hints: {measure_hints}\n"

    user_prompt += (
        f"\nWorkspace sources ({len(source_descriptions)} sources):\n"
        f"{json.dumps(source_descriptions, ensure_ascii=False, indent=1)}\n\n"
    )
    if join_edges:
        user_prompt += (
            f"Known join edges:\n"
            f"{json.dumps(join_edges, ensure_ascii=False, indent=1)}\n\n"
        )

    user_prompt += (
        "For each required output column, identify the BEST (source_id, column_name) match, but do not guess if the evidence is weak.\n"
        "For each filter, identify which source and column the filter should apply to.\n"
        "If output and filter are in different sources, suggest the join path.\n\n"
        "Return JSON with keys: output_hypotheses, filter_hypotheses, suggested_joins, query_family, query_family_confidence, reasoning.\n"
        "Each output_hypothesis item must include: slot_label, source_id, column_name, confidence, is_uncertain, is_dummy_likely, why_not, top_alternatives.\n"
        "Each filter_hypothesis item must include: filter_attribute, source_id, column_name, confidence, is_uncertain, is_dummy_likely, why_not, top_alternatives.\n"
        "If no reliable binding exists, set source_id/column_name to null or omit them, set no_reliable_binding=true, and explain why_not.\n"
        "query_family should be one of: direct_join, filter_join, aggregation_join, count_star_support, direct_aggregation"
    )

    try:
        raw = session.chat_json(_GROUNDING_SYSTEM, user_prompt, cache_namespace="llm_pre_grounding")
    except Exception:
        return empty_result

    # Validate and normalize output
    result: Dict[str, Any] = {
        "output_bindings": [],
        "filter_bindings": [],
        "output_hypotheses": [],
        "filter_hypotheses": [],
        "suggested_joins": [],
        "query_family": None,
        "query_family_confidence": 0.0,
        "reasoning": str(raw.get("reasoning", "")),
    }

    raw_output_hypotheses = raw.get("output_hypotheses", [])
    if not isinstance(raw_output_hypotheses, list) or not raw_output_hypotheses:
        raw_output_hypotheses = raw.get("output_bindings", [])
    for item in raw_output_hypotheses:
        if not isinstance(item, dict):
            continue
        hypothesis = _normalize_output_hypothesis(item, catalog)
        if hypothesis is None:
            continue
        result["output_hypotheses"].append(hypothesis)
        if hypothesis["binding"] is not None:
            result["output_bindings"].append(
                {
                    "slot_label": hypothesis["slot_label"],
                    "source_id": hypothesis["binding"]["source_id"],
                    "column_name": hypothesis["binding"]["column_name"],
                    "confidence": hypothesis["confidence"],
                    "reason": hypothesis["binding"].get("reason", ""),
                    "is_uncertain": hypothesis["is_uncertain"],
                    "is_dummy_likely": hypothesis["is_dummy_likely"],
                    "why_not": hypothesis["why_not"],
                    "top_alternatives": list(hypothesis["top_alternatives"]),
                    "confidence_reason": hypothesis["confidence_reason"],
                    "no_reliable_binding": hypothesis["no_reliable_binding"],
                }
            )

    raw_filter_hypotheses = raw.get("filter_hypotheses", [])
    if not isinstance(raw_filter_hypotheses, list) or not raw_filter_hypotheses:
        raw_filter_hypotheses = raw.get("filter_bindings", [])
    for item in raw_filter_hypotheses:
        if not isinstance(item, dict):
            continue
        hypothesis = _normalize_filter_hypothesis(item, catalog)
        if hypothesis is None:
            continue
        result["filter_hypotheses"].append(hypothesis)
        if hypothesis["binding"] is not None:
            result["filter_bindings"].append(
                {
                    "filter_attribute": hypothesis["filter_attribute"],
                    "source_id": hypothesis["binding"]["source_id"],
                    "column_name": hypothesis["binding"]["column_name"],
                    "confidence": hypothesis["confidence"],
                    "reason": hypothesis["binding"].get("reason", ""),
                    "is_uncertain": hypothesis["is_uncertain"],
                    "is_dummy_likely": hypothesis["is_dummy_likely"],
                    "why_not": hypothesis["why_not"],
                    "top_alternatives": list(hypothesis["top_alternatives"]),
                    "confidence_reason": hypothesis["confidence_reason"],
                    "no_reliable_binding": hypothesis["no_reliable_binding"],
                }
            )

    for item in raw.get("suggested_joins", []):
        if isinstance(item, dict):
            result["suggested_joins"].append(item)

    qf = str(raw.get("query_family", "")).strip().lower()
    valid_families = {"direct_join", "filter_join", "aggregation_join", "count_star_support", "direct_aggregation", "support_join"}
    if qf in valid_families:
        result["query_family"] = qf
        result["query_family_confidence"] = _normalized_confidence(raw.get("query_family_confidence", 0.5))

    return result


def is_overlay_edge(edge_id: str) -> bool:
    return str(edge_id).startswith("llm_overlay__")


def grounding_to_binding_set(grounding: Dict[str, Any]) -> tuple[set[tuple[str, str]], set[tuple[str, str]], str | None]:
    """Convert LLM grounding result into sets for fast lookup in scoring functions.

    Returns:
    - output_binding_set: set of (source_id, column_name) tuples for output
    - filter_binding_set: set of (source_id, column_name) tuples for filter
    - query_family: suggested family or None
    """
    output_set: set[tuple[str, str]] = set()
    for item in grounding.get("output_bindings", []):
        sid = item.get("source_id", "")
        col = item.get("column_name", "")
        if sid and col:
            output_set.add((sid, col))

    filter_set: set[tuple[str, str]] = set()
    for item in grounding.get("filter_bindings", []):
        sid = item.get("source_id", "")
        col = item.get("column_name", "")
        if sid and col:
            filter_set.add((sid, col))

    return output_set, filter_set, grounding.get("query_family")


def grounding_to_search_hints(grounding: Dict[str, Any]) -> Dict[str, Any]:
    output_priors_by_slot: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] = {}
    filter_priors_by_attribute: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] = {}

    for item in grounding.get("output_hypotheses", []):
        if not isinstance(item, dict):
            continue
        slot_label = str(item.get("slot_label", "")).strip()
        if not slot_label:
            continue
        priors = output_priors_by_slot.setdefault(slot_label, {})
        candidates: List[Dict[str, Any]] = []
        binding = item.get("binding")
        if isinstance(binding, dict):
            candidates.append(
                {
                    **binding,
                    "raw_confidence": _normalized_confidence(item.get("confidence", binding.get("confidence", 0.5))),
                    "confidence": _normalized_confidence(item.get("confidence", binding.get("confidence", 0.5))),
                    "is_uncertain": _coerce_bool(item.get("is_uncertain"), default=False),
                    "is_dummy_likely": _coerce_bool(item.get("is_dummy_likely"), default=False),
                    "why_not": str(item.get("why_not", "")),
                    "confidence_reason": str(item.get("confidence_reason", "")),
                    "no_reliable_binding": _coerce_bool(item.get("no_reliable_binding"), default=False),
                    "rank": 0,
                    "is_primary": True,
                    "cross_source_join_risk": False,
                    "calibration_rules": [],
                }
            )
        for rank, alt in enumerate(item.get("top_alternatives", []), start=1):
            if not isinstance(alt, dict):
                continue
            candidates.append(
                {
                    **alt,
                    "raw_confidence": _normalized_confidence(alt.get("confidence", 0.3), default=0.3),
                    "confidence": _normalized_confidence(alt.get("confidence", 0.3), default=0.3),
                    "is_uncertain": True,
                    "is_dummy_likely": False,
                    "why_not": str(item.get("why_not", "")),
                    "confidence_reason": str(item.get("confidence_reason", "")),
                    "no_reliable_binding": _coerce_bool(item.get("no_reliable_binding"), default=False),
                    "rank": rank,
                    "is_primary": False,
                    "cross_source_join_risk": False,
                    "calibration_rules": [],
                }
            )
        for candidate in candidates:
            key = (str(candidate.get("source_id", "")), str(candidate.get("column_name", "")))
            if not all(key):
                continue
            previous = priors.get(key)
            if previous is None or float(candidate["confidence"]) > float(previous["confidence"]):
                priors[key] = candidate

    for item in grounding.get("filter_hypotheses", []):
        if not isinstance(item, dict):
            continue
        filter_attribute = str(item.get("filter_attribute", "")).strip() or "*"
        priors = filter_priors_by_attribute.setdefault(filter_attribute, {})
        candidates: List[Dict[str, Any]] = []
        binding = item.get("binding")
        if isinstance(binding, dict):
            candidates.append(
                {
                    **binding,
                    "raw_confidence": _normalized_confidence(item.get("confidence", binding.get("confidence", 0.5))),
                    "confidence": _normalized_confidence(item.get("confidence", binding.get("confidence", 0.5))),
                    "is_uncertain": _coerce_bool(item.get("is_uncertain"), default=False),
                    "is_dummy_likely": _coerce_bool(item.get("is_dummy_likely"), default=False),
                    "why_not": str(item.get("why_not", "")),
                    "confidence_reason": str(item.get("confidence_reason", "")),
                    "no_reliable_binding": _coerce_bool(item.get("no_reliable_binding"), default=False),
                    "rank": 0,
                    "is_primary": True,
                    "cross_source_join_risk": False,
                    "calibration_rules": [],
                }
            )
        for rank, alt in enumerate(item.get("top_alternatives", []), start=1):
            if not isinstance(alt, dict):
                continue
            candidates.append(
                {
                    **alt,
                    "raw_confidence": _normalized_confidence(alt.get("confidence", 0.3), default=0.3),
                    "confidence": _normalized_confidence(alt.get("confidence", 0.3), default=0.3),
                    "is_uncertain": True,
                    "is_dummy_likely": False,
                    "why_not": str(item.get("why_not", "")),
                    "confidence_reason": str(item.get("confidence_reason", "")),
                    "no_reliable_binding": _coerce_bool(item.get("no_reliable_binding"), default=False),
                    "rank": rank,
                    "is_primary": False,
                    "cross_source_join_risk": False,
                    "calibration_rules": [],
                }
            )
        for candidate in candidates:
            key = (str(candidate.get("source_id", "")), str(candidate.get("column_name", "")))
            if not all(key):
                continue
            previous = priors.get(key)
            if previous is None or float(candidate["confidence"]) > float(previous["confidence"]):
                priors[key] = candidate

    # Backfill legacy-only payloads so search can still consume priors.
    if not output_priors_by_slot:
        for item in grounding.get("output_bindings", []):
            if not isinstance(item, dict):
                continue
            slot_label = str(item.get("slot_label", item.get("label", ""))).strip()
            sid = str(item.get("source_id", "")).strip()
            col = str(item.get("column_name", "")).strip()
            if not slot_label or not sid or not col:
                continue
            output_priors_by_slot.setdefault(slot_label, {})[(sid, col)] = {
                "source_id": sid,
                "column_name": col,
                "raw_confidence": _normalized_confidence(item.get("confidence", 0.5)),
                "confidence": _normalized_confidence(item.get("confidence", 0.5)),
                "is_uncertain": _coerce_bool(item.get("is_uncertain"), default=_normalized_confidence(item.get("confidence", 0.5)) < 0.5),
                "is_dummy_likely": _coerce_bool(item.get("is_dummy_likely"), default=False),
                "why_not": str(item.get("why_not", "")),
                "confidence_reason": str(item.get("confidence_reason", "")),
                "no_reliable_binding": _coerce_bool(item.get("no_reliable_binding"), default=False),
                "rank": 0,
                "is_primary": True,
                "cross_source_join_risk": False,
                "calibration_rules": [],
            }
    if not filter_priors_by_attribute:
        for item in grounding.get("filter_bindings", []):
            if not isinstance(item, dict):
                continue
            filter_attribute = str(item.get("filter_attribute", item.get("attribute", ""))).strip() or "*"
            sid = str(item.get("source_id", "")).strip()
            col = str(item.get("column_name", "")).strip()
            if not sid or not col:
                continue
            filter_priors_by_attribute.setdefault(filter_attribute, {})[(sid, col)] = {
                "source_id": sid,
                "column_name": col,
                "raw_confidence": _normalized_confidence(item.get("confidence", 0.5)),
                "confidence": _normalized_confidence(item.get("confidence", 0.5)),
                "is_uncertain": _coerce_bool(item.get("is_uncertain"), default=_normalized_confidence(item.get("confidence", 0.5)) < 0.5),
                "is_dummy_likely": _coerce_bool(item.get("is_dummy_likely"), default=False),
                "why_not": str(item.get("why_not", "")),
                "confidence_reason": str(item.get("confidence_reason", "")),
                "no_reliable_binding": _coerce_bool(item.get("no_reliable_binding"), default=False),
                "rank": 0,
                "is_primary": True,
                "cross_source_join_risk": False,
                "calibration_rules": [],
            }

    primary_output_sources = {
        candidate["source_id"]
        for priors in output_priors_by_slot.values()
        for candidate in priors.values()
        if candidate.get("is_primary") and not candidate.get("is_uncertain") and not candidate.get("is_dummy_likely") and float(candidate.get("confidence", 0.0)) >= 0.55
    }
    return {
        "output_priors_by_slot": output_priors_by_slot,
        "filter_priors_by_attribute": filter_priors_by_attribute,
        "order_priors_by_target": {},
        "query_family": grounding.get("query_family"),
        "query_family_confidence": _normalized_confidence(grounding.get("query_family_confidence", 0.0), default=0.0),
        "strong_multi_source_output": len(primary_output_sources) > 1,
        "cross_source_join_risk": False,
        "calibration_rules_fired": [],
    }


def _record_rule(hints: Dict[str, Any], candidate: Dict[str, Any] | None, rule: str) -> None:
    if rule not in hints["calibration_rules_fired"]:
        hints["calibration_rules_fired"].append(rule)
    if candidate is None:
        return
    rules = candidate.setdefault("calibration_rules", [])
    if rule not in rules:
        rules.append(rule)


def _candidate_profile(catalog: WorkspaceCatalog, candidate: Dict[str, Any]) -> tuple[Any, Any] | tuple[None, None]:
    source_id = str(candidate.get("source_id", "")).strip()
    column_name = str(candidate.get("column_name", "")).strip()
    if not source_id or not column_name or source_id not in catalog.sources:
        return None, None
    source = catalog.source(source_id)
    profile = source.column_profiles.get(column_name)
    return source, profile


def _cap_candidate_confidence(
    hints: Dict[str, Any],
    candidate: Dict[str, Any],
    rule: str,
    *,
    cap: float | None = None,
    force_uncertain: bool = False,
    force_dummy: bool = False,
    join_risk: bool = False,
) -> None:
    before = float(candidate.get("confidence", 0.0))
    if cap is not None:
        candidate["confidence"] = min(before, cap)
    if force_uncertain:
        candidate["is_uncertain"] = True
    if force_dummy:
        candidate["is_dummy_likely"] = True
    if join_risk:
        candidate["cross_source_join_risk"] = True
        hints["cross_source_join_risk"] = True
    _record_rule(hints, candidate, rule)


def _has_join_evidence(
    catalog: WorkspaceCatalog,
    left_source_id: str,
    right_source_id: str,
    suggested_join_specs: List[Dict[str, Any]],
    *,
    max_hops: int = 2,
) -> bool:
    if not left_source_id or not right_source_id or left_source_id == right_source_id:
        return True
    if catalog.find_best_path(left_source_id, right_source_id, max_hops=max_hops):
        return True
    wanted = frozenset((left_source_id, right_source_id))
    for spec in suggested_join_specs:
        if frozenset((str(spec.get("from_source", "")).strip(), str(spec.get("to_source", "")).strip())) == wanted:
            return True
    return False


def _slot_primary_source(slot_priors: Dict[tuple[str, str], Dict[str, Any]]) -> str | None:
    primary = next(
        (
            candidate
            for candidate in slot_priors.values()
            if candidate.get("is_primary")
        ),
        None,
    )
    if primary is None:
        return None
    return str(primary.get("source_id", "")).strip() or None


def _best_output_anchor_source(output_priors_by_slot: Dict[str, Dict[tuple[str, str], Dict[str, Any]]]) -> str | None:
    source_scores: Dict[str, float] = {}
    for priors in output_priors_by_slot.values():
        for candidate in priors.values():
            if not candidate.get("is_primary"):
                continue
            if candidate.get("is_dummy_likely"):
                continue
            source_id = str(candidate.get("source_id", "")).strip()
            if not source_id:
                continue
            source_scores[source_id] = source_scores.get(source_id, 0.0) + float(candidate.get("confidence", 0.0))
    if not source_scores:
        return None
    return max(source_scores.items(), key=lambda item: item[1])[0]


def _has_usable_primary(priors: Dict[tuple[str, str], Dict[str, Any]]) -> bool:
    return any(
        candidate.get("is_primary")
        and not candidate.get("is_dummy_likely")
        and float(candidate.get("confidence", 0.0)) > 0.0
        for candidate in priors.values()
    )


def _has_strong_primary(priors: Dict[tuple[str, str], Dict[str, Any]]) -> bool:
    return any(
        candidate.get("is_primary")
        and not candidate.get("is_uncertain")
        and not candidate.get("is_dummy_likely")
        and float(candidate.get("confidence", 0.0)) >= 0.55
        for candidate in priors.values()
    )


def _question_token_set(instruction: str, extra: str = "") -> set[str]:
    tokens = set(tokenize(instruction))
    if extra:
        tokens.update(tokenize(extra))
    return tokens


def _sample_token_overlap(tokens: set[str], sample_values: List[str]) -> float:
    if not tokens:
        return 0.0
    sample_tokens: set[str] = set()
    for value in sample_values[:8]:
        sample_tokens.update(tokenize(str(value)))
    if not sample_tokens:
        return 0.0
    return len(tokens & sample_tokens) / max(len(tokens), 1)


def _fallback_confidence(score: float, *, floor: float = 0.22, ceiling: float = 0.72) -> float:
    return max(floor, min(ceiling, floor + (score * 0.06)))


def _candidate_dict_from_profile(
    source_id: str,
    column_name: str,
    score: float,
    reason: str,
    *,
    derived_from: str,
    rank: int,
    primary: bool,
    uncertain: bool,
) -> Dict[str, Any]:
    confidence = _fallback_confidence(score)
    return {
        "source_id": source_id,
        "column_name": column_name,
        "raw_confidence": confidence,
        "confidence": confidence,
        "is_uncertain": uncertain,
        "is_dummy_likely": False,
        "why_not": reason,
        "confidence_reason": derived_from,
        "no_reliable_binding": False,
        "rank": rank,
        "is_primary": primary,
        "cross_source_join_risk": False,
        "calibration_rules": [],
        "derived_from": derived_from,
    }


def _score_profile_output_candidate(
    slot_label: str,
    slot_role: str,
    source,
    column_name: str,
    instruction: str,
) -> tuple[float, str]:
    profile = source.column_profiles[column_name]
    tokens = _question_token_set(instruction, slot_label)
    score = 0.0
    if slot_role in {"entity", "attribute", "description", "status", "location"}:
        if profile.text_like:
            score += 4.0
        if source.role_hint in {"dimension", "unknown"}:
            score += 2.0
        if profile.unique_ratio >= 0.15:
            score += 1.5
        if profile.key_like:
            score -= 3.0
        if profile.numeric_ratio >= 0.7 and slot_role != "location":
            score -= 4.0
    elif slot_role == "measure":
        if profile.measure_like or profile.numeric_ratio >= 0.7:
            score += 5.0
        if profile.key_like:
            score -= 4.0
        if profile.time_like:
            score -= 2.0
    elif slot_role == "time":
        if profile.time_like:
            score += 5.0
        else:
            score -= 4.0
    elif slot_role in {"key", "code"} and profile.key_like:
        score += 4.0
    score += 4.0 * _sample_token_overlap(tokens, profile.sample_values)
    score += len(tokens & set(tokenize(column_name))) * 0.4
    return score, "profile_fallback_output"


def _score_profile_filter_candidate(
    filter_attribute: str,
    filter_hint: Dict[str, Any],
    source,
    column_name: str,
    instruction: str,
) -> tuple[float, str]:
    profile = source.column_profiles[column_name]
    score = 0.0
    tokens = _question_token_set(instruction, filter_attribute)
    raw_value = filter_hint.get("value")
    if isinstance(raw_value, str):
        try:
            raw_value = float(raw_value) if "." in raw_value else int(raw_value)
        except Exception:
            pass
    if isinstance(raw_value, (int, float)):
        if profile.measure_like or profile.numeric_ratio >= 0.6:
            score += 5.0
        elif profile.time_like:
            score -= 3.0
        else:
            score -= 5.0
    else:
        if profile.text_like:
            score += 3.5
        if profile.numeric_ratio >= 0.6:
            score -= 2.5
    if profile.key_like and profile.unique_ratio > 0.9:
        score -= 3.5
    score += 3.5 * _sample_token_overlap(tokens, profile.sample_values)
    score += len(tokens & set(tokenize(column_name))) * 0.4
    return score, "profile_fallback_filter"


def _score_profile_order_candidate(
    target: str,
    source,
    column_name: str,
    instruction: str,
) -> tuple[float, str]:
    profile = source.column_profiles[column_name]
    tokens = _question_token_set(instruction, target)
    score = 0.0
    if _target_expects_numeric(target):
        if profile.measure_like or profile.numeric_ratio >= 0.6:
            score += 5.0
        elif profile.time_like:
            score -= 3.0
        else:
            score -= 5.0
    elif _target_expects_time(target):
        if profile.time_like:
            score += 5.0
        else:
            score -= 5.0
    elif profile.text_like:
        score += 2.0
    if source.role_hint == "fact":
        score += 1.0
    if profile.key_like and not any(token in _semantic_key(target) for token in ["id", "key", "code"]):
        score -= 3.0
    score += 3.0 * _sample_token_overlap(tokens, profile.sample_values)
    score += len(tokens & set(tokenize(column_name))) * 0.4
    return score, "profile_fallback_order"


def _inject_profile_fallback_output_priors(
    hints: Dict[str, Any],
    catalog: WorkspaceCatalog,
    observable_sketch: ObservableSketch,
    instruction: str,
) -> None:
    injected = hints.setdefault("fallback_injected", {"output_slots": [], "filter_attributes": [], "order_targets": []})
    for slot in observable_sketch.output_slots:
        priors = hints.get("output_priors_by_slot", {}).setdefault(slot.label, {})
        if _has_strong_primary(priors):
            continue
        ranked: List[tuple[float, Dict[str, Any]]] = []
        for source in catalog.sources.values():
            for column_name in source.columns:
                key = (source.source_id, column_name)
                if key in priors:
                    continue
                score, reason = _score_profile_output_candidate(slot.label, slot.role, source, column_name, instruction)
                if score <= 0.5:
                    continue
                ranked.append(
                    (
                        score,
                        _candidate_dict_from_profile(
                            source.source_id,
                            column_name,
                            score,
                            reason,
                            derived_from="profile_fallback",
                            rank=len(priors) + len(ranked),
                            primary=False,
                            uncertain=True,
                        ),
                    )
                )
        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked:
            continue
        promoted = not _has_usable_primary(priors)
        for idx, (_, candidate) in enumerate(ranked[:3]):
            if idx == 0 and promoted:
                for existing in priors.values():
                    existing["is_primary"] = False
                candidate["is_primary"] = True
                candidate["is_uncertain"] = float(candidate["confidence"]) < 0.58
            priors[(candidate["source_id"], candidate["column_name"])] = candidate
        if slot.label not in injected["output_slots"]:
            injected["output_slots"].append(slot.label)
        _record_rule(hints, None, "rule_profile_fallback_output")


def _inject_profile_fallback_filter_priors(
    hints: Dict[str, Any],
    catalog: WorkspaceCatalog,
    observable_sketch: ObservableSketch,
    instruction: str,
) -> None:
    injected = hints.setdefault("fallback_injected", {"output_slots": [], "filter_attributes": [], "order_targets": []})
    for filter_hint in observable_sketch.filter_hints:
        filter_attribute = str(filter_hint.get("attribute", "")).strip() or "*"
        priors = hints.get("filter_priors_by_attribute", {}).setdefault(filter_attribute, {})
        if _has_strong_primary(priors):
            continue
        ranked: List[tuple[float, Dict[str, Any]]] = []
        for source in catalog.sources.values():
            for column_name in source.columns:
                key = (source.source_id, column_name)
                if key in priors:
                    continue
                score, reason = _score_profile_filter_candidate(filter_attribute, filter_hint, source, column_name, instruction)
                if score <= 0.5:
                    continue
                ranked.append(
                    (
                        score,
                        _candidate_dict_from_profile(
                            source.source_id,
                            column_name,
                            score,
                            reason,
                            derived_from="profile_fallback",
                            rank=len(priors) + len(ranked),
                            primary=False,
                            uncertain=True,
                        ),
                    )
                )
        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked:
            continue
        promoted = not _has_usable_primary(priors)
        for idx, (_, candidate) in enumerate(ranked[:3]):
            if idx == 0 and promoted:
                for existing in priors.values():
                    existing["is_primary"] = False
                candidate["is_primary"] = True
                candidate["is_uncertain"] = float(candidate["confidence"]) < 0.58
            priors[(candidate["source_id"], candidate["column_name"])] = candidate
        if filter_attribute not in injected["filter_attributes"]:
            injected["filter_attributes"].append(filter_attribute)
        _record_rule(hints, None, "rule_profile_fallback_filter")


def _inject_profile_fallback_order_priors(
    hints: Dict[str, Any],
    catalog: WorkspaceCatalog,
    observable_sketch: ObservableSketch,
    instruction: str,
) -> None:
    injected = hints.setdefault("fallback_injected", {"output_slots": [], "filter_attributes": [], "order_targets": []})
    order_hint = observable_sketch.order_hint or {}
    raw_target = str(order_hint.get("target", "")).strip()
    if not raw_target:
        return
    target_key = _semantic_key(raw_target)
    priors = hints.get("order_priors_by_target", {}).setdefault(target_key, {})
    if _has_strong_primary(priors):
        return
    ranked: List[tuple[float, Dict[str, Any]]] = []
    for source in catalog.sources.values():
        for column_name in source.columns:
            key = (source.source_id, column_name)
            if key in priors:
                continue
            score, reason = _score_profile_order_candidate(raw_target, source, column_name, instruction)
            if score <= 1.0:
                continue
            ranked.append(
                (
                    score,
                    _candidate_dict_from_profile(
                        source.source_id,
                        column_name,
                        score,
                        reason,
                        derived_from="profile_fallback",
                        rank=len(priors) + len(ranked),
                        primary=False,
                        uncertain=True,
                    ),
                )
            )
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return
    promoted = not _has_usable_primary(priors)
    for idx, (_, candidate) in enumerate(ranked[:3]):
        if idx == 0 and promoted:
            for existing in priors.values():
                existing["is_primary"] = False
            candidate["is_primary"] = True
            candidate["is_uncertain"] = float(candidate["confidence"]) < 0.58
        priors[(candidate["source_id"], candidate["column_name"])] = candidate
    if target_key not in injected["order_targets"]:
        injected["order_targets"].append(target_key)
    _record_rule(hints, None, "rule_profile_fallback_order")


def _derive_order_priors(
    hints: Dict[str, Any],
    observable_sketch: ObservableSketch,
) -> Dict[str, Dict[tuple[str, str], Dict[str, Any]]]:
    order_priors_by_target: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] = {}
    order_hint = observable_sketch.order_hint or {}
    raw_target = str(order_hint.get("target", "")).strip()
    if not raw_target:
        return order_priors_by_target
    target_key = _semantic_key(raw_target)
    target_tokens = set(target_key.split())
    derived: Dict[tuple[str, str], Dict[str, Any]] = {}
    for filter_attribute, priors in hints.get("filter_priors_by_attribute", {}).items():
        filter_key = _semantic_key(filter_attribute)
        filter_tokens = set(filter_key.split())
        if filter_key != target_key and not (target_tokens & filter_tokens):
            continue
        for key, candidate in priors.items():
            cloned = copy.deepcopy(candidate)
            cloned["derived_from"] = "filter_prior"
            derived[key] = cloned
    if derived:
        order_priors_by_target[target_key] = derived
    return order_priors_by_target


def _apply_duplicate_slot_collapse(
    hints: Dict[str, Any],
    output_priors_by_slot: Dict[str, Dict[tuple[str, str], Dict[str, Any]]],
) -> None:
    primary_by_key: Dict[tuple[str, str], List[tuple[str, Dict[str, Any]]]] = {}
    for slot_label, priors in output_priors_by_slot.items():
        primary = next((candidate for candidate in priors.values() if candidate.get("is_primary")), None)
        if primary is None:
            continue
        key = (str(primary.get("source_id", "")), str(primary.get("column_name", "")))
        if not all(key):
            continue
        primary_by_key.setdefault(key, []).append((slot_label, primary))

    for _, entries in primary_by_key.items():
        if len(entries) <= 1:
            continue
        winner_slot, winner_candidate = max(entries, key=lambda item: float(item[1].get("confidence", 0.0)))
        for slot_label, candidate in entries:
            if slot_label == winner_slot and candidate is winner_candidate:
                continue
            _cap_candidate_confidence(
                hints,
                candidate,
                "rule_duplicate_slot_collapse",
                cap=0.25,
                force_uncertain=True,
                force_dummy=True,
            )


def _apply_output_filter_profile_rules(
    hints: Dict[str, Any],
    priors_by_group: Dict[str, Dict[tuple[str, str], Dict[str, Any]]],
    catalog: WorkspaceCatalog,
    *,
    is_filter: bool,
) -> None:
    for group_name, priors in priors_by_group.items():
        for candidate in priors.values():
            _, profile = _candidate_profile(catalog, candidate)
            if profile is None:
                continue
            if is_filter:
                expects_numeric = _target_expects_numeric(group_name)
                expects_time = _target_expects_time(group_name)
                if (profile.key_like or profile.unique_ratio > 0.9) and not (
                    (expects_numeric and (profile.measure_like or profile.numeric_ratio >= 0.6))
                    or (expects_time and profile.time_like)
                ):
                    _cap_candidate_confidence(
                        hints,
                        candidate,
                        "rule_filter_high_unique_or_key_like",
                        cap=0.25,
                        force_uncertain=True,
                        force_dummy=True,
                    )
                elif expects_numeric and not (profile.measure_like or profile.numeric_ratio >= 0.6):
                    _cap_candidate_confidence(
                        hints,
                        candidate,
                        "rule_filter_value_shape_contradiction",
                        cap=0.35,
                        force_uncertain=True,
                        force_dummy=profile.text_like and not profile.time_like,
                    )
                elif expects_time and not profile.time_like:
                    _cap_candidate_confidence(
                        hints,
                        candidate,
                        "rule_filter_value_shape_contradiction",
                        cap=0.35,
                        force_uncertain=True,
                    )
            else:
                expects_numeric = _target_expects_numeric(group_name)
                expects_time = _target_expects_time(group_name)
                if expects_numeric and not (profile.measure_like or profile.numeric_ratio >= 0.6):
                    _cap_candidate_confidence(
                        hints,
                        candidate,
                        "rule_output_value_shape_contradiction",
                        cap=0.35,
                        force_uncertain=True,
                        force_dummy=profile.text_like and not profile.time_like,
                    )
                elif expects_time and not profile.time_like:
                    _cap_candidate_confidence(
                        hints,
                        candidate,
                        "rule_output_value_shape_contradiction",
                        cap=0.35,
                        force_uncertain=True,
                    )


def _apply_weak_justification_rule(
    hints: Dict[str, Any],
    priors_by_group: Dict[str, Dict[tuple[str, str], Dict[str, Any]]],
    catalog: WorkspaceCatalog,
) -> None:
    for group_name, priors in priors_by_group.items():
        for candidate in priors.values():
            source, profile = _candidate_profile(catalog, candidate)
            if source is None or profile is None:
                continue
            confidence = float(candidate.get("confidence", 0.0))
            if confidence <= 0.6:
                continue
            why_not = str(candidate.get("why_not", "")).strip()
            confidence_reason = str(candidate.get("confidence_reason", "")).strip()
            weak_justification = len(why_not) < 12 and len(confidence_reason) < 12
            weak_shape = (
                _semantic_key(group_name) not in _semantic_key(candidate.get("column_name", ""))
                and not profile.measure_like
                and not profile.time_like
                and not profile.text_like
            )
            if weak_justification and (_is_obfuscated_name(candidate.get("column_name", "")) or weak_shape):
                _cap_candidate_confidence(
                    hints,
                    candidate,
                    "rule_weak_justification_high_confidence",
                    cap=0.6,
                    force_uncertain=True,
                )


def _apply_cross_source_join_risk(
    hints: Dict[str, Any],
    catalog: WorkspaceCatalog,
    suggested_join_specs: List[Dict[str, Any]],
) -> None:
    anchor_source = _best_output_anchor_source(hints.get("output_priors_by_slot", {}))
    if anchor_source is None:
        return
    for priors in hints.get("output_priors_by_slot", {}).values():
        for candidate in priors.values():
            source_id = str(candidate.get("source_id", "")).strip()
            if not source_id or source_id == anchor_source:
                continue
            if not _has_join_evidence(catalog, anchor_source, source_id, suggested_join_specs):
                _cap_candidate_confidence(
                    hints,
                    candidate,
                    "rule_cross_source_without_join_evidence",
                    cap=0.4,
                    force_uncertain=True,
                    join_risk=True,
                )
    for priors in hints.get("filter_priors_by_attribute", {}).values():
        for candidate in priors.values():
            source_id = str(candidate.get("source_id", "")).strip()
            if not source_id or source_id == anchor_source:
                continue
            if not _has_join_evidence(catalog, anchor_source, source_id, suggested_join_specs):
                _cap_candidate_confidence(
                    hints,
                    candidate,
                    "rule_cross_source_without_join_evidence",
                    cap=0.4,
                    force_uncertain=True,
                    join_risk=True,
                )
    for priors in hints.get("order_priors_by_target", {}).values():
        for candidate in priors.values():
            source_id = str(candidate.get("source_id", "")).strip()
            if not source_id or source_id == anchor_source:
                continue
            if not _has_join_evidence(catalog, anchor_source, source_id, suggested_join_specs):
                _cap_candidate_confidence(
                    hints,
                    candidate,
                    "rule_cross_source_without_join_evidence",
                    cap=0.4,
                    force_uncertain=True,
                    join_risk=True,
                )


def _apply_order_rules(
    hints: Dict[str, Any],
    catalog: WorkspaceCatalog,
) -> None:
    for target_key, priors in hints.get("order_priors_by_target", {}).items():
        expects_numeric = _target_expects_numeric(target_key)
        expects_time = _target_expects_time(target_key)
        for candidate in priors.values():
            _, profile = _candidate_profile(catalog, candidate)
            if profile is None:
                continue
            if expects_numeric and not (profile.measure_like or profile.numeric_ratio >= 0.6):
                _cap_candidate_confidence(
                    hints,
                    candidate,
                    "rule_order_target_type_mismatch",
                    cap=0.35,
                    force_uncertain=True,
                    force_dummy=profile.text_like or profile.key_like,
                )
            elif expects_time and not profile.time_like:
                _cap_candidate_confidence(
                    hints,
                    candidate,
                    "rule_order_target_type_mismatch",
                    cap=0.35,
                    force_uncertain=True,
                )


def calibrate_grounding_hints(
    hints: Dict[str, Any],
    catalog: WorkspaceCatalog,
    observable_sketch: ObservableSketch,
    instruction: str,
    suggested_join_specs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    calibrated = copy.deepcopy(hints)
    obfuscation = _workspace_obfuscation_metrics(catalog)
    calibrated["order_priors_by_target"] = _derive_order_priors(calibrated, observable_sketch)
    calibrated["cross_source_join_risk"] = False
    calibrated["calibration_rules_fired"] = []
    calibrated["calibration_mode"] = "strict"
    calibrated["fallback_injected"] = {"output_slots": [], "filter_attributes": [], "order_targets": []}
    calibrated["obfuscation_metrics"] = obfuscation

    original_output_priors = copy.deepcopy(calibrated.get("output_priors_by_slot", {}))
    original_order_priors = copy.deepcopy(calibrated.get("order_priors_by_target", {}))

    _apply_duplicate_slot_collapse(calibrated, calibrated.get("output_priors_by_slot", {}))
    _apply_output_filter_profile_rules(calibrated, calibrated.get("output_priors_by_slot", {}), catalog, is_filter=False)
    _apply_output_filter_profile_rules(calibrated, calibrated.get("filter_priors_by_attribute", {}), catalog, is_filter=True)
    _apply_weak_justification_rule(calibrated, calibrated.get("output_priors_by_slot", {}), catalog)
    _apply_weak_justification_rule(calibrated, calibrated.get("filter_priors_by_attribute", {}), catalog)
    _apply_order_rules(calibrated, catalog)
    _apply_weak_justification_rule(calibrated, calibrated.get("order_priors_by_target", {}), catalog)
    fallback_enabled = obfuscation["column_ratio"] >= 0.18 or obfuscation["file_ratio"] >= 0.55
    if fallback_enabled:
        _inject_profile_fallback_output_priors(calibrated, catalog, observable_sketch, instruction)
        _inject_profile_fallback_filter_priors(calibrated, catalog, observable_sketch, instruction)
        _inject_profile_fallback_order_priors(calibrated, catalog, observable_sketch, instruction)
    _apply_cross_source_join_risk(calibrated, catalog, suggested_join_specs)

    for slot_label, priors in original_output_priors.items():
        current = calibrated.get("output_priors_by_slot", {}).get(slot_label, {})
        if priors and not _has_usable_primary(current):
            calibrated["output_priors_by_slot"][slot_label] = priors
            _record_rule(calibrated, None, "rule_safe_fallback_output_slot")

    for target_key, priors in original_order_priors.items():
        current = calibrated.get("order_priors_by_target", {}).get(target_key, {})
        if priors and not _has_usable_primary(current):
            calibrated["order_priors_by_target"][target_key] = priors
            _record_rule(calibrated, None, "rule_safe_fallback_order_target")

    calibrated["strong_multi_source_output"] = len(
        {
            _slot_primary_source(priors)
            for priors in calibrated.get("output_priors_by_slot", {}).values()
            if _slot_primary_source(priors)
        }
    ) > 1
    if (
        calibrated["fallback_injected"]["output_slots"]
        or calibrated["fallback_injected"]["filter_attributes"]
        or calibrated["fallback_injected"]["order_targets"]
    ):
        calibrated["calibration_mode"] = "relaxed"
    elif any(
        not _has_strong_primary(priors)
        for priors in calibrated.get("output_priors_by_slot", {}).values()
    ):
        calibrated["calibration_mode"] = "relaxed"
    elif observable_sketch.order_hint.get("target") and not _has_strong_primary(
        calibrated.get("order_priors_by_target", {}).get(_semantic_key(observable_sketch.order_hint.get("target", "")), {})
    ):
        calibrated["calibration_mode"] = "relaxed"
    if not fallback_enabled and calibrated["calibration_mode"] == "relaxed":
        calibrated["calibration_mode"] = "strict"
    return calibrated


def extract_suggested_join_specs(grounding: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    for item in grounding.get("suggested_joins", []):
        if not isinstance(item, dict):
            continue
        left_source = str(item.get("from_source") or item.get("left_source") or item.get("from") or "").strip()
        right_source = str(item.get("to_source") or item.get("right_source") or item.get("to") or "").strip()
        left_column = str(item.get("from_column") or item.get("left_column") or item.get("join_column") or "").strip()
        right_column = str(item.get("to_column") or item.get("right_column") or item.get("join_column") or "").strip()
        if (not left_source or not left_column) and item.get("left"):
            try:
                left_value = str(item.get("left", "")).strip()
                left_source, left_column = left_value.rsplit(".", 1)
            except ValueError:
                left_source, left_column = left_source, left_column
        if (not right_source or not right_column) and item.get("right"):
            try:
                right_value = str(item.get("right", "")).strip()
                right_source, right_column = right_value.rsplit(".", 1)
            except ValueError:
                right_source, right_column = right_source, right_column
        if not left_source or not right_source or not left_column or not right_column:
            continue
        try:
            confidence = float(item.get("confidence", 0.8))
        except Exception:
            confidence = 0.8
        specs.append(
            {
                "from_source": left_source,
                "from_column": left_column,
                "to_source": right_source,
                "to_column": right_column,
                "confidence": confidence,
                "reason": str(item.get("reason", "")),
            }
        )
    return specs


def _resolved_column_name(source, column_name: str) -> str | None:
    if column_name in source.column_profiles:
        return column_name
    lower = column_name.lower()
    return next((col for col in source.columns if col.lower() == lower), None)


def _validate_llm_edge(edge_spec: Dict[str, Any], catalog: WorkspaceCatalog) -> JoinEdge | None:
    left_source_id = str(edge_spec.get("from_source", "")).strip()
    right_source_id = str(edge_spec.get("to_source", "")).strip()
    left_column_raw = str(edge_spec.get("from_column", "")).strip()
    right_column_raw = str(edge_spec.get("to_column", "")).strip()
    if not left_source_id or not right_source_id or not left_column_raw or not right_column_raw:
        return None
    if left_source_id == right_source_id:
        return None
    if left_source_id not in catalog.sources or right_source_id not in catalog.sources:
        return None

    left_source = catalog.source(left_source_id)
    right_source = catalog.source(right_source_id)
    left_column = _resolved_column_name(left_source, left_column_raw)
    right_column = _resolved_column_name(right_source, right_column_raw)
    if left_column is None or right_column is None:
        return None

    left_profile = left_source.column_profiles[left_column]
    right_profile = right_source.column_profiles[right_column]

    try:
        confidence = float(edge_spec.get("confidence", 0.8))
    except Exception:
        confidence = 0.8
    confidence = max(0.0, min(confidence, 1.0))
    overlap = 0.25 + 0.5 * confidence

    type_conflict = (
        not left_profile.key_like
        and not right_profile.key_like
        and (
            (left_profile.text_like and (right_profile.measure_like or right_profile.numeric_ratio >= 0.7))
            or (right_profile.text_like and (left_profile.measure_like or left_profile.numeric_ratio >= 0.7))
        )
    )
    if type_conflict:
        overlap *= 0.3
    overlap = max(0.0, min(overlap, 0.75))
    if overlap < 0.15:
        return None

    return JoinEdge(
        edge_id=(
            f"llm_overlay__{slugify(left_source_id)}__{slugify(right_source_id)}"
            f"__{slugify(left_column)}__{slugify(right_column)}"
        ),
        left_source_id=left_source_id,
        right_source_id=right_source_id,
        left_column=left_column,
        right_column=right_column,
        left_transform="identity",
        right_transform="identity",
        overlap=float(overlap),
    )


def build_validated_overlay_edges(grounding: Dict[str, Any], catalog: WorkspaceCatalog) -> List[JoinEdge]:
    existing_pairs = {
        frozenset(((edge.left_source_id, edge.left_column), (edge.right_source_id, edge.right_column)))
        for edge in catalog.join_edges
    }
    overlay_edges: List[JoinEdge] = []
    seen_ids: set[str] = set()
    for edge_spec in extract_suggested_join_specs(grounding):
        edge = _validate_llm_edge(edge_spec, catalog)
        if edge is None:
            continue
        pair_key = frozenset(((edge.left_source_id, edge.left_column), (edge.right_source_id, edge.right_column)))
        if pair_key in existing_pairs or edge.edge_id in seen_ids:
            continue
        overlay_edges.append(edge)
        seen_ids.add(edge.edge_id)
    return overlay_edges


def overlay_edges_to_dict(edges: List[JoinEdge]) -> List[Dict[str, Any]]:
    return [asdict(edge) for edge in edges]
