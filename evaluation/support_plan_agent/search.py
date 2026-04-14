from __future__ import annotations

from dataclasses import asdict
from itertools import product
from typing import Any, Dict, List, Tuple

from evaluation.workspace_catalog import WorkspaceCatalog, tokenize

from .types import AnchorPath, Binding, ObligationSketch, ObservableSketch, ObservableSlot, PlanScore, SupportPlan
from .utils import infer_operator_hints, name_overlap_score, normalize_operator_direction, sample_value_overlap_score
from .verifier import obligations_from_trace, verify_support_plan


def _source_label_text(source) -> str:
    return f"{source.file_name} {source.table_name or ''} {' '.join(source.columns)}"


def _question_overlap(question_tokens: List[str], source) -> float:
    source_tokens = set(tokenize(_source_label_text(source)))
    if not source_tokens:
        return 0.0
    overlap = len(set(question_tokens) & source_tokens)
    return overlap / len(source_tokens)


def _observable_requires_aggregation(observable_sketch: ObservableSketch) -> bool:
    return bool(observable_sketch.measure_hints) or any(
        item in {"count", "sum", "avg", "average", "max", "min"}
        for item in observable_sketch.operator_hints
    )


FILTER_TYPE_CONFLICT_REASONS = {
    "numeric_filter_type_mismatch",
    "numeric_filter_time_penalty",
    "text_filter_numeric_penalty",
    "time_attribute_mismatch",
    "time_type_mismatch",
}
STRONG_PATH_SEMANTICS = {"key_path", "fact_to_dimension_path"}
WEAK_PATH_SEMANTICS = {"attribute_echo_path", "fallback_name_match_path"}


def _filter_attribute_key(filter_hint: Dict[str, Any]) -> str:
    return str(filter_hint.get("attribute", "")).strip() or "*"


