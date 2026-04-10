from __future__ import annotations

from typing import Any, Dict, List


def _strong_prior_count(priors_by_group: Dict[str, Any]) -> int:
    count = 0
    for priors in priors_by_group.values():
        if not isinstance(priors, dict):
            continue
        if any(
            isinstance(candidate, dict)
            and candidate.get("is_primary")
            and not candidate.get("is_uncertain")
            and not candidate.get("is_dummy_likely")
            and float(candidate.get("confidence", 0.0)) >= 0.55
            for candidate in priors.values()
        ):
            count += 1
    return count


def classify_discovery_fail_subtype(payload: Dict[str, Any]) -> str:
    attribution = payload.get("attribution")
    if attribution != "DISCOVERY_FAIL":
        return "not_discovery_fail"
    meta = payload.get("meta", payload)
    hints = meta.get("calibrated_grounding_hints") or meta.get("search_summary", {}).get("calibrated_grounding_hints") or {}
    support_plan = meta.get("support_plan", {}) or {}
    plan_score = support_plan.get("plan_score", {}) or {}
    hard_invalid_reasons = set(plan_score.get("hard_invalid_reasons", []) or [])
    semantic_reasons = set(plan_score.get("semantic_complete_reasons", []) or [])
    fallback_injected = hints.get("fallback_injected", {}) or {}
    fallback_used = any(bool(fallback_injected.get(key)) for key in ("output_slots", "filter_attributes", "order_targets"))
    calibration_rules = set(hints.get("calibration_rules_fired", []) or [])
    strong_output = _strong_prior_count(hints.get("output_priors_by_slot", {}) or {})
    strong_filter = _strong_prior_count(hints.get("filter_priors_by_attribute", {}) or {})
    strong_order = _strong_prior_count(hints.get("order_priors_by_target", {}) or {})

    calibration_only_reasons = {
        "selected_output_binding_unsupported_by_calibrated_prior",
        "selected_filter_binding_without_join_evidence",
        "selected_output_binding_without_join_evidence",
        "selected_order_binding_without_join_evidence",
        "selected_order_binding_unsupported_by_calibrated_prior",
        "selected_low_confidence_filter_binding",
        "selected_low_confidence_order_binding",
        "missing_order_binding_despite_calibrated_prior",
    }
    if hard_invalid_reasons and hard_invalid_reasons.issubset(calibration_only_reasons):
        return "C_calibration_overreach"
    if semantic_reasons & {
        "output_binding_not_supported_by_calibrated_prior",
        "order_binding_not_supported_by_calibrated_prior",
        "low_confidence_output_binding",
        "low_confidence_filter_binding",
        "low_confidence_order_binding",
    } and fallback_used:
        return "C_calibration_overreach"
    if hints.get("cross_source_join_risk") and (strong_output > 0 or strong_filter > 0 or strong_order > 0):
        return "A_path_gap"
    if fallback_used or calibration_rules:
        return "B_world_not_found"
    return "B_world_not_found"


def classify_failure(payload: Dict[str, Any]) -> str:
    meta = payload.get("meta", payload)
    if payload.get("pass", meta.get("success", False)):
        return "pass"
    support_ir = meta.get("support_ir", {}) or {}
    critique = meta.get("critique", {}) or {}
    verifier_trace = meta.get("verifier_trace", []) or []
    if not meta.get("observable_sketch", {}).get("output_slots"):
        return "observable_fail"
    if meta.get("support_plan", {}).get("unmet_obligations"):
        unmet = set(meta["support_plan"]["unmet_obligations"])
        if "support_relation" in unmet or "aggregation_support" in unmet:
            return "obligation_fail"
        if "filter_transfer" in unmet:
            return "support_retrieval_fail"
        if "value_alignment" in unmet:
            return "role_consistency_fail"
    if not support_ir.get("compile_ready", False):
        return "ir_compile_fail"
    if any(item.get("check") == "role_consistency" and not item.get("passed") for item in verifier_trace):
        return "role_consistency_fail"
    if critique.get("likely_failure_layer"):
        return str(critique["likely_failure_layer"])
    return "execution_fail"


def summarize_failures(report: Dict[str, Any]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    examples: Dict[str, List[Dict[str, Any]]] = {}
    for rec in report.get("records", []):
        failure_type = classify_failure(rec)
        counts[failure_type] = counts.get(failure_type, 0) + 1
        if failure_type == "pass":
            continue
        examples.setdefault(failure_type, [])
        if len(examples[failure_type]) < 5:
            examples[failure_type].append(
                {
                    "seed_id": rec["seed_id"],
                    "variant": rec["variant"],
                    "split": rec["split"],
                    "view": rec["view"],
                    "error": rec.get("meta", {}).get("error"),
                    "unmet_obligations": rec.get("meta", {}).get("support_plan", {}).get("unmet_obligations", []),
                }
            )
    return {"counts": counts, "examples": examples}


def summarize_discovery_failures(report: Dict[str, Any]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    examples: Dict[str, List[Dict[str, Any]]] = {}
    for rec in report.get("records", []):
        subtype = classify_discovery_fail_subtype(rec)
        if subtype == "not_discovery_fail":
            continue
        counts[subtype] = counts.get(subtype, 0) + 1
        examples.setdefault(subtype, [])
        if len(examples[subtype]) < 5:
            plan_score = (rec.get("meta", {}).get("support_plan", {}) or {}).get("plan_score", {}) or {}
            examples[subtype].append(
                {
                    "seed_id": rec.get("seed_id"),
                    "variant": rec.get("variant"),
                    "split": rec.get("split"),
                    "hard_invalid_reasons": plan_score.get("hard_invalid_reasons", []),
                    "semantic_complete_reasons": plan_score.get("semantic_complete_reasons", []),
                }
            )
    return {"counts": counts, "examples": examples}
