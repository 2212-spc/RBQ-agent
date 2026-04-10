from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.run_hdrbench_eval import _load_json
from evaluation.scorer import score_single
from evaluation.llm_backend import create_llm_session
from evaluation.support_plan_agent.compiler import compile_support_plan
from evaluation.support_plan_agent.grounding import build_llm_grounding, build_validated_overlay_edges, is_overlay_edge, overlay_edges_to_dict
from evaluation.support_plan_agent.ir import build_support_plan_ir
from evaluation.support_plan_agent.probes import prepare_case_context
from evaluation.support_plan_agent.search import _path_semantics, search_support_plans
from evaluation.support_plan_agent.verifier import obligations_from_trace, verify_support_plan


def _parse_plan_notes(notes: List[str]) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    for item in notes:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        try:
            parsed[key] = float(value)
        except Exception:
            parsed[key] = value
    return parsed


def _semantic_key(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        safe: Dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, tuple):
                safe_key = " | ".join(str(part) for part in key)
            else:
                safe_key = str(key)
            safe[safe_key] = _json_safe(item)
        return safe
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _selected_output_prior(plan, calibrated_hints: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    output_priors = (calibrated_hints or {}).get("output_priors_by_slot", {})
    for binding in plan.output_bindings:
        slot_label = str(binding.metadata.get("slot_label", "")).strip()
        prior = output_priors.get(slot_label, {}).get((binding.source_id, binding.column_name))
        if prior is not None:
            rows.append(prior)
    return rows


def _selected_filter_prior(plan, calibrated_hints: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    filter_priors = (calibrated_hints or {}).get("filter_priors_by_attribute", {})
    for binding in plan.filter_bindings:
        filter_key = str(binding.metadata.get("attribute", "")).strip() or "*"
        prior = filter_priors.get(filter_key, {}).get((binding.source_id, binding.column_name))
        if prior is None:
            prior = filter_priors.get("*", {}).get((binding.source_id, binding.column_name))
        if prior is not None:
            rows.append(prior)
    return rows


def _selected_order_prior(plan, calibrated_hints: Dict[str, Any]) -> Dict[str, Any] | None:
    if plan.order_binding is None:
        return None
    target = str(plan.order_binding.metadata.get("target") or plan.operator_plan.get("target", "")).strip()
    if not target:
        return None
    return (
        (calibrated_hints or {})
        .get("order_priors_by_target", {})
        .get(_semantic_key(target), {})
        .get((plan.order_binding.source_id, plan.order_binding.column_name))
    )


def analyze_top_candidates(
    bench_root: Path,
    seed_id: str,
    *,
    variant: str = "A",
    split: str = "l1",
    view: str = "full",
    sketch_mode: str = "fallback",
) -> Dict[str, Any]:
    seed_dir = bench_root / seed_id
    pub = _load_json(seed_dir / "variants" / variant / "manifest_public.json")
    pri = _load_json(seed_dir / "variants" / variant / "manifest_private.json")
    context = prepare_case_context(pub, pri, split=split, view=view, sketch_mode=sketch_mode, namespace=f"support_top_candidates_{seed_id}_{split}")
    session = create_llm_session(f"support_top_candidates_{seed_id}_{split}")
    llm_grounding = build_llm_grounding(
        instruction=context.instruction,
        observable_sketch=context.observable_sketch,
        catalog=context.catalog,
        session=session,
    )
    overlay_edges = build_validated_overlay_edges(llm_grounding, context.catalog)
    if overlay_edges:
        context.catalog.join_edges.extend(overlay_edges)

    search_summary = search_support_plans(
        instruction=context.instruction,
        observable_sketch=context.observable_sketch,
        obligation_sketch=context.obligation_sketch,
        catalog=context.catalog,
        llm_grounding=llm_grounding,
    )
    candidates = search_summary.get("top_plan_candidates", [])
    family_best = search_summary.get("family_best_candidates", [])
    calibrated_hints = dict(search_summary.get("calibrated_grounding_hints", {}) or {})
    family_rank_map = {id(plan): rank for rank, plan in enumerate(family_best, start=1)}

    rows: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        for rank, plan in enumerate(candidates, start=1):
            verifier_trace = verify_support_plan(plan, context.observable_sketch, context.obligation_sketch, context.catalog)
            satisfied, unmet = obligations_from_trace(verifier_trace, context.obligation_sketch)
            plan.satisfied_obligations = satisfied
            plan.unmet_obligations = unmet
            plan_ir = build_support_plan_ir(plan, context.observable_sketch, context.obligation_sketch, context.catalog)
            output_csv = tmp_root / f"candidate_{rank}.csv"
            compile_meta = compile_support_plan(plan, plan_ir, context.catalog, context.deliverable_spec, output_csv)
            score = score_single(output_csv, context.gold_path, context.deliverable_spec)
            output_source_id = plan.output_bindings[0].source_id if plan.output_bindings else None
            output_join_edge_ids = [str(edge.get("edge_id", "")) for path in plan.output_join_paths for edge in path.edges]
            filter_join_edge_ids = [str(edge.get("edge_id", "")) for path in plan.filter_join_paths for edge in path.edges]
            anchor_edge_ids = [str(edge.get("edge_id", "")) for edge in (plan.anchor_binding.edges if plan.anchor_binding is not None else [])]
            order_join_edge_ids = [str(edge.get("edge_id", "")) for edge in (plan.order_join_path.edges if plan.order_join_path is not None else [])]
            rows.append(
                {
                    "rank": rank,
                    "global_rank": rank,
                    "family_rank": family_rank_map.get(id(plan)),
                    "plan_kind": plan.plan_kind,
                    "confidence": plan.confidence,
                    "plan_score": plan.plan_score.to_dict() if plan.plan_score is not None else {},
                    "ordering_consistency": float(plan.plan_score.ordering_consistency) if plan.plan_score is not None else 0.0,
                    "semantic_complete": bool(plan.plan_score.semantic_complete) if plan.plan_score is not None else False,
                    "semantic_gap_count": int(plan.plan_score.semantic_gap_count) if plan.plan_score is not None else 0,
                    "semantic_complete_reasons": list(plan.plan_score.semantic_complete_reasons) if plan.plan_score is not None else [],
                    "hard_invalid": bool(plan.plan_score.hard_invalid) if plan.plan_score is not None else False,
                    "hard_invalid_reasons": list(plan.plan_score.hard_invalid_reasons) if plan.plan_score is not None else [],
                    "pass": bool(score.get("pass")),
                    "score": float(score.get("score", 0.0)),
                    "stage": score.get("stage"),
                    "result_rows": int(score.get("result_rows", 0)),
                    "gold_rows": int(score.get("gold_rows", 0)),
                    "support_source_id": plan.support_binding.source_id if plan.support_binding is not None else None,
                    "support_column": plan.support_binding.column_name if plan.support_binding is not None else None,
                    "measure_source_id": plan.measure_binding.source_id if plan.measure_binding is not None else None,
                    "measure_column": plan.measure_binding.column_name if plan.measure_binding is not None else None,
                    "order_source_id": plan.order_binding.source_id if plan.order_binding is not None else None,
                    "order_column": plan.order_binding.column_name if plan.order_binding is not None else None,
                    "filter_sources": [binding.source_id for binding in plan.filter_bindings],
                    "filter_columns": [binding.column_name for binding in plan.filter_bindings],
                    "filter_join_path_count": len(plan.filter_join_paths),
                    "filter_join_path_scores": [path.score for path in plan.filter_join_paths],
                    "filter_join_path_source_ids": [list(path.path_source_ids) for path in plan.filter_join_paths],
                    "filter_join_path_semantics": [_path_semantics(path, output_source_id, context.catalog) for path in plan.filter_join_paths],
                    "output_sources": [binding.source_id for binding in plan.output_bindings],
                    "output_columns": [binding.column_name for binding in plan.output_bindings],
                    "anchor_score": plan.anchor_binding.score if plan.anchor_binding is not None else 0.0,
                    "anchor_path_source_ids": list(plan.anchor_binding.path_source_ids) if plan.anchor_binding is not None else [],
                    "anchor_semantics": _path_semantics(plan.anchor_binding, output_source_id, context.catalog) if plan.anchor_binding is not None else None,
                    "order_join_path_source_ids": list(plan.order_join_path.path_source_ids) if plan.order_join_path is not None else [],
                    "order_join_path_semantics": _path_semantics(plan.order_join_path, output_source_id, context.catalog) if plan.order_join_path is not None else None,
                    "output_join_edge_ids": output_join_edge_ids,
                    "output_join_uses_overlay": any(is_overlay_edge(edge_id) for edge_id in output_join_edge_ids),
                    "output_join_scores": [path.score for path in plan.output_join_paths],
                    "output_join_path_source_ids": [list(path.path_source_ids) for path in plan.output_join_paths],
                    "output_join_semantics": [_path_semantics(path, output_source_id, context.catalog) for path in plan.output_join_paths],
                    "filter_join_edge_ids": filter_join_edge_ids,
                    "filter_join_uses_overlay": any(is_overlay_edge(edge_id) for edge_id in filter_join_edge_ids),
                    "anchor_edge_ids": anchor_edge_ids,
                    "anchor_uses_overlay": any(is_overlay_edge(edge_id) for edge_id in anchor_edge_ids),
                    "order_join_edge_ids": order_join_edge_ids,
                    "order_join_uses_overlay": any(is_overlay_edge(edge_id) for edge_id in order_join_edge_ids),
                    "satisfied_obligations": list(plan.satisfied_obligations),
                    "unmet_obligations": list(plan.unmet_obligations),
                    "note_breakdown": _parse_plan_notes(plan.notes),
                    "selected_output_priors": _selected_output_prior(plan, calibrated_hints),
                    "selected_filter_priors": _selected_filter_prior(plan, calibrated_hints),
                    "selected_order_prior": _selected_order_prior(plan, calibrated_hints),
                    "calibrated_cross_source_join_risk": bool(calibrated_hints.get("cross_source_join_risk")),
                    "calibration_rules_fired": list(calibrated_hints.get("calibration_rules_fired", [])),
                    "notes": list(plan.notes),
                    "final_sql": compile_meta.get("final_sql"),
                    "compile_ready": bool(plan_ir.compile_ready),
                    "compile_reason": plan_ir.compile_reason,
                    "compile_meta": compile_meta,
                    "verifier_trace": verifier_trace,
                }
            )

    return {
        "seed_id": seed_id,
        "variant": variant,
        "split": split,
        "view": view,
        "sketch_mode": context.sketch_mode,
        "instruction": context.instruction,
        "gold_targets": context.gold_targets.to_dict(),
        "observable_sketch": context.observable_sketch.to_dict(),
        "obligation_sketch": context.obligation_sketch.to_dict(),
        "llm_grounding": llm_grounding,
        "llm_query_family": llm_grounding.get("query_family"),
        "llm_query_family_confidence": float(llm_grounding.get("query_family_confidence", 0.0) or 0.0),
        "llm_uncertain_output_slots": [
            item.get("slot_label")
            for item in llm_grounding.get("output_hypotheses", [])
            if isinstance(item, dict) and item.get("is_uncertain")
        ],
        "llm_uncertain_filter_attributes": [
            item.get("filter_attribute")
            for item in llm_grounding.get("filter_hypotheses", [])
            if isinstance(item, dict) and item.get("is_uncertain")
        ],
        "calibrated_grounding_hints": _json_safe(calibrated_hints),
        "calibrated_query_family_confidence": float(calibrated_hints.get("query_family_confidence", 0.0) or 0.0),
        "cross_source_join_risk": bool(calibrated_hints.get("cross_source_join_risk")),
        "calibration_rules_fired": list(calibrated_hints.get("calibration_rules_fired", [])),
        "overlay_edge_count": len(overlay_edges),
        "overlay_edges": overlay_edges_to_dict(overlay_edges),
        "candidates_considered": int(search_summary.get("candidates_considered", 0)),
        "top_candidates": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze top support-plan candidates for a single benchmark case.")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--seed_id", required=True)
    parser.add_argument("--variant", default="A")
    parser.add_argument("--split", default="l1", choices=["l0", "l1", "l2", "l3"])
    parser.add_argument("--view", default="full", choices=["full", "oracle", "trimmed"])
    parser.add_argument("--sketch_mode", default="fallback", choices=["fallback", "live"])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    payload = analyze_top_candidates(
        bench_root=Path(args.bench_root),
        seed_id=args.seed_id,
        variant=args.variant,
        split=args.split,
        view=args.view,
        sketch_mode=args.sketch_mode,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out_path), "candidates_considered": payload["candidates_considered"], "top_candidate_count": len(payload["top_candidates"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