def _semantic_key(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _llm_prior_bonus(prior: Dict[str, Any]) -> float:
    """Compute score bonus from LLM grounding prior.

    Philosophy: Confidence-gated LLM bonus.
    - Low confidence (< 0.6): modest bonus, let heuristics dominate
    - Medium confidence (0.6-0.75): meaningful bonus
    - High confidence (>= 0.75): strong bonus

    This prevents unreliable LLM guesses from overriding good heuristics on L1,
    while still letting LLM dominate on L2/L3 with obfuscated schemas.
    """
    confidence = max(0.0, min(float(prior.get("confidence", 0.0)), 1.0))
    rank = max(0, int(prior.get("rank", 0)))
    rank_discount = 1.0 if rank == 0 else max(0.3, 0.6 - (0.15 * min(rank - 1, 3)))

    if prior.get("is_dummy_likely"):
        base = -5.0 + (3.0 * confidence)
    elif prior.get("is_uncertain"):
        # Uncertain = weak signal, give only minor bonus
        base = 0.5 + (1.0 * confidence)
    else:
        # Confident = meaningful bonus, scales with confidence
        # Low conf: ~6.5, Med conf: ~11, High conf: ~16
        base = 4.0 + (16.0 * confidence)
    return base * rank_discount


def _llm_family_bonus(
    family_name: str,
    llm_family: str | None,
    llm_family_confidence: float,
    *,
    cross_source_join_risk: bool = False,
) -> float:
    if not llm_family:
        return 0.0
    conf = max(0.0, min(llm_family_confidence, 1.0))
    if conf <= 0.0:
        return 0.0
    if family_name == llm_family:
        bonus = 3.0 + (8.0 * conf)
        if cross_source_join_risk and family_name in {"direct_join", "filter_join", "support_join", "aggregation_join", "count_star_support"}:
            bonus *= 0.7
        return bonus
    near_matches = {
        "direct_join": {"filter_join", "support_join"},
        "filter_join": {"direct_join", "support_join"},
        "support_join": {"direct_join", "filter_join", "aggregation_join", "count_star_support"},
        "aggregation_join": {"count_star_support", "direct_aggregation", "support_join"},
        "count_star_support": {"aggregation_join", "direct_aggregation", "support_join"},
        "direct_aggregation": {"aggregation_join", "count_star_support"},
    }
    if family_name in near_matches.get(llm_family, set()):
        bonus = 1.5 * conf
        if cross_source_join_risk and family_name in {"filter_join", "support_join", "aggregation_join", "count_star_support"}:
            bonus *= 0.7
        return bonus
    penalty = -4.0 * conf
    if cross_source_join_risk and family_name in {"filter_join", "support_join", "aggregation_join", "count_star_support"}:
        penalty *= 0.7
    return penalty


def _has_duplicate_output_binding_conflict(plan: SupportPlan) -> bool:
    if len(plan.output_bindings) <= 1:
        return False
    keys = [(binding.source_id, binding.column_name) for binding in plan.output_bindings]
    if len(keys) == len(set(keys)):
        return False
    slot_labels = {str(binding.metadata.get("slot_label", binding.column_name)).strip() for binding in plan.output_bindings}
    return len(slot_labels) > 1


def _selected_output_prior(binding: Binding, grounding_hints: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not grounding_hints:
        return None
    slot_label = str(binding.metadata.get("slot_label", "")).strip()
    if not slot_label:
        return None
    return grounding_hints.get("output_priors_by_slot", {}).get(slot_label, {}).get((binding.source_id, binding.column_name))


def _selected_filter_prior(binding: Binding, grounding_hints: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not grounding_hints:
        return None
    filter_key = _filter_attribute_key(binding.metadata)
    prior = grounding_hints.get("filter_priors_by_attribute", {}).get(filter_key, {}).get((binding.source_id, binding.column_name))
    if prior is None:
        prior = grounding_hints.get("filter_priors_by_attribute", {}).get("*", {}).get((binding.source_id, binding.column_name))
    return prior


def _selected_order_prior(binding: Binding, target: str, grounding_hints: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not grounding_hints or not target:
        return None
    return grounding_hints.get("order_priors_by_target", {}).get(_semantic_key(target), {}).get((binding.source_id, binding.column_name))


def _has_strong_supported_prior(priors: Dict[tuple[str, str], Dict[str, Any]] | None) -> bool:
    if not priors:
        return False
    return any(
        candidate.get("is_primary")
        and not candidate.get("is_uncertain")
        and not candidate.get("is_dummy_likely")
        and float(candidate.get("confidence", 0.0)) >= 0.55
        for candidate in priors.values()
    )


def _has_strong_nonfallback_prior(priors: Dict[tuple[str, str], Dict[str, Any]] | None) -> bool:
    if not priors:
        return False
    return any(
        candidate.get("is_primary")
        and not candidate.get("is_uncertain")
        and not candidate.get("is_dummy_likely")
        and float(candidate.get("confidence", 0.0)) >= 0.55
        and candidate.get("derived_from") != "profile_fallback"
        for candidate in priors.values()
    )


def _is_semantically_low_confidence_prior(prior: Dict[str, Any] | None) -> bool:
    if not prior:
        return False
    if prior.get("is_dummy_likely"):
        return True
    if not prior.get("is_uncertain"):
        return False
    if prior.get("cross_source_join_risk"):
        return True
    if prior.get("calibration_rules"):
        return True
    return float(prior.get("confidence", 0.0)) < 0.6


def _strong_order_prior_sources(
    operator_plan: Dict[str, Any],
    grounding_hints: Dict[str, Any] | None,
) -> set[str]:
    if not grounding_hints:
        return set()
    target = str(operator_plan.get("target", "")).strip()
    if not target:
        return set()
    priors = grounding_hints.get("order_priors_by_target", {}).get(_semantic_key(target), {})
    return {
        str(candidate.get("source_id", "")).strip()
        for candidate in priors.values()
        if candidate.get("is_primary")
        and not candidate.get("is_uncertain")
        and not candidate.get("is_dummy_likely")
        and float(candidate.get("confidence", 0.0)) >= 0.55
    }


def _numeric_sample_stats(sample_values: List[str]) -> Dict[str, float]:
    nums: List[float] = []
    with_decimal = 0
    for value in sample_values[:8]:
        try:
            num = float(str(value).replace(",", ""))
        except Exception:
            continue
        nums.append(num)
        if abs(num - round(num)) > 1e-6:
            with_decimal += 1
    if not nums:
        return {"count": 0.0, "median_abs": 0.0, "max_abs": 0.0, "decimal_ratio": 0.0}
    ordered = sorted(abs(num) for num in nums)
    return {
        "count": float(len(nums)),
        "median_abs": float(ordered[len(ordered) // 2]),
        "max_abs": float(max(ordered)),
        "decimal_ratio": float(with_decimal / max(len(nums), 1)),
    }


def _normalized_value_set(sample_values: List[str]) -> set[str]:
    return {
        " ".join(str(value).strip().lower().split())
        for value in sample_values[:8]
        if str(value).strip()
    }


def _sample_value_overlap_ratio(left_values: List[str], right_values: List[str]) -> float:
    left = _normalized_value_set(left_values)
    right = _normalized_value_set(right_values)
    if not left or not right:
        return 0.0
    return len(left & right) / max(min(len(left), len(right)), 1)


def _is_identifier_like_text(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(token in lowered for token in [" id", "id ", "id_", "_id", "key", "code", "number", "no", "ref"])


def _is_small_count_attribute(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(
        token in lowered
        for token in [
            "bedroom",
            "bathroom",
            "room",
            "age",
            "star",
            "rating",
            "rank",
            "level",
            "floor",
            "child",
            "children",
            "adult",
            "guest",
            "student",
            "employee",
            "people",
            "person",
            "player",
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "semester",
            "week",
            "count",
            "quantity",
            "qty",
        ]
    )


def _reachable_sources(source_ids: List[str], catalog: WorkspaceCatalog, max_hops: int = 2) -> List[str]:
    seed_sources = [source_id for source_id in source_ids if source_id in catalog.sources]
    if not seed_sources:
        return []
    reachable = set(seed_sources)
    for candidate_source_id in catalog.sources:
        if candidate_source_id in reachable:
            continue
        if any(
            catalog.find_best_path(seed_source_id, candidate_source_id, max_hops=max_hops)
            for seed_source_id in seed_sources
        ):
            reachable.add(candidate_source_id)
    return sorted(reachable)


def _score_output_binding(
    slot: ObservableSlot,
    source,
    column_name: str,
    question_tokens: List[str],
    observable_sketch: ObservableSketch | None = None,
    catalog: WorkspaceCatalog | None = None,
    llm_output_set: set[tuple[str, str]] | None = None,
    slot_grounding_priors: Dict[tuple[str, str], Dict[str, Any]] | None = None,
) -> Tuple[float, List[str]]:
    profile = source.column_profiles[column_name]
    reasons: List[str] = []
    score = name_overlap_score(slot.label, column_name) * 10.0
    # --- Sample value semantic scoring (key for L2 with obfuscated column names) ---
    sv_score, sv_reasons = sample_value_overlap_score(
        slot.label, "", profile.sample_values, slot.role
    )
    score += sv_score
    reasons.extend(sv_reasons)
    if column_name.lower() == slot.label.lower():
        score += 8.0
        reasons.append("exact_column_match")
    if slot.label.lower() in column_name.lower():
        score += 3.0
        reasons.append("label_substring_match")
    # --- LLM pre-grounding bonus ---
    prior = slot_grounding_priors.get((source.source_id, column_name), {}) if slot_grounding_priors else {}
    if prior or (llm_output_set and (source.source_id, column_name) in llm_output_set):
        bonus = _llm_prior_bonus(prior) if prior else 5.0
        score += bonus
        if prior.get("is_dummy_likely"):
            reasons.append("llm_grounding_dummy_penalty")
        elif prior.get("is_uncertain"):
            reasons.append("llm_grounding_uncertain")
        else:
            reasons.append("llm_grounding_match")
    elif slot_grounding_priors and catalog is not None:
        mirror_bonus = 0.0
        for candidate in slot_grounding_priors.values():
            if (
                not candidate.get("is_primary")
                or candidate.get("is_dummy_likely")
                or float(candidate.get("confidence", 0.0)) < 0.45
            ):
                continue
            prior_source_id = str(candidate.get("source_id", "")).strip()
            prior_column_name = str(candidate.get("column_name", "")).strip()
            if not prior_source_id or not prior_column_name or prior_source_id not in catalog.sources:
                continue
            prior_source = catalog.source(prior_source_id)
            prior_profile = prior_source.column_profiles.get(prior_column_name)
            if prior_profile is None:
                continue
            overlap = _sample_value_overlap_ratio(profile.sample_values, prior_profile.sample_values)
            if overlap < 0.5:
                continue
            bonus = 2.0 + (6.0 * overlap)
            if profile.text_like and prior_profile.text_like:
                bonus += 1.5
            if source.source_id != prior_source_id:
                bonus += 1.0
            mirror_bonus = max(mirror_bonus, bonus)
        if mirror_bonus > 0.0:
            score += mirror_bonus
            reasons.append("llm_semantic_mirror")
    if slot.role in {"entity", "attribute", "description", "status", "location"}:
        if profile.text_like:
            score += 3.0
            reasons.append("text_compatible")
        if source.role_hint == "dimension":
            score += 2.0
            reasons.append("dimension_source_bonus")
        elif source.role_hint == "fact":
            score -= 1.5
            reasons.append("fact_source_penalty")
        if profile.unique_ratio >= 0.4:
            score += 1.0
            reasons.append("distinctive_text_values")
        if profile.numeric_ratio >= 0.6 and slot.role != "location":
            score -= 3.0
            reasons.append("numeric_text_mismatch")
        if profile.key_like and any(token in column_name.lower() for token in ["id", "code"]) and slot.role not in {"key", "code"}:
            score -= 2.0
            reasons.append("key_like_text_penalty")
    if slot.role == "measure":
        if profile.measure_like or profile.numeric_ratio >= 0.7:
            score += 4.0
            reasons.append("measure_compatible")
        else:
            score -= 5.0
    if slot.role == "time":
        if profile.time_like:
            score += 4.0
            reasons.append("time_compatible")
        else:
            score -= 5.0
    if slot.role == "key":
        if profile.key_like:
            score += 4.0
            reasons.append("key_compatible")
    if slot.role == "code":
        if profile.text_like:
            score += 3.0
            reasons.append("code_text_compatible")
        if profile.text_like and profile.unique_ratio <= 0.9:
            score += 1.0
            reasons.append("categorical_code_values")
        if profile.key_like and profile.numeric_ratio >= 0.6 and "code" not in column_name.lower():
            score -= 6.0
            reasons.append("numeric_key_code_penalty")
        if "code" in column_name.lower():
            score += 2.0
            reasons.append("code_name_match")
    score += _question_overlap(question_tokens, source) * 3.0
    if observable_sketch is not None and catalog is not None:
        needs_relational_support = bool(observable_sketch.filter_hints or observable_sketch.measure_hints) or any(
            item in {"count", "sum", "avg", "average", "max", "min"} for item in observable_sketch.operator_hints
        )
        if needs_relational_support and slot.role in {"entity", "attribute", "description", "status", "location"}:
            neighbors = catalog.join_neighbors(source.source_id)
            if neighbors:
                avg_overlap = sum(edge.overlap for edge in neighbors) / len(neighbors)
                fact_neighbor = any(
                    catalog.source(edge.left_source_id if edge.right_source_id == source.source_id else edge.right_source_id).role_hint == "fact"
                    for edge in neighbors
                )
                if fact_neighbor and source.role_hint in {"dimension", "unknown"}:
                    score += 2.0 + (avg_overlap * 2.0)
                    reasons.append("fact_neighbor_bonus")
                elif source.role_hint == "fact":
                    score -= 1.5
                    reasons.append("fact_like_output_risk")
    return score, reasons


def _score_filter_binding(
    filter_hint: Dict[str, Any],
    source,
    column_name: str,
    question_tokens: List[str],
    preferred_source_ids: set[str] | None = None,
    llm_filter_set: set[tuple[str, str]] | None = None,
    filter_grounding_priors: Dict[tuple[str, str], Dict[str, Any]] | None = None,
) -> Tuple[float, List[str]]:
    profile = source.column_profiles[column_name]
    attribute = str(filter_hint.get("attribute", ""))
    score = name_overlap_score(attribute, column_name) * 12.0
    reasons: List[str] = []
    if attribute and attribute.lower() in column_name.lower():
        score += 5.0
        reasons.append("attribute_substring_match")
    # --- LLM pre-grounding bonus ---
    prior = filter_grounding_priors.get((source.source_id, column_name), {}) if filter_grounding_priors else {}
    if prior or (llm_filter_set and (source.source_id, column_name) in llm_filter_set):
        bonus = _llm_prior_bonus(prior) if prior else 5.0
        score += bonus
        if prior.get("is_dummy_likely"):
            reasons.append("llm_grounding_dummy_penalty")
        elif prior.get("is_uncertain"):
            reasons.append("llm_grounding_uncertain")
        else:
            reasons.append("llm_grounding_match")
    filter_value = filter_hint.get("value")
    if isinstance(filter_value, str):
        try:
            filter_value = float(filter_value) if "." in filter_value else int(filter_value)
        except (ValueError, TypeError):
            pass
    if isinstance(filter_value, (int, float)):
        if profile.numeric_ratio >= 0.5 or profile.measure_like:
            score += 4.0
            reasons.append("numeric_filter_compatible")
        elif profile.time_like:
            score -= 4.0
            reasons.append("numeric_filter_time_penalty")
        else:
            score -= 6.0
            reasons.append("numeric_filter_type_mismatch")
        attribute_lower = attribute.lower()
        numeric_stats = _numeric_sample_stats(profile.sample_values)
        if profile.key_like and not _is_identifier_like_text(attribute_lower):
            score -= 6.0
            reasons.append("numeric_filter_key_like_penalty")
        if profile.unique_ratio >= 0.9 and not profile.measure_like and not _is_identifier_like_text(attribute_lower):
            score -= 2.5
            reasons.append("numeric_filter_high_unique_penalty")
        if _is_small_count_attribute(attribute_lower) and numeric_stats["count"] > 0.0:
            plausible_upper = max(100.0, abs(float(filter_value)) * 12.0 + 12.0)
            plausible_median = max(20.0, abs(float(filter_value)) * 6.0 + 6.0)
            if numeric_stats["median_abs"] <= plausible_median and numeric_stats["max_abs"] <= plausible_upper:
                score += 2.5
                reasons.append("numeric_filter_scale_plausible")
            elif numeric_stats["median_abs"] >= 100.0 or numeric_stats["max_abs"] >= 1000.0:
                score -= 5.0
                reasons.append("numeric_filter_scale_mismatch")
    else:
        values = [value.lower() for value in profile.sample_values]
        value_text = str(filter_hint.get("value_text", "")).lower()
        if value_text and any(value_text in value for value in values):
            score += 4.0
            reasons.append("literal_sample_match")
        if value_text:
            if profile.text_like:
                score += 1.5
                reasons.append("text_filter_compatible")
            elif profile.numeric_ratio >= 0.5:
                score -= 4.0
                reasons.append("text_filter_numeric_penalty")
    attribute_lower = attribute.lower()
    if any(token in attribute_lower for token in ["date", "year", "month", "time"]):
        if profile.time_like or any(token in column_name.lower() for token in ["date", "year", "month", "time"]):
            score += 4.0
            reasons.append("time_attribute_match")
        else:
            score -= 3.0
            reasons.append("time_attribute_mismatch")
    if source.role_hint == "fact":
        score += 1.0
        reasons.append("fact_filter_bonus")
    score += _question_overlap(question_tokens, source) * 2.0
    return score, reasons


def _score_time_binding(source, column_name: str, preferred_source_ids: set[str] | None = None) -> Tuple[float, List[str]]:
    profile = source.column_profiles[column_name]
    score = 0.0
    reasons: List[str] = []
    if profile.time_like:
        score += 6.0
        reasons.append("time_compatible")
    if "date" in column_name.lower() or "year" in column_name.lower() or "time" in column_name.lower():
        score += 2.5
        reasons.append("time_name_match")
    elif not profile.time_like:
        score -= 3.5
        reasons.append("time_type_mismatch")
    return score, reasons


def _score_order_binding(
    target: str,
    source,
    column_name: str,
    question_tokens: List[str],
    preferred_source_ids: set[str] | None = None,
    order_grounding_priors: Dict[tuple[str, str], Dict[str, Any]] | None = None,
) -> Tuple[float, List[str]]:
    profile = source.column_profiles[column_name]
    target_lower = target.lower()
    score = name_overlap_score(target, column_name) * 12.0
    reasons: List[str] = []

    # Semantic mappings for common measure targets
    # When target is "duration", also match columns named "time", "length", etc.
    target_synonyms = {
        "duration": {"duration", "time", "length", "period", "elapsed", "seconds", "minutes", "hours"},
        "distance": {"distance", "length", "miles", "km", "kilometers", "meters"},
        "length": {"length", "distance", "size", "long"},
        "height": {"height", "altitude", "elevation"},
        "weight": {"weight", "mass", "kg", "pounds"},
        "price": {"price", "cost", "amount", "fee", "rate", "salary"},
        "count": {"count", "number", "total", "quantity", "num"},
        "rating": {"rating", "score", "grade", "rank"},
        "date": {"date", "day", "time", "when"},
    }

    # Check for synonym matches
    for canonical, synonyms in target_synonyms.items():
        if target_lower == canonical or target_lower in synonyms:
            col_lower = column_name.lower()
            if col_lower in synonyms:
                score += 8.0
                reasons.append(f"order_target_synonym_match:{canonical}")
                break

    if target_lower and target_lower in column_name.lower():
        score += 5.0
        reasons.append("order_target_substring_match")
    prior = order_grounding_priors.get((source.source_id, column_name), {}) if order_grounding_priors else {}
    if prior:
        score += _llm_prior_bonus(prior)
        if prior.get("is_dummy_likely"):
            reasons.append("llm_grounding_dummy_penalty")
        elif prior.get("is_uncertain"):
            reasons.append("llm_grounding_uncertain")
        else:
            reasons.append("llm_grounding_match")
    expects_time = any(token in target_lower for token in ["date", "year", "month", "time", "day"])
    expects_numeric = any(token in target_lower for token in ["price", "amount", "cost", "score", "rating", "total", "number", "count", "value", "duration", "distance", "length", "height"])
    if expects_time:
        if profile.time_like:
            score += 4.0
            reasons.append("order_time_compatible")
        else:
            score -= 4.0
            reasons.append("order_time_mismatch")
    elif expects_numeric:
        if profile.measure_like or profile.numeric_ratio >= 0.6:
            score += 4.0
            reasons.append("order_numeric_compatible")
        elif profile.time_like:
            score -= 3.0
            reasons.append("order_numeric_time_penalty")
        else:
            score -= 4.0
            reasons.append("order_numeric_mismatch")
    else:
        if profile.text_like:
            score += 1.5
            reasons.append("order_text_fallback")
    has_target_lexical_match = target_lower and (
        target_lower in column_name.lower()
        or any(
            synonym in column_name.lower()
            for synonyms in target_synonyms.values()
            for synonym in synonyms
            if target_lower in synonyms
        )
    )
    if source.role_hint == "fact" and (expects_numeric or expects_time):
        score += 1.0
        reasons.append("fact_order_bonus")
    if profile.key_like and not any(token in target_lower for token in ["id", "key", "code"]) and not has_target_lexical_match:
        score -= 8.0
        reasons.append("order_key_like_penalty")
    score += _question_overlap(question_tokens, source) * 2.0
    return score, reasons


def _score_support_source(
    source,
    output_source_id: str,
    obligation_sketch: ObligationSketch,
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
    question_tokens: List[str],
) -> Tuple[float, List[str], AnchorPath | None]:
    score = 0.0
    reasons: List[str] = []
    aggregation_required = _observable_requires_aggregation(observable_sketch)
    if source.role_hint == "fact":
        score += 5.0
        reasons.append("fact_source_bonus")
    elif source.role_hint == "dimension":
        score -= 1.5
    score += _question_overlap(question_tokens, source) * 4.0
    if observable_sketch.time_hints.get("years") or observable_sketch.time_hints.get("months"):
        if any(profile.time_like for profile in source.column_profiles.values()):
            score += 2.0
            reasons.append("has_time_evidence")
    if observable_sketch.filter_hints:
        if any(profile.measure_like or profile.time_like for profile in source.column_profiles.values()):
            score += 1.5
            reasons.append("can_host_filters")
    path_edges = catalog.find_best_path(source.source_id, output_source_id, max_hops=2)
    if source.source_id == output_source_id:
        anchor_path = AnchorPath(path_source_ids=[source.source_id], edges=[], score=1.0, notes=["same_source"])
    elif path_edges:
        anchor_score = sum(edge.overlap for edge in path_edges)
        score += anchor_score * 8.0
        reasons.append("anchor_path_found")
        edge_payload = [asdict(edge) for edge in path_edges]
        anchor_path = AnchorPath(
            path_source_ids=_ordered_path_source_ids(source.source_id, edge_payload),
            edges=edge_payload,
            score=float(anchor_score),
            notes=[],
        )
    else:
        anchor_path = None
        score -= 4.0
    if source.source_id == output_source_id:
        if aggregation_required:
            score -= 5.0
            reasons.append("same_source_aggregation_penalty")
        elif obligation_sketch.probability("support_relation") >= 0.45:
            score -= 2.0
            reasons.append("same_source_penalty")
    return score, reasons, anchor_path


def _best_output_bindings(
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
    question_tokens: List[str],
    top_k: int = 8,
    llm_output_set: set[tuple[str, str]] | None = None,
    llm_output_priors_by_slot: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] | None = None,
) -> Dict[str, List[Binding]]:
    ranked: Dict[str, List[Binding]] = {}
    for slot in observable_sketch.output_slots:
        candidates: List[Binding] = []
        slot_priors = (llm_output_priors_by_slot or {}).get(slot.label, {})
        for source in catalog.sources.values():
            for column_name in source.columns:
                score, reasons = _score_output_binding(
                    slot,
                    source,
                    column_name,
                    question_tokens,
                    observable_sketch=observable_sketch,
                    catalog=catalog,
                    llm_output_set=llm_output_set,
                    slot_grounding_priors=slot_priors,
                )
                candidates.append(
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name=column_name,
                        role=slot.role,
                        score=float(score),
                        reasons=reasons,
                        metadata={"slot_label": slot.label},
                    )
                )
        candidates.sort(key=lambda item: item.score, reverse=True)
        ranked[slot.label] = candidates[:top_k]
    return ranked


def _best_output_bindings_for_source(
    observable_sketch: ObservableSketch,
    source,
    question_tokens: List[str],
    *,
    llm_output_set: set[tuple[str, str]] | None = None,
    llm_output_priors_by_slot: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] | None = None,
    per_slot_top_k: int = 6,
    combo_top_k: int = 4,
    catalog: WorkspaceCatalog | None = None,
) -> List[Tuple[List[Binding], float]]:
    slot_order = [slot.label for slot in observable_sketch.output_slots]
    slot_candidates: Dict[str, List[Binding]] = {}
    for slot in observable_sketch.output_slots:
        slot_priors = (llm_output_priors_by_slot or {}).get(slot.label, {})
        candidates: List[Binding] = []
        for column_name in source.columns:
            score, reasons = _score_output_binding(
                slot,
                source,
                column_name,
                question_tokens,
                observable_sketch=observable_sketch,
                catalog=catalog,
                llm_output_set=llm_output_set,
                slot_grounding_priors=slot_priors,
            )
            candidates.append(
                Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name=column_name,
                    role=slot.role,
                    score=float(score),
                    reasons=reasons,
                    metadata={"slot_label": slot.label},
                )
            )
        candidates.sort(key=lambda item: item.score, reverse=True)
        slot_candidates[slot.label] = candidates[:per_slot_top_k]

    combos: List[Tuple[List[Binding], float]] = []
    for tuple_bindings in product(*[slot_candidates[label] for label in slot_order]):
        bindings = list(tuple_bindings)
        score = sum(binding.score for binding in bindings)
        if len({binding.column_name for binding in bindings}) < len(bindings):
            score -= 6.0
        temp_plan = SupportPlan(output_bindings=bindings)
        if _has_duplicate_output_binding_conflict(temp_plan):
            score -= 4.0
        combos.append((bindings, score))

    deduped: Dict[Tuple[Tuple[str, str], ...], Tuple[List[Binding], float]] = {}
    for bindings, score in combos:
        key = tuple((binding.source_id, binding.column_name) for binding in bindings)
        current = deduped.get(key)
        if current is None or score > current[1]:
            deduped[key] = (bindings, score)
    ranked = sorted(deduped.values(), key=lambda item: item[1], reverse=True)
    return ranked[:combo_top_k]


def _answer_source_world_bonus(
    source,
    observable_sketch: ObservableSketch,
    operator_plan: Dict[str, Any] | None,
    catalog: WorkspaceCatalog,
    grounding_hints: Dict[str, Any] | None,
) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []
    operator_plan = operator_plan or {}
    neighbors = catalog.join_neighbors(source.source_id)
    neighbor_source_ids = {
        edge.left_source_id if edge.right_source_id == source.source_id else edge.right_source_id
        for edge in neighbors
    }
    has_fact_neighbor = any(catalog.source(source_id).role_hint == "fact" for source_id in neighbor_source_ids)
    if any(slot.role in {"entity", "attribute", "description", "status", "location", "code"} for slot in observable_sketch.output_slots):
        if source.role_hint == "dimension":
            score += 1.5
            reasons.append("dimension_answer_source")
        elif source.role_hint == "fact":
            score -= 1.5
            reasons.append("fact_answer_source_risk")
    if observable_sketch.filter_hints:
        filter_prior_sources = {
            str(candidate.get("source_id", "")).strip()
            for priors in (grounding_hints or {}).get("filter_priors_by_attribute", {}).values()
            for candidate in priors.values()
            if not candidate.get("is_dummy_likely")
            and float(candidate.get("confidence", 0.0)) >= 0.3
        }
        if source.source_id in filter_prior_sources:
            score += 1.5
            reasons.append("answer_source_has_filter_prior")
        elif any(catalog.find_best_path(source.source_id, filter_source_id, max_hops=2) for filter_source_id in filter_prior_sources):
            score += 2.5
            reasons.append("answer_source_reaches_filter_world")
        elif has_fact_neighbor:
            score += 1.0
            reasons.append("answer_source_has_fact_neighbor")
        else:
            score -= 1.5
            reasons.append("answer_source_filter_isolated")
    if operator_plan.get("direction"):
        order_sources = _strong_order_prior_sources(operator_plan, grounding_hints)
        if source.source_id in order_sources:
            score += 1.0
            reasons.append("answer_source_has_order_prior")
        elif any(catalog.find_best_path(source.source_id, order_source_id, max_hops=2) for order_source_id in order_sources):
            score += 2.0
            reasons.append("answer_source_reaches_order_world")
    if _observable_requires_aggregation(observable_sketch):
        if source.role_hint in {"dimension", "unknown"} and has_fact_neighbor:
            score += 2.0
            reasons.append("aggregation_answer_source_reaches_fact")
        elif source.role_hint == "fact" and any(slot.role in {"entity", "attribute", "description", "status", "location"} for slot in observable_sketch.output_slots):
            score -= 1.5
            reasons.append("aggregation_answer_source_fact_risk")
    if (observable_sketch.filter_hints or operator_plan.get("direction") or _observable_requires_aggregation(observable_sketch)) and not neighbors:
        score -= 1.5
        reasons.append("relationally_isolated_answer_source")
    return score, reasons


def _same_source_output_world_candidates(
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
    question_tokens: List[str],
    *,
    top_k: int = 12,
    llm_output_set: set[tuple[str, str]] | None = None,
    llm_output_priors_by_slot: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] | None = None,
    operator_plan: Dict[str, Any] | None = None,
    grounding_hints: Dict[str, Any] | None = None,
) -> List[Tuple[List[Binding], List[AnchorPath], float]]:
    candidates: List[Tuple[List[Binding], List[AnchorPath], float]] = []
    for source in catalog.sources.values():
        source_combos = _best_output_bindings_for_source(
            observable_sketch,
            source,
            question_tokens,
            llm_output_set=llm_output_set,
            llm_output_priors_by_slot=llm_output_priors_by_slot,
            catalog=catalog,
        )
        world_bonus, _ = _answer_source_world_bonus(
            source,
            observable_sketch,
            operator_plan,
            catalog,
            grounding_hints,
        )
        for bindings, score in source_combos:
            candidates.append((bindings, [], score + world_bonus))
    candidates.sort(key=lambda item: item[2], reverse=True)
    return candidates[:top_k]


def _output_plan_candidates(
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
    question_tokens: List[str],
    top_k: int = 24,
    llm_output_set: set[tuple[str, str]] | None = None,
    llm_output_priors_by_slot: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] | None = None,
    operator_plan: Dict[str, Any] | None = None,
    grounding_hints: Dict[str, Any] | None = None,
) -> List[Tuple[List[Binding], List[AnchorPath], float]]:
    binding_options = _best_output_bindings(
        observable_sketch,
        catalog,
        question_tokens,
        llm_output_set=llm_output_set,
        llm_output_priors_by_slot=llm_output_priors_by_slot,
    )
    slot_order = [slot.label for slot in observable_sketch.output_slots]
    combos: List[Tuple[List[Binding], List[AnchorPath], float]] = []
    strong_order_sources = _strong_order_prior_sources(operator_plan or {}, grounding_hints)
    for tuple_bindings in product(*[binding_options[label] for label in slot_order]):
        bindings = list(tuple_bindings)
        combo_score = sum(binding.score for binding in bindings)
        join_paths: List[AnchorPath] = []
        primary_source_id = bindings[0].source_id
        connected = True
        for binding in bindings[1:]:
            if binding.source_id == primary_source_id:
                continue
            path_edges = catalog.find_best_path(primary_source_id, binding.source_id, max_hops=2)
            if not path_edges:
                combo_score -= 6.0
                connected = False
                continue
            combo_score += sum(edge.overlap for edge in path_edges) * 6.0
            edge_payload = [asdict(edge) for edge in path_edges]
            join_paths.append(
                AnchorPath(
                    path_source_ids=_ordered_path_source_ids(primary_source_id, edge_payload),
                    edges=edge_payload,
                    score=float(sum(edge.overlap for edge in path_edges)),
                    notes=["output_join_path"],
                )
            )
        if not connected:
            continue
        if strong_order_sources and operator_plan and operator_plan.get("direction"):
            order_reachable = False
            all_sources = {binding.source_id for binding in bindings}
            for output_source_id in all_sources:
                if output_source_id in strong_order_sources:
                    order_reachable = True
                    break
                for order_source_id in strong_order_sources:
                    if catalog.find_best_path(output_source_id, order_source_id, max_hops=2):
                        order_reachable = True
                        break
                if order_reachable:
                    break
            if order_reachable:
                combo_score += 6.0
            else:
                combo_score -= 3.0
        combos.append((bindings, join_paths, combo_score))
    dedup: Dict[Tuple[Tuple[str, str], ...], Tuple[List[Binding], List[AnchorPath], float]] = {}
    for bindings, join_paths, score in combos:
        key = tuple((binding.source_id, binding.column_name) for binding in bindings)
        current = dedup.get(key)
        if current is None or score > current[2]:
            dedup[key] = (bindings, join_paths, score)
    ranked = sorted(dedup.values(), key=lambda item: item[2], reverse=True)
    return ranked[:top_k]


def _compute_filter_join_paths(
    filter_bindings: List[Binding],
    connected_source_ids: List[str],
    catalog: WorkspaceCatalog,
) -> List[AnchorPath]:
    """For each filter binding whose source is not already connected, find and return
    an AnchorPath connecting it to the main plan graph.

    Strategy (in order):
    1. Catalog overlap path (find_best_path) – the normal case.
    2. Column-name exact-match fallback – for L2 obfuscated workspaces where
       value-overlap is broken but FK column names survive obfuscation.
       e.g. both data_s97x and export_joay have 'apt_id', so we synthesise a
       join edge on that shared column even though the catalog has no edge.
    """
    if not filter_bindings:
        return []
    connected: set[str] = set(connected_source_ids)
    extra_paths: List[AnchorPath] = []
    for fb in filter_bindings:
        if fb.source_id in connected:
            continue

        # --- pass 1: catalog overlap path ---
        best_edges = None
        best_score = -1.0
        best_via: str = ""
        for via_id in list(connected):
            path_edges = catalog.find_best_path(via_id, fb.source_id, max_hops=2)
            if not path_edges:
                path_edges = catalog.find_best_path(fb.source_id, via_id, max_hops=2)
            if path_edges:
                score = sum(e.overlap for e in path_edges)
                if score > best_score:
                    best_score = score
                    best_edges = path_edges
                    best_via = via_id

        if best_edges is not None:
            edge_payload = [asdict(e) for e in best_edges]
            extra_paths.append(
                AnchorPath(
                    path_source_ids=_ordered_path_source_ids(best_via, edge_payload),
                    edges=edge_payload,
                    score=float(best_score),
                    notes=["filter_join_path"],
                )
            )
            connected.add(fb.source_id)
            continue

        # --- pass 2: column-name exact-match fallback ---
        filter_source = catalog.source(fb.source_id)
        # Candidate FK columns on the filter source: everything except the filter column itself.
        filter_col_set = {c.lower(): c for c in filter_source.columns if c.lower() != fb.column_name.lower()}

        best_fallback_via: str = ""
        best_fallback_left_col: str = ""
        best_fallback_right_col: str = ""
        best_fallback_score: float = -1.0

        for via_id in list(connected):
            via_source = catalog.source(via_id)
            via_col_lower = {c.lower(): c for c in via_source.columns}
            shared = set(filter_col_set.keys()) & set(via_col_lower.keys())
            for shared_lower in shared:
                score = 1.0
                if any(kw in shared_lower for kw in ("id", "key", "code", "no", "num", "ref")):
                    score += 3.0
                if score > best_fallback_score:
                    best_fallback_score = score
                    best_fallback_via = via_id
                    best_fallback_left_col = via_col_lower[shared_lower]
                    best_fallback_right_col = filter_col_set[shared_lower]

        if best_fallback_via:
            synthetic_edge: Dict[str, Any] = {
                "edge_id": (
                    f"{best_fallback_via}__{fb.source_id}"
                    f"__{best_fallback_left_col}__{best_fallback_right_col}__namematch"
                ),
                "left_source_id": best_fallback_via,
                "right_source_id": fb.source_id,
                "left_column": best_fallback_left_col,
                "right_column": best_fallback_right_col,
                "left_transform": "identity",
                "right_transform": "identity",
                "overlap": 0.01,
            }
            extra_paths.append(
                AnchorPath(
                    path_source_ids=[best_fallback_via, fb.source_id],
                    edges=[synthetic_edge],
                    score=best_fallback_score,
                    notes=["filter_join_path_namematch_fallback"],
                )
            )
            connected.add(fb.source_id)

    return extra_paths


def _compute_single_join_path(
    source_id: str,
    connected_source_ids: List[str],
    catalog: WorkspaceCatalog,
    *,
    path_note: str,
) -> AnchorPath | None:
    connected: set[str] = set(connected_source_ids)
    if source_id in connected:
        return None
    best_edges = None
    best_score = -1.0
    best_via: str = ""
    for via_id in list(connected):
        path_edges = catalog.find_best_path(via_id, source_id, max_hops=2)
        if not path_edges:
            path_edges = catalog.find_best_path(source_id, via_id, max_hops=2)
        if path_edges:
            score = sum(e.overlap for e in path_edges)
            if score > best_score:
                best_score = score
                best_edges = path_edges
                best_via = via_id
    if best_edges is None:
        return None
    edge_payload = [asdict(e) for e in best_edges]
    return AnchorPath(
        path_source_ids=_ordered_path_source_ids(best_via, edge_payload),
        edges=edge_payload,
        score=float(best_score),
        notes=[path_note],
    )


def _binding_has_filter_type_conflict(binding: Binding) -> bool:
    return any(reason in FILTER_TYPE_CONFLICT_REASONS for reason in binding.reasons)


def _binding_has_order_type_conflict(binding: Binding) -> bool:
    return any(
        reason in {"order_time_mismatch", "order_numeric_mismatch", "order_numeric_time_penalty"}
        for reason in binding.reasons
    )


def _ordered_path_source_ids(start_source_id: str, edges: List[Dict[str, Any]]) -> List[str]:
    if not edges:
        return [start_source_id]
    remaining = list(edges)
    current = start_source_id
    ordered = [start_source_id]
    while remaining:
        for idx, edge in enumerate(remaining):
            if edge["left_source_id"] == current:
                current = edge["right_source_id"]
                ordered.append(current)
                remaining.pop(idx)
                break
            if edge["right_source_id"] == current:
                current = edge["left_source_id"]
                ordered.append(current)
                remaining.pop(idx)
                break
        else:
            # Fall back to a best-effort source sequence if the edge ordering
            # is not directly traversable from the requested start source.
            for edge in remaining:
                for source_id in (edge["left_source_id"], edge["right_source_id"]):
                    if source_id not in ordered:
                        ordered.append(source_id)
            break
    return ordered


def _path_uses_output_projection_bridge(path: AnchorPath, output_bindings: List[Binding]) -> bool:
    if len(path.edges) <= 1:
        return False
    output_columns_by_source: Dict[str, set[str]] = {}
    for binding in output_bindings:
        output_columns_by_source.setdefault(binding.source_id, set()).add(binding.column_name)
    for edge in path.edges:
        if edge["left_source_id"] in output_columns_by_source and edge["left_column"] in output_columns_by_source[edge["left_source_id"]]:
            return True
        if edge["right_source_id"] in output_columns_by_source and edge["right_column"] in output_columns_by_source[edge["right_source_id"]]:
            return True
    return False


def _path_semantics(path: AnchorPath, output_source_id: str | None, catalog: WorkspaceCatalog) -> str:
    if any("same_source" in note for note in path.notes):
        return "same_source_path"
    if any("namematch_fallback" in note for note in path.notes):
        return "fallback_name_match_path"
    has_output_echo = False
    has_fact_dimension = False
    has_key_edge = False
    for edge in path.edges:
        left_source = catalog.source(edge["left_source_id"])
        right_source = catalog.source(edge["right_source_id"])
        left_profile = left_source.column_profiles.get(edge["left_column"])
        right_profile = right_source.column_profiles.get(edge["right_column"])
        if left_profile and right_profile and left_profile.key_like and right_profile.key_like:
            has_key_edge = True
        if {left_source.role_hint, right_source.role_hint} == {"fact", "dimension"}:
            has_fact_dimension = True
        if output_source_id is not None:
            if edge["left_source_id"] == output_source_id and left_profile is not None and left_profile.text_like and not left_profile.key_like:
                has_output_echo = True
            if edge["right_source_id"] == output_source_id and right_profile is not None and right_profile.text_like and not right_profile.key_like:
                has_output_echo = True
    if has_output_echo:
        return "attribute_echo_path"
    if has_fact_dimension and has_key_edge:
        return "fact_to_dimension_path"
    if has_key_edge:
        return "key_path"
    return "generic_path"


def _path_quality(path: AnchorPath, output_source_id: str | None, catalog: WorkspaceCatalog) -> Tuple[str, str]:
    semantic = _path_semantics(path, output_source_id, catalog)
    if semantic in {"same_source_path"} | STRONG_PATH_SEMANTICS:
        return semantic, "strong"
    if semantic in WEAK_PATH_SEMANTICS:
        return semantic, "weak"
    if path.score < 0.12:
        return semantic, "weak"
    return semantic, "acceptable"


def _filter_assignment_candidates(
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
    question_tokens: List[str],
    candidate_source_ids: List[str],
    *,
    per_hint_top_k: int = 5,
    assignment_top_k: int = 12,
    llm_filter_set: set[tuple[str, str]] | None = None,
    llm_filter_priors_by_attribute: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] | None = None,
) -> List[Tuple[List[Binding], float]]:
    preferred_source_ids = {source_id for source_id in candidate_source_ids if source_id in catalog.sources}
    sources = [catalog.source(source_id) for source_id in preferred_source_ids] if preferred_source_ids else list(catalog.sources.values())
    groups: List[List[Binding]] = []

    for filter_hint in observable_sketch.filter_hints:
        candidates: List[Binding] = []
        filter_priors = (llm_filter_priors_by_attribute or {}).get(_filter_attribute_key(filter_hint), {})
        if not filter_priors:
            filter_priors = (llm_filter_priors_by_attribute or {}).get("*", {})
        for source in sources:
            for column_name in source.columns:
                score, reasons = _score_filter_binding(
                    filter_hint,
                    source,
                    column_name,
                    question_tokens,
                    preferred_source_ids=preferred_source_ids,
                    llm_filter_set=llm_filter_set,
                    filter_grounding_priors=filter_priors,
                )
                candidates.append(
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name=column_name,
                        role="filter",
                        score=float(score),
                        reasons=reasons,
                        metadata=dict(filter_hint),
                    )
                )
        candidates.sort(key=lambda item: item.score, reverse=True)
        groups.append(candidates[:per_hint_top_k])

    time_options: List[Binding | None] = [None]
    if observable_sketch.time_hints.get("years") or observable_sketch.time_hints.get("months"):
        time_candidates: List[Binding] = []
        for source in sources:
            for column_name in source.columns:
                score, reasons = _score_time_binding(source, column_name, preferred_source_ids=preferred_source_ids)
                time_candidates.append(
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name=column_name,
                        role="time",
                        score=float(score),
                        reasons=reasons,
                        metadata=dict(observable_sketch.time_hints),
                    )
                )
        time_candidates.sort(key=lambda item: item.score, reverse=True)
        time_options = [None] + time_candidates[:2]

    assignments: List[Tuple[List[Binding], float]] = []
    if not groups:
        for time_binding in time_options:
            binding_list = [time_binding] if time_binding is not None else []
            assignments.append((binding_list, sum(binding.score for binding in binding_list)))
    else:
        for combo in product(*groups):
            base = list(combo)
            for time_binding in time_options:
                binding_list = list(base)
                if time_binding is not None:
                    binding_list.append(time_binding)
                assignments.append((binding_list, sum(binding.score for binding in binding_list)))

    dedup: Dict[Tuple[Tuple[str, str, str], ...], Tuple[List[Binding], float]] = {}
    for bindings, score in assignments:
        key = tuple(sorted((binding.source_id, binding.column_name, binding.role) for binding in bindings))
        current = dedup.get(key)
        if current is None or score > current[1]:
            dedup[key] = (bindings, score)
    ranked = sorted(dedup.values(), key=lambda item: item[1], reverse=True)
    return ranked[:assignment_top_k]


