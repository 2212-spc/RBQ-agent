from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from evaluation.llm_backend import create_llm_session
from evaluation.workspace_catalog import build_workspace_catalog, summarize_workspace

from .compiler import compile_support_plan
from .grounding import build_llm_grounding, build_validated_overlay_edges, overlay_edges_to_dict
from .ir import build_support_plan_ir
from .observable import build_observable_sketch
from .obligations import build_obligation_sketch, disable_obligation_reasoning
from .search import search_support_plans
from .types import SupportPlan, SupportPlanIR
from .verifier import obligations_from_trace, verify_support_plan


def _planner_output(plan, catalog) -> Dict[str, Any]:
    relevant_files = sorted({catalog.source(binding.source_id).file_name for binding in plan.output_bindings})
    if plan.support_binding is not None:
        relevant_files.append(catalog.source(plan.support_binding.source_id).file_name)
    for binding in plan.filter_bindings:
        relevant_files.append(catalog.source(binding.source_id).file_name)
    relevant_files = sorted(set(relevant_files))
    return {
        "relevant_files": relevant_files,
        "output_bindings": [binding.to_dict() for binding in plan.output_bindings],
        "output_mappings": [
            {
                "slot_id": binding.metadata.get("slot_label", binding.column_name),
                "source_file": catalog.source(binding.source_id).file_name,
                "source_id": binding.source_id,
                "source_column": binding.column_name,
            }
            for binding in plan.output_bindings
        ],
        "support_bindings": [plan.support_binding.to_dict()] if plan.support_binding is not None else [],
        "anchor_bindings": [plan.anchor_binding.to_dict()] if plan.anchor_binding is not None else [],
    }


def _execution_sanity_score(compile_meta: Dict[str, Any], plan: SupportPlan) -> float:
    """Score a compiled plan by execution quality — used to pick the best among
    top-k candidates.  Higher is better."""
    if not compile_meta.get("executed"):
        return -100.0
    row_count = compile_meta.get("row_count", 0)
    score = 0.0
    # Must have required columns
    if compile_meta.get("required_columns_ok"):
        score += 20.0
    else:
        score -= 30.0
    # Empty result is very bad
    if row_count == 0:
        score -= 50.0
    # Reasonable row count
    elif 1 <= row_count <= 100:
        score += 10.0
    elif 100 < row_count <= 500:
        score += 3.0
    else:
        # Potential row explosion
        score -= 15.0
    # Use plan confidence as tiebreaker (scaled down so it doesn't dominate)
    score += plan.confidence * 0.01
    # Bonus for semantically complete plans
    if plan.plan_score is not None:
        if plan.plan_score.semantic_complete:
            score += 5.0
        if plan.plan_score.hard_invalid:
            score -= 30.0
    return score


def _select_best_by_execution(
    candidates: List[SupportPlan],
    observable_sketch,
    obligation_sketch,
    catalog,
    deliverable_spec: Dict[str, Any],
    output_csv: Path,
) -> Tuple[SupportPlan, SupportPlanIR, Dict[str, Any]]:
    """Compile ALL candidates and select the BEST one based on execution results.
    This replaces the old "first successful plan wins" logic.
    """
    compiled_results: List[Tuple[SupportPlan, SupportPlanIR, Dict[str, Any], float]] = []

    for idx, plan in enumerate(candidates):
        plan_ir = build_support_plan_ir(plan, observable_sketch, obligation_sketch, catalog)
        # Each candidate writes to a temp file to avoid clobbering
        if idx == 0:
            target_csv = output_csv
        else:
            target_csv = output_csv.parent / f"_candidate_{idx}.csv"
        compile_meta = compile_support_plan(plan, plan_ir, catalog, deliverable_spec, target_csv)
        exec_score = _execution_sanity_score(compile_meta, plan)
        compiled_results.append((plan, plan_ir, compile_meta, exec_score))

    # Select the best plan: prefer compiled+executed+required_columns_ok with highest score
    successful = [(p, ir, m, s) for p, ir, m, s in compiled_results
                 if m.get("compiled") and m.get("executed") and m.get("required_columns_ok")]

    if successful:
        # Among successful plans, prefer higher row_count (more complete), then higher exec_score
        successful.sort(key=lambda x: (x[3], x[2].get("row_count", 0)), reverse=True)
        selected_plan, selected_ir, selected_meta, _ = successful[0]
    else:
        # Fall back to highest exec_score
        compiled_results.sort(key=lambda x: x[3], reverse=True)
        selected_plan, selected_ir, selected_meta, _ = compiled_results[0]

    # Re-execute the winning SQL to the actual output_csv
    if selected_meta.get("final_sql") and selected_meta.get("executed"):
        from evaluation.workspace_catalog import execute_duckdb_sql
        exec_meta = execute_duckdb_sql(catalog, sql_query=selected_meta["final_sql"], output_csv=output_csv)
        selected_meta["execution_summary"] = exec_meta

    # Clean up temp files
    for idx in range(1, len(candidates)):
        temp_csv = output_csv.parent / f"_candidate_{idx}.csv"
        if temp_csv.exists():
            try:
                temp_csv.unlink()
            except OSError:
                pass

    return selected_plan, selected_ir, selected_meta


