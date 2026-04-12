from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from evaluation.repo_agent_utils import csv_has_content, ensure_parent, normalize_output_csv_schema
from evaluation.support_plan_agent import run_support_plan_agent


def _compact_planner_output(planner_output: dict | None) -> dict:
    planner_output = planner_output or {}
    relevant_files = [item for item in planner_output.get("relevant_files", []) if item]
    output_mappings = []
    for item in planner_output.get("output_mappings", []) or []:
        if not isinstance(item, dict):
            continue
        slim = {}
        if item.get("source_file"):
            slim["source_file"] = item["source_file"]
        if item.get("target_column"):
            slim["target_column"] = item["target_column"]
        if slim:
            output_mappings.append(slim)
    compact = {}
    if relevant_files:
        compact["relevant_files"] = relevant_files
    if output_mappings:
        compact["output_mappings"] = output_mappings
    return compact


def _compact_execution_summary(execution_summary: dict | None) -> dict:
    execution_summary = execution_summary or {}
    keep = (
        "success",
        "executed",
        "row_count",
        "empty_result",
        "non_empty_output",
        "reason",
        "selected_candidate_rank",
    )
    return {k: execution_summary[k] for k in keep if k in execution_summary}


def _compact_support_meta(meta: dict) -> dict:
    compact = {
        "success": bool(meta.get("success")),
        "agent_impl": meta.get("agent_impl", "support_plan_agent"),
        "error": meta.get("error"),
        "files_touched": list(meta.get("files_touched", []) or []),
    }
    planner_output = _compact_planner_output(meta.get("planner_output"))
    if planner_output:
        compact["planner_output"] = planner_output
    execution_summary = _compact_execution_summary(meta.get("execution_summary"))
    if execution_summary:
        compact["execution_summary"] = execution_summary
    for key in ("wall_clock_time", "llm_calls_used", "llm_calls_budget", "obligation_mode"):
        if key in meta:
            compact[key] = meta.get(key)
    search_summary = meta.get("search_summary") or {}
    if search_summary:
        compact["search_summary"] = {
            key: search_summary.get(key)
            for key in ("candidates_considered", "execution_candidates_tried")
            if key in search_summary
        }
    return compact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--deliverable-spec-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--obligation-mode", default="full")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    output_csv = Path(args.output_csv).resolve()
    deliverable_spec = json.loads(args.deliverable_spec_json)
    required_columns = list(deliverable_spec.get("required_columns", []))
    ensure_parent(output_csv)

    meta = run_support_plan_agent(
        instruction=args.instruction,
        workspace=workspace,
        deliverable_spec=deliverable_spec,
        output_csv=output_csv,
        obligation_mode=args.obligation_mode,
    )

    normalize_output_csv_schema(output_csv, required_columns)
    if not csv_has_content(output_csv):
        pd.DataFrame(columns=required_columns).to_csv(output_csv, index=False)
        meta["success"] = False
        if not meta.get("error"):
            meta["error"] = "support path did not create a non-empty output csv"

    print(json.dumps(_compact_support_meta(meta), ensure_ascii=False))


if __name__ == "__main__":
    main()