def _best_filter_bindings(
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
    question_tokens: List[str],
    candidate_source_ids: List[str],
    llm_filter_priors_by_attribute: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] | None = None,
) -> List[Binding]:
    assignments = _filter_assignment_candidates(
        observable_sketch,
        catalog,
        question_tokens,
        candidate_source_ids,
        per_hint_top_k=1,
        assignment_top_k=1,
        llm_filter_priors_by_attribute=llm_filter_priors_by_attribute,
    )
    return assignments[0][0] if assignments else []


def _filter_binding_key_like_misuse(binding: Binding, catalog: WorkspaceCatalog) -> bool:
    source = catalog.source(binding.source_id)
    profile = source.column_profiles[binding.column_name]
    attribute_text = str(binding.metadata.get("attribute", ""))
    return profile.key_like and profile.unique_ratio >= 0.8 and not _is_identifier_like_text(attribute_text)


def _filter_binding_scale_mismatch(binding: Binding, catalog: WorkspaceCatalog) -> bool:
    raw_value = binding.metadata.get("value")
    try:
        value = float(raw_value)
    except Exception:
        return False
    attribute_text = str(binding.metadata.get("attribute", ""))
    if not _is_small_count_attribute(attribute_text):
        return False
    source = catalog.source(binding.source_id)
    profile = source.column_profiles[binding.column_name]
    stats = _numeric_sample_stats(profile.sample_values)
    if stats["count"] <= 0.0:
        return False
    plausible_upper = max(100.0, abs(value) * 12.0 + 12.0)
    plausible_median = max(20.0, abs(value) * 6.0 + 6.0)
    return stats["median_abs"] > plausible_median and stats["max_abs"] > plausible_upper