def run_support_plan_agent(
    instruction: str,
    workspace: Path,
    deliverable_spec: Dict[str, Any],
    output_csv: Path,
    obligation_mode: str = "full",
) -> Dict[str, Any]:
    if obligation_mode not in {"full", "off"}:
        raise ValueError(f"Unsupported obligation_mode: {obligation_mode}")
    started = time.time()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    session = create_llm_session("support_plan_agent")
    workspace_summary = summarize_workspace(workspace)
    catalog = build_workspace_catalog(workspace)

    # --- Step 1: Observable sketch (1 LLM call) ---
    observable_sketch = build_observable_sketch(instruction=instruction, deliverable_spec=deliverable_spec, session=session)

    # --- Step 2: Workspace-aware obligation sketch (1 LLM call) ---
    obligation_sketch = build_obligation_sketch(instruction=instruction, observable_sketch=observable_sketch, session=session, catalog=catalog)
    if obligation_mode == "off":
        obligation_sketch = disable_obligation_reasoning(obligation_sketch)

    # --- Step 3: LLM pre-grounding (1 LLM call) ---
    llm_grounding = build_llm_grounding(instruction=instruction, observable_sketch=observable_sketch, catalog=catalog, session=session)
    overlay_edges = build_validated_overlay_edges(llm_grounding, catalog)
    if overlay_edges:
        catalog.join_edges.extend(overlay_edges)

    # --- Step 4: Search support plans (0 LLM calls, uses grounding) ---
    search_summary = search_support_plans(
        instruction=instruction,
        observable_sketch=observable_sketch,
        obligation_sketch=obligation_sketch,
        catalog=catalog,
        llm_grounding=llm_grounding,
    )

    # --- Step 5: Execution-based verification on top-3 candidates ---
    candidates = search_summary.get("family_best_candidates", [])
    if not candidates:
        candidates = [search_summary["best_plan"]]
    # Take up to 3 candidates for execution verification
    candidates = candidates[:3]

    plan, plan_ir, compile_meta = _select_best_by_execution(
        candidates, observable_sketch, obligation_sketch, catalog, deliverable_spec, output_csv,
    )

    # Update plan with verification info
    verifier_trace = verify_support_plan(plan, observable_sketch, obligation_sketch, catalog)
    satisfied, unmet = obligations_from_trace(verifier_trace, obligation_sketch)
    plan.satisfied_obligations = satisfied
    plan.unmet_obligations = unmet

    # --- Step 6: Optional critique if failed (0-1 LLM call) ---
    critique: Dict[str, Any] | None = None
    if (not compile_meta.get("compiled") or not compile_meta.get("required_columns_ok")) and session is not None and session.remaining_calls > 0:
        try:
            critique = session.chat_json(
                "You are a terse SQL plan critic. Return JSON only.",
                (
                    f"Question: {instruction}\n\n"
                    f"Observable sketch: {observable_sketch.to_dict()}\n\n"
                    f"Obligation sketch: {obligation_sketch.to_dict()}\n\n"
                    f"Support plan: {plan.to_dict()}\n\n"
                    f"IR: {plan_ir.to_dict()}\n\n"
                    f"Compile meta: {compile_meta}\n\n"
                    "Return JSON with keys: likely_failure_layer, critique, next_fix."
                ),
                cache_namespace="support_plan_critique",
            )
        except Exception:
            critique = None

    success = bool(
        compile_meta.get("compiled")
        and compile_meta.get("executed")
        and compile_meta.get("required_columns_ok")
        and compile_meta.get("row_count", 0) > 0
    )
    if not output_csv.exists():
        pd.DataFrame(columns=deliverable_spec.get("required_columns", [])).to_csv(output_csv, index=False)

    execution_summary = dict(compile_meta.get("execution_summary", {}) or {})
    if "success" not in execution_summary:
        execution_summary["success"] = bool(compile_meta.get("executed"))
    return {
        "success": success,
        "files_touched": catalog.files_touched,
        "error": None if success else compile_meta.get("reason", "compile_failed"),
        "workspace_summary": workspace_summary,
        "observable_sketch": observable_sketch.to_dict(),
        "obligation_sketch": obligation_sketch.to_dict(),
        "obligation_mode": obligation_mode,
        "llm_grounding": llm_grounding,
        "llm_overlay_edge_count": len(overlay_edges),
        "llm_overlay_edges": overlay_edges_to_dict(overlay_edges),
        "calibrated_grounding_hints": search_summary.get("calibrated_grounding_hints"),
        "search_summary": {
            "candidates_considered": search_summary["candidates_considered"],
            "search_log": search_summary["search_log"],
            "execution_candidates_tried": len(candidates),
            "calibrated_grounding_hints": search_summary.get("calibrated_grounding_hints"),
        },
        "support_plan": plan.to_dict(),
        "support_ir": plan_ir.to_dict(),
        "verifier_trace": verifier_trace,
        "planner_output": _planner_output(plan, catalog),
        "final_sql": compile_meta.get("final_sql"),
        "execution_summary": execution_summary,
        "critique": critique,
        "agent_impl": "support_plan_agent",
        "wall_clock_time": round(time.time() - started, 4),
        "llm_calls_used": session.calls_used if session is not None else 0,
        "llm_calls_budget": session.max_calls if session is not None else 0,
    }