def _order_binding_candidates(
    operator_plan: Dict[str, Any],
    catalog: WorkspaceCatalog,
    question_tokens: List[str],
    candidate_source_ids: List[str],
    *,
    top_k: int = 4,
    order_priors_by_target: Dict[str, Dict[tuple[str, str], Dict[str, Any]]] | None = None,
) -> List[Tuple[Binding | None, AnchorPath | None, float]]:
    direction = operator_plan.get("direction")
    target = str(operator_plan.get("target", "")).strip()
    if not direction:
        return [(None, None, 0.0)]
    preferred_source_ids = {sid for sid in candidate_source_ids if sid in catalog.sources}
    if not target:
        ranked: List[Tuple[Binding, AnchorPath | None, float]] = []
        for source in catalog.sources.values():
            for column_name, profile in source.column_profiles.items():
                # Only consider columns that look like they can be ranked
                if not (profile.measure_like or profile.numeric_ratio >= 0.5 or profile.time_like):
                    continue
                score = 0.0
                reasons = ["fallback_order_candidate"]
                if profile.measure_like:
                    score += 6.0
                    reasons.append("measure_like")
                if profile.numeric_ratio >= 0.7:
                    score += 4.0
                    reasons.append("high_numeric_ratio")
                if profile.time_like:
                    score += 2.0
                    reasons.append("time_like")
                binding = Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name=column_name,
                    role="order",
                    score=float(score),
                    reasons=reasons,
                    metadata={"target": "IMPLICIT_MEASURE", "direction": direction},
                )
                order_path = _compute_single_join_path(
                    source.source_id, candidate_source_ids, catalog, path_note="order_join_path"
                )
                if source.source_id not in preferred_source_ids and order_path is None:
                    continue
                total_score = score + (order_path.score * 2.0 if order_path is not None else 0.0)
                ranked.append((binding, order_path, total_score))
        ranked.sort(key=lambda item: item[2], reverse=True)
        out: List[Tuple[Binding | None, AnchorPath | None, float]] = [(None, None, 0.0)]
        seen: set[tuple[str, str]] = set()
        for binding, order_path, total_score in ranked:
            key = (binding.source_id, binding.column_name)
            if key in seen:
                continue
            out.append((binding, order_path, total_score))
            seen.add(key)
            if len(out) >= top_k + 1:
                break
        return out
    target_priors = (order_priors_by_target or {}).get(_semantic_key(target), {})
    ranked: List[Tuple[Binding, AnchorPath | None, float]] = []
    for source in catalog.sources.values():
        for column_name in source.columns:
            score, reasons = _score_order_binding(
                target,
                source,
                column_name,
                question_tokens,
                preferred_source_ids=preferred_source_ids,
                order_grounding_priors=target_priors,
            )
            binding = Binding(
                source_id=source.source_id,
                file_name=source.file_name,
                view_name=source.raw_view_name,
                column_name=column_name,
                role="order",
                score=float(score),
                reasons=reasons,
                metadata={"target": target, "direction": direction},
            )
            order_path = _compute_single_join_path(source.source_id, candidate_source_ids, catalog, path_note="order_join_path")
            if source.source_id not in preferred_source_ids and order_path is None:
                continue
            total_score = binding.score + (order_path.score * 2.0 if order_path is not None else 0.0)
            ranked.append((binding, order_path, total_score))

    ranked.sort(key=lambda item: item[2], reverse=True)
    out: List[Tuple[Binding | None, AnchorPath | None, float]] = [(None, None, 0.0)]
    seen: set[tuple[str, str]] = set()
    for binding, order_path, total_score in ranked:
        key = (binding.source_id, binding.column_name)
        if key in seen:
            continue
        out.append((binding, order_path, total_score))
        seen.add(key)
        if len(out) >= top_k + 1:
            break
    return out


def _best_measure_binding(observable_sketch: ObservableSketch, support_source) -> Binding | None:
    operator = infer_operator_hints(" ".join(observable_sketch.operator_hints))
    aggregation = operator.get("aggregation") or (observable_sketch.measure_hints[0] if observable_sketch.measure_hints else None)
    if aggregation in {None, "", "count"}:
        return None
    measure_hint = observable_sketch.measure_hints[0] if observable_sketch.measure_hints else aggregation
    best: Binding | None = None
    for column_name, profile in support_source.column_profiles.items():
        score = name_overlap_score(measure_hint, column_name) * 10.0
        reasons: List[str] = []
        if profile.measure_like or profile.numeric_ratio >= 0.7:
            score += 4.0
            reasons.append("numeric_measure")
        else:
            score -= 3.0
            reasons.append("non_numeric_measure_penalty")
        if measure_hint.lower() in column_name.lower():
            score += 3.0
            reasons.append("measure_name_match")
        if profile.key_like:
            score -= 4.0
            reasons.append("key_like_penalty")
        if profile.time_like:
            score -= 2.0
            reasons.append("time_like_penalty")
        if profile.unique_ratio >= 0.95 and profile.numeric_ratio >= 0.7:
            score -= 1.5
            reasons.append("high_cardinality_numeric_penalty")
        if best is None or score > best.score:
            best = Binding(
                source_id=support_source.source_id,
                file_name=support_source.file_name,
                view_name=support_source.raw_view_name,
                column_name=column_name,
                role="measure",
                score=float(score),
                reasons=reasons,
                metadata={"aggregation": aggregation},
            )
    return best


def _avg_path_score(paths: List[AnchorPath]) -> float:
    if not paths:
        return 0.0
    return sum(path.score for path in paths) / len(paths)


def _output_consistency_adjustment(plan: SupportPlan, catalog: WorkspaceCatalog) -> Tuple[float, List[str]]:
    return _output_consistency_adjustment_with_hints(plan, catalog, grounding_hints=None)


def _output_consistency_adjustment_with_hints(
    plan: SupportPlan,
    catalog: WorkspaceCatalog,
    grounding_hints: Dict[str, Any] | None = None,
) -> Tuple[float, List[str]]:
    if not plan.output_bindings:
        return -10.0, ["missing_output_bindings"]
    score = 0.0
    reasons: List[str] = []
    avg_output_score = sum(binding.score for binding in plan.output_bindings) / len(plan.output_bindings)
    if avg_output_score >= 8.5:
        score += 4.0
        reasons.append("high_output_binding_confidence")
    elif avg_output_score < 7.0:
        score -= 4.0
        reasons.append("low_output_binding_confidence")

    output_source = catalog.source(plan.output_bindings[0].source_id)
    text_outputs = [binding for binding in plan.output_bindings if binding.role in {"entity", "attribute", "description", "status", "location"}]
    if text_outputs and output_source.role_hint == "dimension":
        score += 2.0
        reasons.append("dimension_output_source")
    elif text_outputs and output_source.role_hint == "fact":
        score -= 4.0
        reasons.append("fact_output_row_risk")

    if _has_duplicate_output_binding_conflict(plan):
        score -= 4.0
        reasons.append("duplicate_output_binding")

    unique_output_sources = {binding.source_id for binding in plan.output_bindings}
    if len(unique_output_sources) == 1:
        if grounding_hints and grounding_hints.get("strong_multi_source_output") and len(plan.output_bindings) > 1:
            score -= 2.0
            reasons.append("single_output_source_under_llm_multisource_hint")
        else:
            score += 1.5
            reasons.append("single_output_source")
    elif plan.output_join_paths and all(path.score >= 0.12 for path in plan.output_join_paths):
        score += 1.5
        reasons.append("well_connected_output_sources")
    else:
        score -= 2.0
        reasons.append("weak_output_connectivity")
    return score, reasons


def _filter_consistency_adjustment(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    obligation_sketch: ObligationSketch,
    catalog: WorkspaceCatalog,
) -> Tuple[float, List[str]]:
    if not observable_sketch.filter_hints and not observable_sketch.time_hints.get("years") and not observable_sketch.time_hints.get("months"):
        return 0.0, []
    score = 0.0
    reasons: List[str] = []
    if not plan.filter_bindings:
        return -5.0, ["missing_filter_bindings"]
    output_source_id = plan.output_bindings[0].source_id if plan.output_bindings else None
    support_source_id = plan.support_binding.source_id if plan.support_binding is not None else None
    for binding in plan.filter_bindings:
        source = catalog.source(binding.source_id)
        profile = source.column_profiles[binding.column_name]
        output_source_id = plan.output_bindings[0].source_id if plan.output_bindings else None
        if binding.source_id != output_source_id:
            connected = any(binding.source_id in path.path_source_ids for path in plan.filter_join_paths)
            if connected:
                score += 1.0
                reasons.append("filter_path_present")
            else:
                score -= 4.0
                reasons.append("filter_path_missing")
        if binding.role == "time":
            if profile.time_like or any(token in binding.column_name.lower() for token in ["date", "year", "time", "month"]):
                score += 2.5
                reasons.append("time_filter_type_match")
            else:
                score -= 4.0
                reasons.append("time_filter_type_mismatch")
        else:
            raw_value = binding.metadata.get("value")
            is_numeric = isinstance(raw_value, (int, float))
            if is_numeric:
                if profile.numeric_ratio >= 0.5 or profile.measure_like:
                    score += 2.5
                    reasons.append("numeric_filter_type_match")
                else:
                    score -= 4.0
                    reasons.append("numeric_filter_type_mismatch")
            else:
                value_text = str(binding.metadata.get("value_text", ""))
                if value_text:
                    if profile.text_like:
                        score += 1.5
                        reasons.append("text_filter_type_match")
                    elif profile.numeric_ratio >= 0.5:
                        score -= 3.0
                        reasons.append("text_filter_type_mismatch")
        if support_source_id and binding.source_id == support_source_id:
            score += 1.5
            reasons.append("support_side_filter")
        elif support_source_id and binding.source_id == output_source_id and obligation_sketch.probability("filter_transfer") >= 0.45:
            score -= 1.5
            reasons.append("output_side_filter_under_transfer")
    return score, reasons


def _aggregation_consistency_adjustment(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
) -> Tuple[float, List[str]]:
    aggregation = plan.operator_plan.get("aggregation")
    if not aggregation:
        return 0.0, []
    score = 0.0
    reasons: List[str] = []
    if plan.support_binding is None:
        # Direct aggregation: satisfied if a measure-role output binding exists.
        has_measure_output = any(b.role == "measure" for b in plan.output_bindings)
        if has_measure_output:
            score += 2.0
            reasons.append("direct_measure_output_binding")
            if plan.plan_kind == "direct_aggregation":
                score += 1.0
                reasons.append("family_matches_direct_aggregation")
            return score, reasons
        return -5.0, ["missing_support_for_aggregation"]
    support_source = catalog.source(plan.support_binding.source_id)
    if support_source.role_hint == "fact":
        score += 2.5
        reasons.append("fact_support_for_aggregation")
    else:
        score -= 2.0
        reasons.append("non_fact_support_for_aggregation")

    if aggregation == "count":
        if plan.plan_kind == "count_star_support":
            score += 2.0
            reasons.append("count_star_family")
        if support_source.row_count >= catalog.source(plan.output_bindings[0].source_id).row_count:
            score += 1.0
            reasons.append("count_support_cardinality_ok")
        else:
            score -= 1.0
            reasons.append("count_support_cardinality_weak")
        if plan.support_binding.source_id == plan.output_bindings[0].source_id:
            score -= 6.0
            reasons.append("same_source_count_penalty")
        if plan.anchor_binding is None or plan.anchor_binding.score < 0.12:
            score -= 5.0
            reasons.append("count_anchor_missing")
        else:
            score += 1.5
            reasons.append("count_anchor_present")
    else:
        if plan.plan_kind == "aggregation_join":
            score += 1.5
            reasons.append("aggregation_family")
        if plan.measure_binding is None:
            score -= 6.0
            reasons.append("missing_measure_binding")
        else:
            measure_source = catalog.source(plan.measure_binding.source_id)
            profile = measure_source.column_profiles[plan.measure_binding.column_name]
            if plan.measure_binding.source_id == plan.support_binding.source_id:
                score += 1.5
                reasons.append("measure_on_support_source")
            else:
                score -= 2.0
                reasons.append("measure_off_support_source")
            if profile.measure_like or profile.numeric_ratio >= 0.7:
                score += 3.0
                reasons.append("typed_measure_binding")
            else:
                score -= 5.0
                reasons.append("typed_measure_mismatch")
            if profile.key_like:
                score -= 4.0
                reasons.append("key_like_measure_penalty")
        if plan.anchor_binding is None or plan.anchor_binding.score < 0.12:
            score -= 3.0
            reasons.append("aggregation_anchor_missing")
        else:
            score += 1.0
            reasons.append("aggregation_anchor_present")
    if plan.operator_plan.get("direction"):
        score += 0.5
        reasons.append("ordered_aggregation")
        if plan.ranking_target_kind == "aggregation_value":
            score += 1.0
            reasons.append("ranking_target_matches_aggregation")
    return score, reasons


def _ordering_consistency_adjustment(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
) -> Tuple[float, List[str]]:
    if not plan.operator_plan.get("direction"):
        return 0.0, []
    score = 0.0
    reasons: List[str] = []
    target = str(plan.operator_plan.get("target", "")).strip()
    aggregation = plan.operator_plan.get("aggregation")
    output_source_id = plan.output_bindings[0].source_id if plan.output_bindings else None

    if aggregation:
        if plan.ranking_target_kind == "aggregation_value":
            score += 1.5
            reasons.append("ordering_matches_aggregation_value")
        else:
            score -= 2.0
            reasons.append("ordering_misses_aggregation_value")
        return score, reasons

    if plan.order_binding is None:
        if target:
            return -5.0, ["missing_order_binding"]
        return -1.0, ["direction_without_target"]

    if _binding_has_order_type_conflict(plan.order_binding):
        score -= 4.0
        reasons.append("order_binding_type_conflict")
    else:
        score += 2.0
        reasons.append("order_binding_grounded")

    if plan.order_binding.source_id == output_source_id:
        score += 1.0
        reasons.append("order_on_output_source")
    else:
        if plan.order_join_path is None:
            score -= 6.0
            reasons.append("order_path_missing")
        else:
            semantic, quality = _path_quality(plan.order_join_path, output_source_id, catalog)
            if quality == "weak":
                score -= 3.0
                reasons.append(f"weak_order_path:{semantic}")
            else:
                score += 1.5
                reasons.append(f"order_path:{semantic}")
            if _path_uses_output_projection_bridge(plan.order_join_path, plan.output_bindings):
                score -= 3.0
                reasons.append("order_path_via_output_projection")
    return score, reasons


def _obligation_consistency_adjustment(
    plan: SupportPlan,
    obligation_sketch: ObligationSketch,
) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []
    if obligation_sketch.probability("support_relation") >= 0.45:
        if plan.support_binding is not None and plan.anchor_binding is not None and plan.anchor_binding.score >= 0.12:
            score += 4.0
            reasons.append("support_relation_satisfied")
        else:
            score -= 8.0
            reasons.append("support_relation_missing")
    if obligation_sketch.probability("aggregation_support") >= 0.45:
        if plan.operator_plan.get("aggregation") == "count" or plan.measure_binding is not None:
            score += 3.0
            reasons.append("aggregation_support_satisfied")
        else:
            score -= 5.0
            reasons.append("aggregation_support_missing")
    if obligation_sketch.probability("filter_transfer") >= 0.45:
        if plan.filter_bindings and plan.support_binding is not None and any(binding.source_id == plan.support_binding.source_id for binding in plan.filter_bindings):
            score += 2.0
            reasons.append("filter_transfer_satisfied")
        elif plan.filter_bindings:
            score -= 2.0
            reasons.append("filter_transfer_weak")
    if obligation_sketch.probability("value_alignment") >= 0.45:
        if plan.anchor_binding is not None and (
            plan.anchor_binding.score >= 0.12
            or any(edge.get("left_transform") != "identity" or edge.get("right_transform") != "identity" for edge in plan.anchor_binding.edges)
        ):
            score += 2.0
            reasons.append("value_alignment_satisfied")
        else:
            score -= 2.0
            reasons.append("value_alignment_missing")
    if obligation_sketch.probability("multihop") >= 0.45:
        if (plan.anchor_binding is not None and len(plan.anchor_binding.edges) >= 1) or any(path.edges for path in plan.output_join_paths):
            score += 1.5
            reasons.append("multihop_satisfied")
        else:
            score -= 2.0
            reasons.append("multihop_missing")
    score += len(plan.satisfied_obligations) * 0.75
    score -= len(plan.unmet_obligations) * 2.5
    return score, reasons


def _shape_sanity_adjustment(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []
    if not plan.output_bindings:
        return score, reasons
    involved_source_ids = {binding.source_id for binding in plan.output_bindings}
    if plan.support_binding is not None:
        involved_source_ids.add(plan.support_binding.source_id)
    for binding in plan.filter_bindings:
        involved_source_ids.add(binding.source_id)
    row_counts = [catalog.source(source_id).row_count for source_id in involved_source_ids if source_id in catalog.sources]
    if row_counts:
        row_ratio = max(row_counts) / max(min(row_counts), 1)
        if not plan.operator_plan.get("aggregation") and not plan.filter_bindings and row_ratio > 20:
            score -= 3.0
            reasons.append("row_explosion_risk")
    output_source = catalog.source(plan.output_bindings[0].source_id)
    text_outputs = any(binding.role in {"entity", "attribute", "description", "status", "location"} for binding in plan.output_bindings)
    if text_outputs and output_source.role_hint == "fact":
        score -= 3.0
        reasons.append("fact_output_shape_risk")
    if plan.anchor_binding is not None:
        anchor_semantic, anchor_quality = _path_quality(plan.anchor_binding, output_source.source_id, catalog)
        if plan.anchor_binding.score < 0.12:
            score -= 3.0
            reasons.append("weak_anchor_path")
        elif plan.anchor_binding.score >= 0.35:
            score += 1.5
            reasons.append("strong_anchor_path")
        if anchor_quality == "weak":
            score -= 2.0
            reasons.append(f"weak_anchor_semantics:{anchor_semantic}")
        elif anchor_semantic in STRONG_PATH_SEMANTICS:
            score += 0.75
            reasons.append(f"structured_anchor_semantics:{anchor_semantic}")
    if plan.output_join_paths and any(path.score < 0.1 for path in plan.output_join_paths):
        score -= 2.0
        reasons.append("weak_output_join_path")
    for path in plan.filter_join_paths:
        semantic, quality = _path_quality(path, output_source.source_id, catalog)
        if path.score < 0.1:
            score -= 1.5
            reasons.append("weak_filter_join_path")
        if quality == "weak":
            score -= 1.5
            reasons.append(f"weak_filter_path_semantics:{semantic}")
        elif semantic in STRONG_PATH_SEMANTICS:
            score += 0.5
            reasons.append(f"structured_filter_path_semantics:{semantic}")
    if plan.order_join_path is not None:
        semantic, quality = _path_quality(plan.order_join_path, output_source.source_id, catalog)
        if quality == "weak":
            score -= 1.5
            reasons.append(f"weak_order_path_semantics:{semantic}")
        elif semantic in STRONG_PATH_SEMANTICS:
            score += 0.5
            reasons.append(f"structured_order_path_semantics:{semantic}")
    if plan.operator_plan.get("aggregation") and plan.support_binding is not None:
        support_source = catalog.source(plan.support_binding.source_id)
        if support_source.row_count >= output_source.row_count:
            score += 1.0
            reasons.append("aggregation_cardinality_plausible")
        elif support_source.source_id != output_source.source_id:
            score -= 1.5
            reasons.append("aggregation_cardinality_implausible")
    deduped: List[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    reasons = deduped
    return score, reasons


def _joint_rerank_adjustment(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    obligation_sketch: ObligationSketch,
    catalog: WorkspaceCatalog,
    grounding_hints: Dict[str, Any] | None = None,
) -> Tuple[float, Dict[str, float]]:
    output_score, _ = _output_consistency_adjustment_with_hints(plan, catalog, grounding_hints=grounding_hints)
    filter_score, _ = _filter_consistency_adjustment(plan, observable_sketch, obligation_sketch, catalog)
    aggregation_score, _ = _aggregation_consistency_adjustment(plan, observable_sketch, catalog)
    ordering_score, _ = _ordering_consistency_adjustment(plan, observable_sketch, catalog)
    obligation_score, _ = _obligation_consistency_adjustment(plan, obligation_sketch)
    shape_score, _ = _shape_sanity_adjustment(plan, observable_sketch, catalog)
    breakdown = {
        "output_consistency": round(output_score, 4),
        "filter_consistency": round(filter_score, 4),
        "aggregation_consistency": round(aggregation_score, 4),
        "ordering_consistency": round(ordering_score, 4),
        "obligation_consistency": round(obligation_score, 4),
        "shape_sanity": round(shape_score, 4),
    }
    return sum(breakdown.values()), breakdown


def _output_source_has_relational_support(
    plan: SupportPlan,
    source_id: str,
    observable_sketch: ObservableSketch,
    catalog: WorkspaceCatalog,
    grounding_hints: Dict[str, Any] | None = None,
) -> bool:
    if source_id not in catalog.sources:
        return False
    if plan.filter_bindings:
        if any(binding.source_id == source_id for binding in plan.filter_bindings):
            return True
        if any(catalog.find_best_path(source_id, binding.source_id, max_hops=2) for binding in plan.filter_bindings):
            return True
    if observable_sketch.filter_hints and grounding_hints:
        filter_prior_sources = {
            str(candidate.get("source_id", "")).strip()
            for priors in grounding_hints.get("filter_priors_by_attribute", {}).values()
            for candidate in priors.values()
            if not candidate.get("is_dummy_likely")
            and float(candidate.get("confidence", 0.0)) >= 0.3
        }
        if source_id in filter_prior_sources:
            return True
        if any(catalog.find_best_path(source_id, prior_source_id, max_hops=2) for prior_source_id in filter_prior_sources):
            return True
    if plan.order_binding is not None:
        if plan.order_binding.source_id == source_id:
            return True
        if catalog.find_best_path(source_id, plan.order_binding.source_id, max_hops=2):
            return True
    if plan.support_binding is not None:
        if plan.support_binding.source_id == source_id:
            return True
        if catalog.find_best_path(source_id, plan.support_binding.source_id, max_hops=2):
            return True
    if observable_sketch.filter_hints or observable_sketch.measure_hints or observable_sketch.order_hint.get("target"):
        neighbors = catalog.join_neighbors(source_id)
        if any(
            catalog.source(edge.left_source_id if edge.right_source_id == source_id else edge.right_source_id).role_hint == "fact"
            for edge in neighbors
        ):
            return True
    return False


def _calibration_guardrail_state(grounding_hints: Dict[str, Any] | None) -> tuple[bool, bool]:
    calibration_mode = str((grounding_hints or {}).get("calibration_mode", "strict")).strip().lower()
    guardrails_enabled = calibration_mode not in {"off", "no_calibration"}
    relaxed_mode = guardrails_enabled and calibration_mode == "relaxed"
    return guardrails_enabled, relaxed_mode


def _hard_invalid_reasons(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    obligation_sketch: ObligationSketch,
    catalog: WorkspaceCatalog,
    grounding_hints: Dict[str, Any] | None = None,
) -> List[str]:
    reasons: List[str] = []
    calibration_enabled, relaxed_mode = _calibration_guardrail_state(grounding_hints)
    aggregation = plan.operator_plan.get("aggregation")
    output_source_id = plan.output_bindings[0].source_id if plan.output_bindings else None
    has_ordering = bool(plan.operator_plan.get("direction"))
    order_target = str(plan.operator_plan.get("target", "")).strip()

    if _has_duplicate_output_binding_conflict(plan):
        reasons.append("duplicate_output_binding")
    if grounding_hints and grounding_hints.get("strong_multi_source_output") and len({binding.source_id for binding in plan.output_bindings}) == 1 and len(plan.output_bindings) > 1:
        reasons.append("collapsed_output_sources_against_llm_hint")
    if grounding_hints:
        for binding in plan.output_bindings:
            slot_label = str(binding.metadata.get("slot_label", "")).strip()
            slot_priors = grounding_hints.get("output_priors_by_slot", {}).get(slot_label, {})
            prior = _selected_output_prior(binding, grounding_hints)
            lexical_overlap = name_overlap_score(slot_label, binding.column_name) if slot_label else 0.0
            has_world_support = _output_source_has_relational_support(
                plan,
                binding.source_id,
                observable_sketch,
                catalog,
                grounding_hints,
            )
            if calibration_enabled and (not relaxed_mode) and slot_priors and prior is None and (_has_strong_supported_prior(slot_priors) or lexical_overlap < 0.15) and not has_world_support:
                reasons.append("selected_output_binding_unsupported_by_calibrated_prior")
                break
            if prior and prior.get("is_dummy_likely"):
                reasons.append("selected_dummy_output_binding")
                break
            if calibration_enabled and (not relaxed_mode) and prior and prior.get("cross_source_join_risk") and binding.source_id != output_source_id:
                reasons.append("selected_output_binding_without_join_evidence")
                break

    if aggregation and plan.plan_kind == "direct_join":
        has_measure_output = any(binding.role == "measure" for binding in plan.output_bindings)
        if not has_measure_output:
            reasons.append("direct_join_without_measure_output_under_aggregation")

    if obligation_sketch.probability("existence_check") >= 0.45 or plan.operator_plan.get("exists"):
        if plan.support_binding is None:
            reasons.append("missing_existence_support")

    if has_ordering and order_target and plan.order_binding is not None:
        order_priors = grounding_hints.get("order_priors_by_target", {}).get(_semantic_key(order_target), {}) if grounding_hints else {}
        order_prior = _selected_order_prior(plan.order_binding, order_target, grounding_hints)
        if calibration_enabled and order_priors and order_prior is None and ((not relaxed_mode) or _has_strong_nonfallback_prior(order_priors)):
            reasons.append("selected_order_binding_unsupported_by_calibrated_prior")
        if plan.order_binding.source_id != output_source_id and plan.order_join_path is None:
            reasons.append("order_source_not_connected")
        if calibration_enabled and (not relaxed_mode) and order_prior and order_prior.get("cross_source_join_risk") and plan.order_binding.source_id != output_source_id:
            reasons.append("selected_order_binding_without_join_evidence")
        if order_prior and order_prior.get("is_dummy_likely") and _binding_has_order_type_conflict(plan.order_binding):
            reasons.append("selected_low_confidence_order_binding")
        elif calibration_enabled and (not relaxed_mode) and order_prior and order_prior.get("is_uncertain") and _binding_has_order_type_conflict(plan.order_binding):
            reasons.append("selected_low_confidence_order_binding")
    elif has_ordering and order_target:
        order_priors = grounding_hints.get("order_priors_by_target", {}).get(_semantic_key(order_target), {}) if grounding_hints else {}
        if calibration_enabled and _has_strong_nonfallback_prior(order_priors):
            reasons.append("missing_order_binding_despite_calibrated_prior")

    if plan.plan_kind == "filter_join":
        for binding in plan.filter_bindings:
            filter_prior = _selected_filter_prior(binding, grounding_hints)
            if _binding_has_filter_type_conflict(binding):
                reasons.append("filter_binding_type_conflict")
            if _filter_binding_key_like_misuse(binding, catalog):
                reasons.append("filter_binding_key_like_misuse")
            if _filter_binding_scale_mismatch(binding, catalog):
                reasons.append("filter_binding_scale_mismatch")
            if filter_prior and filter_prior.get("is_dummy_likely"):
                reasons.append("selected_low_confidence_filter_binding")
            elif calibration_enabled and (not relaxed_mode) and filter_prior and filter_prior.get("is_uncertain"):
                reasons.append("selected_low_confidence_filter_binding")
            if calibration_enabled and (not relaxed_mode) and filter_prior and filter_prior.get("cross_source_join_risk") and binding.source_id != output_source_id:
                reasons.append("selected_filter_binding_without_join_evidence")
            if binding.source_id != output_source_id:
                connected_path = next((path for path in plan.filter_join_paths if binding.source_id in path.path_source_ids), None)
                if connected_path is None:
                    reasons.append("filter_source_not_connected")
                    continue
                semantic, quality = _path_quality(connected_path, output_source_id, catalog)
                if semantic == "attribute_echo_path":
                    reasons.append("filter_path_attribute_echo")
                if _path_uses_output_projection_bridge(connected_path, plan.output_bindings):
                    reasons.append("filter_path_via_output_projection")
                elif quality == "weak" and connected_path.score < 0.08:
                    reasons.append("filter_path_structurally_weak")

    if plan.plan_kind == "aggregation_join":
        if aggregation != "count" and plan.measure_binding is None:
            reasons.append("aggregation_join_missing_measure")
        if plan.anchor_binding is None or plan.anchor_binding.score < 0.12:
            reasons.append("aggregation_join_missing_anchor")
        elif _path_semantics(plan.anchor_binding, output_source_id, catalog) == "attribute_echo_path":
            reasons.append("aggregation_join_attribute_echo_anchor")
        if plan.operator_plan.get("direction") and plan.ranking_target_kind != "aggregation_value":
            reasons.append("aggregation_join_wrong_ranking_target")
        if plan.support_binding is not None and plan.output_bindings and plan.support_binding.source_id == plan.output_bindings[0].source_id:
            reasons.append("aggregation_join_same_source_support")

    if plan.plan_kind == "count_star_support":
        if not plan.evidence_source_ids:
            reasons.append("count_star_missing_evidence")
        if plan.anchor_binding is None or plan.anchor_binding.score < 0.12:
            reasons.append("count_star_missing_anchor")
        elif _path_semantics(plan.anchor_binding, output_source_id, catalog) == "attribute_echo_path":
            reasons.append("count_star_attribute_echo_anchor")
        if plan.support_binding is not None and plan.output_bindings and plan.support_binding.source_id == plan.output_bindings[0].source_id:
            reasons.append("count_star_same_source_support")

    if obligation_sketch.probability("aggregation_support") >= 0.45 and aggregation and plan.measure_binding is None and plan.plan_kind not in {"count_star_support", "direct_aggregation"}:
        reasons.append("aggregation_support_unsatisfied_for_family")

    deduped: List[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    return deduped


def _semantic_complete_reasons(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    obligation_sketch: ObligationSketch,
    catalog: WorkspaceCatalog,
    grounding_hints: Dict[str, Any] | None = None,
) -> List[str]:
    missing: List[str] = []
    calibration_enabled, _ = _calibration_guardrail_state(grounding_hints)
    aggregation = plan.operator_plan.get("aggregation")
    output_source_id = plan.output_bindings[0].source_id if plan.output_bindings else None
    has_ordering = bool(plan.operator_plan.get("direction"))
    order_target = str(plan.operator_plan.get("target", "")).strip()

    if _has_duplicate_output_binding_conflict(plan):
        missing.append("duplicate_output_binding")
    if grounding_hints and grounding_hints.get("strong_multi_source_output") and len({binding.source_id for binding in plan.output_bindings}) == 1 and len(plan.output_bindings) > 1:
        missing.append("collapsed_output_sources_against_llm_hint")
    if grounding_hints:
        output_priors_by_slot = grounding_hints.get("output_priors_by_slot", {})
        for binding in plan.output_bindings:
            slot_label = str(binding.metadata.get("slot_label", "")).strip()
            if not slot_label:
                continue
            slot_priors = output_priors_by_slot.get(slot_label, {})
            prior = slot_priors.get((binding.source_id, binding.column_name))
            lexical_overlap = name_overlap_score(slot_label, binding.column_name) if slot_label else 0.0
            has_world_support = _output_source_has_relational_support(
                plan,
                binding.source_id,
                observable_sketch,
                catalog,
                grounding_hints,
            )
            if calibration_enabled and slot_priors and prior is None and (_has_strong_supported_prior(slot_priors) or lexical_overlap < 0.15) and not has_world_support:
                missing.append("output_binding_not_supported_by_calibrated_prior")
                break
            if calibration_enabled and _is_semantically_low_confidence_prior(prior):
                missing.append("low_confidence_output_binding")
                break
        filter_priors_by_attribute = grounding_hints.get("filter_priors_by_attribute", {})
        for binding in plan.filter_bindings:
            filter_key = _filter_attribute_key(binding.metadata)
            prior = filter_priors_by_attribute.get(filter_key, {}).get((binding.source_id, binding.column_name))
            if prior is None:
                prior = filter_priors_by_attribute.get("*", {}).get((binding.source_id, binding.column_name))
            if calibration_enabled and _is_semantically_low_confidence_prior(prior):
                missing.append("low_confidence_filter_binding")
                break

    if has_ordering and order_target:
        if plan.order_binding is None:
            missing.append("missing_order_binding")
        else:
            order_priors = grounding_hints.get("order_priors_by_target", {}).get(_semantic_key(order_target), {}) if grounding_hints else {}
            order_prior = _selected_order_prior(plan.order_binding, order_target, grounding_hints)
            if calibration_enabled and order_priors and order_prior is None:
                missing.append("order_binding_not_supported_by_calibrated_prior")
            if calibration_enabled and _is_semantically_low_confidence_prior(order_prior):
                missing.append("low_confidence_order_binding")
            if _binding_has_order_type_conflict(plan.order_binding):
                missing.append("order_binding_type_conflict")
            if plan.order_binding.source_id != output_source_id:
                if plan.order_join_path is None:
                    missing.append("missing_order_path")
                else:
                    semantic, quality = _path_quality(plan.order_join_path, output_source_id, catalog)
                    if semantic in WEAK_PATH_SEMANTICS:
                        missing.append(f"weak_order_path:{semantic}")
                    if _path_uses_output_projection_bridge(plan.order_join_path, plan.output_bindings):
                        missing.append("order_path_via_output_projection")
                    if quality == "weak":
                        missing.append("weak_order_path_quality")
                    if plan.order_join_path.score < 0.15:
                        missing.append("weak_order_path_score")

    if plan.plan_kind == "filter_join":
        if not plan.filter_bindings:
            missing.append("missing_filter_bindings")
        for binding in plan.filter_bindings:
            if _binding_has_filter_type_conflict(binding):
                missing.append("filter_binding_type_conflict")
            if _filter_binding_key_like_misuse(binding, catalog):
                missing.append("filter_binding_key_like_misuse")
            if _filter_binding_scale_mismatch(binding, catalog):
                missing.append("filter_binding_scale_mismatch")
            if binding.source_id != output_source_id:
                connected_path = next((path for path in plan.filter_join_paths if binding.source_id in path.path_source_ids), None)
                if connected_path is None:
                    missing.append("missing_filter_path")
                    continue
                semantic, quality = _path_quality(connected_path, output_source_id, catalog)
                if semantic in WEAK_PATH_SEMANTICS:
                    missing.append(f"weak_filter_path:{semantic}")
                if _path_uses_output_projection_bridge(connected_path, plan.output_bindings):
                    missing.append("filter_path_via_output_projection")
                if quality == "weak":
                    missing.append("weak_filter_path_quality")
                if connected_path.score < 0.15:
                    missing.append("weak_filter_path_score")
                filter_source = catalog.source(binding.source_id)
                if output_source_id is not None:
                    output_source = catalog.source(output_source_id)
                    if filter_source.row_count <= output_source.row_count and semantic not in STRONG_PATH_SEMANTICS:
                        missing.append("filter_source_not_evidence_like")
        if obligation_sketch.probability("filter_transfer") >= 0.45 and plan.support_binding is not None:
            if not any(binding.source_id == plan.support_binding.source_id for binding in plan.filter_bindings):
                missing.append("filter_transfer_not_realized")

    if plan.plan_kind in {"aggregation_join", "count_star_support"}:
        if plan.support_binding is None:
            missing.append("missing_support_binding")
        else:
            support_source = catalog.source(plan.support_binding.source_id)
            if support_source.role_hint != "fact":
                missing.append("support_not_fact_like")
            if output_source_id is not None:
                output_source = catalog.source(output_source_id)
                if support_source.source_id != output_source.source_id and support_source.row_count < output_source.row_count:
                    missing.append("support_not_evidence_grain")
        if plan.anchor_binding is None or plan.anchor_binding.score < 0.12:
            missing.append("missing_or_weak_anchor")
        elif output_source_id is not None:
            anchor_semantic, anchor_quality = _path_quality(plan.anchor_binding, output_source_id, catalog)
            if anchor_quality == "weak":
                missing.append(f"weak_anchor_semantics:{anchor_semantic}")
            if _path_uses_output_projection_bridge(plan.anchor_binding, plan.output_bindings):
                missing.append("anchor_path_via_output_projection")
        if aggregation == "count":
            if not plan.evidence_source_ids:
                missing.append("missing_evidence_source")
            if plan.aggregation_unit_kind != "evidence_rows":
                missing.append("wrong_count_unit")
            if plan.support_binding is not None and output_source_id is not None:
                support_source = catalog.source(plan.support_binding.source_id)
                output_source = catalog.source(output_source_id)
                if support_source.source_id != output_source.source_id and support_source.row_count <= output_source.row_count:
                    missing.append("count_support_not_expanding_grain")
        else:
            if plan.measure_binding is None:
                missing.append("missing_measure_binding")
            else:
                measure_source = catalog.source(plan.measure_binding.source_id)
                profile = measure_source.column_profiles[plan.measure_binding.column_name]
                if profile.key_like:
                    missing.append("measure_is_key_like")
                if not (profile.measure_like or profile.numeric_ratio >= 0.7):
                    missing.append("measure_not_numeric")
                if plan.support_binding is not None and plan.measure_binding.source_id != plan.support_binding.source_id:
                    missing.append("measure_off_support_source")
        if plan.operator_plan.get("direction") and plan.ranking_target_kind != "aggregation_value":
            missing.append("wrong_ranking_target")

    if plan.plan_kind == "direct_aggregation":
        if not any(binding.role == "measure" for binding in plan.output_bindings):
            missing.append("direct_aggregation_without_measure_output")

    if plan.plan_kind == "direct_join":
        if observable_sketch.filter_hints and any(binding.source_id != output_source_id for binding in plan.filter_bindings):
            missing.append("cross_source_filter_without_filter_family")
    if obligation_sketch.probability("existence_check") >= 0.45 or plan.operator_plan.get("exists"):
        if plan.support_binding is None:
            missing.append("missing_existence_support")
    if obligation_sketch.probability("intersection_requirement") >= 0.45 or plan.operator_plan.get("intersection"):
        if len(plan.filter_bindings) < 2:
            missing.append("missing_intersection_filters")

    deduped: List[str] = []
    for item in missing:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _plan_sort_key(plan: SupportPlan) -> tuple[int, int, int, float]:
    score = plan.plan_score
    if score is None:
        return (1, 1, 999, float("-inf"))
    return (
        1 if score.hard_invalid else 0,
        0 if score.semantic_complete else 1,
        int(score.semantic_gap_count),
        -float(score.total),
    )


def _family_metadata(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
) -> Dict[str, Any]:
    aggregation = plan.operator_plan.get("aggregation")
    evidence_source_ids = sorted(
        {
            *(binding.source_id for binding in plan.filter_bindings),
            *(
                [plan.support_binding.source_id]
                if plan.support_binding is not None
                else []
            ),
        }
    )
    if aggregation == "count":
        aggregation_mode = "count_star_support" if plan.support_binding is not None else "count_star_direct"
        aggregation_unit_kind = "evidence_rows"
    elif aggregation:
        aggregation_mode = "explicit_measure_support" if plan.support_binding is not None else "explicit_measure_direct"
        aggregation_unit_kind = "measure_column"
    else:
        aggregation_mode = None
        aggregation_unit_kind = None

    ranking_target_kind = None
    if plan.operator_plan.get("direction"):
        if aggregation:
            ranking_target_kind = "aggregation_value"
        elif plan.order_binding is not None:
            ranking_target_kind = "order_binding"
        elif any(binding.role == "measure" for binding in plan.output_bindings):
            ranking_target_kind = "measure_output"
        else:
            ranking_target_kind = "output_value"

    return {
        "evidence_source_ids": evidence_source_ids,
        "aggregation_mode": aggregation_mode,
        "aggregation_unit_kind": aggregation_unit_kind,
        "aggregation_anchor_source_id": plan.output_bindings[0].source_id if plan.output_bindings and aggregation else None,
        "ranking_target_kind": ranking_target_kind,
    }


def _classify_plan_kind(plan: SupportPlan) -> str:
    if plan.operator_plan.get("aggregation"):
        return "aggregation_join"
    if plan.filter_bindings:
        return "filter_join"
    if plan.support_binding is not None:
        return "support_join"
    return "direct_join"


def _finalize_plan_candidate(
    plan: SupportPlan,
    observable_sketch: ObservableSketch,
    obligation_sketch: ObligationSketch,
    catalog: WorkspaceCatalog,
    *,
    family_name: str,
    search_log_entry: Dict[str, Any],
    grounding_hints: Dict[str, Any] | None = None,
    family_prior_bonus: float = 0.0,
    screening_mode: str = "full",
) -> Tuple[SupportPlan, Dict[str, Any]]:
    if screening_mode not in {"full", "off"}:
        raise ValueError(f"Unsupported screening_mode: {screening_mode}")
    trace = verify_support_plan(plan, observable_sketch, obligation_sketch, catalog)
    satisfied, unmet = obligations_from_trace(trace, obligation_sketch)
    plan.satisfied_obligations = satisfied
    plan.unmet_obligations = unmet
    plan.plan_kind = family_name
    metadata = _family_metadata(plan, observable_sketch)
    plan.evidence_source_ids = metadata["evidence_source_ids"]
    plan.aggregation_mode = metadata["aggregation_mode"]
    plan.aggregation_unit_kind = metadata["aggregation_unit_kind"]
    plan.aggregation_anchor_source_id = metadata["aggregation_anchor_source_id"]
    plan.ranking_target_kind = metadata["ranking_target_kind"]
    plan.confidence += family_prior_bonus
    trace_bonus = sum(item["score"] for item in trace if item["passed"]) * 2.0
    plan.confidence += trace_bonus
    rerank_breakdown = {
        "output_consistency": 0.0,
        "filter_consistency": 0.0,
        "aggregation_consistency": 0.0,
        "ordering_consistency": 0.0,
        "obligation_consistency": 0.0,
        "shape_sanity": 0.0,
    }
    joint_bonus = 0.0
    hard_invalid_reasons: List[str] = []
    hard_invalid = False
    semantic_complete_reasons: List[str] = []
    semantic_complete = True
    if screening_mode == "full":
        joint_bonus, rerank_breakdown = _joint_rerank_adjustment(
            plan,
            observable_sketch,
            obligation_sketch,
            catalog,
            grounding_hints=grounding_hints,
        )
        hard_invalid_reasons = _hard_invalid_reasons(
            plan,
            observable_sketch,
            obligation_sketch,
            catalog,
            grounding_hints=grounding_hints,
        )
        hard_invalid = bool(hard_invalid_reasons)
        semantic_complete_reasons = _semantic_complete_reasons(
            plan,
            observable_sketch,
            obligation_sketch,
            catalog,
            grounding_hints=grounding_hints,
        )
        semantic_complete = (not hard_invalid) and (not semantic_complete_reasons)
        if hard_invalid:
            plan.confidence -= 1000.0
        plan.confidence += joint_bonus
    base_retrieval_score = round(plan.confidence - joint_bonus - trace_bonus - family_prior_bonus + (1000.0 if hard_invalid else 0.0), 4)
    plan.plan_score = PlanScore(
        family_name=family_name,
        base_retrieval_score=base_retrieval_score,
        output_consistency=rerank_breakdown["output_consistency"],
        filter_consistency=rerank_breakdown["filter_consistency"],
        aggregation_consistency=rerank_breakdown["aggregation_consistency"],
        ordering_consistency=rerank_breakdown["ordering_consistency"],
        obligation_consistency=rerank_breakdown["obligation_consistency"],
        shape_sanity=rerank_breakdown["shape_sanity"],
        semantic_complete=semantic_complete,
        semantic_gap_count=len(semantic_complete_reasons),
        semantic_complete_reasons=semantic_complete_reasons,
        hard_invalid=hard_invalid,
        hard_invalid_reasons=hard_invalid_reasons,
        total=round(plan.confidence, 4),
    )
    plan.notes.append(f"family={family_name}")
    for key, value in metadata.items():
        if value is not None and value != []:
            plan.notes.append(f"{key}={value}")
    if family_prior_bonus:
        plan.notes.append(f"llm_family_bonus={family_prior_bonus:.4f}")
    plan.notes.append(f"semantic_complete={semantic_complete}")
    plan.notes.append(f"semantic_gap_count={len(semantic_complete_reasons)}")
    for reason in semantic_complete_reasons:
        plan.notes.append(f"semantic_missing={reason}")
    plan.notes.append(f"hard_invalid={hard_invalid}")
    for reason in hard_invalid_reasons:
        plan.notes.append(f"hard_invalid_reason={reason}")
    plan.notes.append(f"joint_rerank_total={joint_bonus:.4f}")
    for key, value in rerank_breakdown.items():
        plan.notes.append(f"{key}={value:.4f}")
    search_log_entry["joint_rerank_total"] = round(joint_bonus, 4)
    search_log_entry["family"] = family_name
    search_log_entry["aggregation_mode"] = metadata["aggregation_mode"]
    if family_prior_bonus:
        search_log_entry["llm_family_bonus"] = round(family_prior_bonus, 4)
    search_log_entry["semantic_complete"] = semantic_complete
    search_log_entry["semantic_gap_count"] = len(semantic_complete_reasons)
    search_log_entry["semantic_complete_reasons"] = semantic_complete_reasons
    search_log_entry["hard_invalid"] = hard_invalid
    search_log_entry["hard_invalid_reasons"] = hard_invalid_reasons
    search_log_entry["screening_mode"] = screening_mode
    return plan, search_log_entry


def _all_filter_sources_connected(
    filter_bindings: List[Binding],
    connected_source_ids: List[str],
    filter_join_paths: List[AnchorPath],
) -> bool:
    connected = set(connected_source_ids)
    for path in filter_join_paths:
        connected.update(path.path_source_ids)
    return all(binding.source_id in connected for binding in filter_bindings)


def search_support_plans(
    instruction: str,
    observable_sketch: ObservableSketch,
    obligation_sketch: ObligationSketch,
    catalog: WorkspaceCatalog,
    llm_grounding: Dict[str, Any] | None = None,
    grounding_mode: str = "full",
    screening_mode: str = "full",
) -> Dict[str, Any]:
    question_tok = tokenize(instruction)
    # Extract LLM grounding sets for scoring
    llm_output_set: set[tuple[str, str]] | None = None
    llm_filter_set: set[tuple[str, str]] | None = None
    llm_family: str | None = None
    llm_family_confidence = 0.0
    grounding_hints: Dict[str, Any] | None = None
    if llm_grounding:
        from .grounding import (
            calibrate_grounding_hints,
            extract_suggested_join_specs,
            grounding_to_binding_set,
            grounding_to_search_hints,
        )
        llm_output_set, llm_filter_set, llm_family = grounding_to_binding_set(llm_grounding)
        grounding_hints = grounding_to_search_hints(llm_grounding)
        if grounding_mode == "full":
            grounding_hints = calibrate_grounding_hints(
                grounding_hints,
                catalog,
                observable_sketch,
                instruction,
                extract_suggested_join_specs(llm_grounding),
            )
        else:
            grounding_hints = dict(grounding_hints)
            grounding_hints.setdefault("query_family", llm_grounding.get("query_family"))
            grounding_hints.setdefault("query_family_confidence", float(llm_grounding.get("query_family_confidence", 0.0) or 0.0))
            grounding_hints.setdefault("cross_source_join_risk", False)
            grounding_hints.setdefault("strong_multi_source_output", False)
            grounding_hints.setdefault("calibration_rules_fired", [])
            grounding_hints.setdefault("calibration_mode", grounding_mode)
            grounding_hints.setdefault("fallback_injected", {"output_slots": [], "filter_attributes": [], "order_targets": []})
        llm_family = grounding_hints.get("query_family")
        llm_family_confidence = float(grounding_hints.get("query_family_confidence", 0.0) or 0.0)
    operator_plan = infer_operator_hints(instruction)
    # Merge LLM-parsed order_hint into operator_plan (LLM values take priority)
    if observable_sketch.order_hint:
        if observable_sketch.order_hint.get("direction") and not operator_plan.get("direction"):
            od = normalize_operator_direction(observable_sketch.order_hint["direction"])
            if od:
                operator_plan["direction"] = od
        if observable_sketch.order_hint.get("limit") and not operator_plan.get("limit"):
            operator_plan["limit"] = observable_sketch.order_hint["limit"]
        if observable_sketch.order_hint.get("target"):
            operator_plan.setdefault("target", observable_sketch.order_hint["target"])
    output_candidates = _output_plan_candidates(
        observable_sketch,
        catalog,
        question_tok,
        top_k=12,
        llm_output_set=llm_output_set,
        llm_output_priors_by_slot=(grounding_hints or {}).get("output_priors_by_slot"),
        operator_plan=operator_plan,
        grounding_hints=grounding_hints,
    )
    plan_candidates: List[SupportPlan] = []
    search_log: List[Dict[str, Any]] = []
    support_required = (
        obligation_sketch.probability("support_relation") >= 0.45
        or obligation_sketch.probability("aggregation_support") >= 0.45
        or obligation_sketch.probability("existence_check") >= 0.45
        or obligation_sketch.probability("intersection_requirement") >= 0.45
    )
    pure_projection_query = bool(
        not observable_sketch.filter_hints
        and not observable_sketch.time_hints.get("years")
        and not observable_sketch.time_hints.get("months")
        and not operator_plan.get("aggregation")
        and not operator_plan.get("direction")
        and not operator_plan.get("exists")
        and not operator_plan.get("intersection")
    )
    if operator_plan.get("exists") or operator_plan.get("intersection"):
        support_required = True
    if (not pure_projection_query) and llm_family in {"support_join", "aggregation_join", "count_star_support"} and llm_family_confidence >= 0.55:
        support_required = True

    for output_bindings, output_join_paths, output_score in output_candidates:
        primary_output_source_id = output_bindings[0].source_id
        output_source_ids = [binding.source_id for binding in output_bindings]
        output_world_source_ids = _reachable_sources(output_source_ids, catalog, max_hops=2)

        direct_filter_assignments = _filter_assignment_candidates(
            observable_sketch,
            catalog,
            question_tok,
            output_world_source_ids,
            per_hint_top_k=5,
            assignment_top_k=12,
            llm_filter_set=llm_filter_set,
            llm_filter_priors_by_attribute=(grounding_hints or {}).get("filter_priors_by_attribute"),
        )
        for filter_bindings, filter_score in direct_filter_assignments:
            filter_join_paths = _compute_filter_join_paths(filter_bindings, output_source_ids, catalog)
            if not _all_filter_sources_connected(filter_bindings, output_source_ids, filter_join_paths):
                continue
            direct_connected_source_ids = list(output_source_ids)
            for path in filter_join_paths:
                direct_connected_source_ids.extend(path.path_source_ids)
            order_candidates = _order_binding_candidates(
                operator_plan,
                catalog,
                question_tok,
                sorted(set(direct_connected_source_ids)),
                top_k=4,
                order_priors_by_target=(grounding_hints or {}).get("order_priors_by_target"),
            )
            for order_binding, order_join_path, order_score in order_candidates:
                if operator_plan.get("aggregation"):
                    family_name = "direct_aggregation"
                elif filter_bindings:
                    family_name = "filter_join"
                else:
                    family_name = "direct_join"
                family_prior_bonus = _llm_family_bonus(
                    family_name,
                    llm_family,
                    llm_family_confidence,
                    cross_source_join_risk=bool((grounding_hints or {}).get("cross_source_join_risk")),
                )
                trace_sources = set(output_source_ids)
                if order_binding is not None:
                    trace_sources.add(order_binding.source_id)
                plan = SupportPlan(
                    output_bindings=output_bindings,
                    plan_kind=family_name,
                    output_join_paths=output_join_paths,
                    filter_join_paths=filter_join_paths,
                    order_join_path=order_join_path,
                    support_binding=None,
                    anchor_binding=None,
                    evidence_bindings=[],
                    measure_binding=None,
                    order_binding=order_binding,
                    filter_bindings=filter_bindings,
                    operator_plan=dict(operator_plan),
                    confidence=output_score + (filter_score * 0.3) + (order_score * 0.3),
                    source_trace=sorted(trace_sources),
                    notes=[family_name],
                )
                plan, log_entry = _finalize_plan_candidate(
                    plan,
                    observable_sketch,
                    obligation_sketch,
                    catalog,
                    family_name=family_name,
                    grounding_hints=grounding_hints,
                    family_prior_bonus=family_prior_bonus,
                    search_log_entry={
                        "kind": "family_candidate",
                        "family_seed": "direct_or_filter",
                        "output_sources": output_source_ids,
                        "filter_sources": [binding.source_id for binding in filter_bindings],
                        "filter_path_count": len(filter_join_paths),
                        "order_source": order_binding.source_id if order_binding is not None else None,
                        "order_path_count": 1 if order_join_path is not None else 0,
                        "llm_family": llm_family,
                        "llm_family_confidence": round(llm_family_confidence, 4),
                    },
                    screening_mode=screening_mode,
                )
                plan_candidates.append(plan)
                search_log.append(log_entry)

        if not support_required:
            continue

        support_ranked: List[Tuple[Binding, AnchorPath | None, float]] = []
        for source in catalog.sources.values():
            support_score, reasons, anchor_path = _score_support_source(
                source,
                primary_output_source_id,
                obligation_sketch,
                observable_sketch,
                catalog,
                question_tok,
            )
            candidate_column = source.key_columns[0] if source.key_columns else source.columns[0]
            support_ranked.append(
                (
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name=candidate_column,
                        role="support",
                        score=float(support_score),
                        reasons=reasons,
                        metadata={},
                    ),
                    anchor_path,
                    support_score,
                )
            )
        support_ranked.sort(key=lambda item: item[2], reverse=True)
        for support_binding, anchor_binding, support_score in support_ranked[:12]:
            connected_source_ids = list(output_source_ids) + [support_binding.source_id]
            if anchor_binding is not None:
                connected_source_ids.extend(anchor_binding.path_source_ids)
            filter_assignments = _filter_assignment_candidates(
                observable_sketch,
                catalog,
                question_tok,
                connected_source_ids,
                per_hint_top_k=5,
                assignment_top_k=12,
                llm_filter_set=llm_filter_set,
                llm_filter_priors_by_attribute=(grounding_hints or {}).get("filter_priors_by_attribute"),
            )
            for filter_bindings, filter_score in filter_assignments:
                filter_join_paths = _compute_filter_join_paths(filter_bindings, connected_source_ids, catalog)
                if not _all_filter_sources_connected(filter_bindings, connected_source_ids, filter_join_paths):
                    continue
                measure_binding = _best_measure_binding(observable_sketch, catalog.source(support_binding.source_id))
                enriched_connected_source_ids = list(connected_source_ids)
                for path in filter_join_paths:
                    enriched_connected_source_ids.extend(path.path_source_ids)
                order_candidates = _order_binding_candidates(
                    operator_plan,
                    catalog,
                    question_tok,
                    sorted(set(enriched_connected_source_ids)),
                    top_k=4,
                    order_priors_by_target=(grounding_hints or {}).get("order_priors_by_target"),
                )
                for order_binding, order_join_path, order_score in order_candidates:
                    if operator_plan.get("aggregation") == "count":
                        family_name = "count_star_support"
                    elif operator_plan.get("aggregation"):
                        family_name = "aggregation_join"
                    elif filter_bindings:
                        family_name = "filter_join"
                    else:
                        family_name = "support_join"
                    family_prior_bonus = _llm_family_bonus(
                        family_name,
                        llm_family,
                        llm_family_confidence,
                        cross_source_join_risk=bool((grounding_hints or {}).get("cross_source_join_risk")),
                    )
                    trace_sources = set(output_source_ids) | {support_binding.source_id}
                    if order_binding is not None:
                        trace_sources.add(order_binding.source_id)
                    plan = SupportPlan(
                        output_bindings=output_bindings,
                        plan_kind=family_name,
                        output_join_paths=output_join_paths,
                        filter_join_paths=filter_join_paths,
                        order_join_path=order_join_path,
                        support_binding=support_binding,
                        anchor_binding=anchor_binding,
                        evidence_bindings=[],
                        measure_binding=measure_binding,
                        order_binding=order_binding,
                        filter_bindings=filter_bindings,
                        operator_plan=dict(operator_plan),
                        confidence=output_score + support_score + (filter_score * 0.3) + (order_score * 0.3),
                        source_trace=sorted(trace_sources),
                        notes=[family_name],
                    )
                    plan, log_entry = _finalize_plan_candidate(
                        plan,
                        observable_sketch,
                        obligation_sketch,
                        catalog,
                        family_name=family_name,
                        grounding_hints=grounding_hints,
                        family_prior_bonus=family_prior_bonus,
                        search_log_entry={
                            "kind": "family_candidate",
                            "family_seed": "support_or_aggregation",
                            "output_sources": output_source_ids,
                            "support_source": support_binding.source_id,
                            "anchor_score": anchor_binding.score if anchor_binding is not None else 0.0,
                            "filter_sources": [binding.source_id for binding in filter_bindings],
                            "filter_path_count": len(filter_join_paths),
                            "order_source": order_binding.source_id if order_binding is not None else None,
                            "order_path_count": 1 if order_join_path is not None else 0,
                            "llm_family": llm_family,
                            "llm_family_confidence": round(llm_family_confidence, 4),
                        },
                        screening_mode=screening_mode,
                    )
                    plan_candidates.append(plan)
                    search_log.append(log_entry)

    plan_candidates.sort(key=_plan_sort_key)
    family_best: Dict[str, List[SupportPlan]] = {}
    for plan in plan_candidates:
        if plan.plan_kind not in family_best:
            family_best[plan.plan_kind] = []
        # Keep top-2 per family for diversity
        if len(family_best[plan.plan_kind]) < 2:
            family_best[plan.plan_kind].append(plan)
    # Also keep top-3 non-family plans (all families together)
    all_candidates = sorted(plan_candidates, key=_plan_sort_key)
    family_best_candidates = all_candidates[:8]
    best_plan = family_best_candidates[0] if family_best_candidates else SupportPlan(output_bindings=[], confidence=0.0, unmet_obligations=["support_relation"])
    return {
        "best_plan": best_plan,
        "family_best_candidates": family_best_candidates[:8],
        "top_plan_candidates": plan_candidates[:8],
        "candidates_considered": len(plan_candidates),
        "search_log": search_log[:24],
        "calibrated_grounding_hints": grounding_hints,
    }
