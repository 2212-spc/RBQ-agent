from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd
from openai import OpenAI


REPO_ROOT = Path(__file__).resolve().parent
DEPLOYMENT_ROOT = REPO_ROOT / "deployment"
HDRBENCH_ROOT = Path(__file__).resolve().parents[3] / "hdrbench_mvp"
if str(HDRBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(HDRBENCH_ROOT))
if str(DEPLOYMENT_ROOT) not in sys.path:
    sys.path.append(str(DEPLOYMENT_ROOT))

from deployment.execution import execute_script
from evaluation.repo_agent_utils import (
    create_chat_completion,
    csv_has_content,
    ensure_parent,
    extract_python_block,
    load_llm_env,
    normalize_output_csv_schema,
    empty_token_usage,
    merge_token_usage,
    response_text,
    response_token_usage,
    run_fallback_code_agent,
    summarize_workspace,
)


def _force_fallback() -> bool:
    return os.environ.get("HDRBENCH_FORCE_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}


def _stage_workspace(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for fp in src.iterdir():
        if fp.is_file():
            shutil.copy2(fp, dst / fp.name)


def _build_native_messages(
    instruction: str,
    workspace: Path,
    deliverable_spec: dict,
    output_csv: Path,
) -> list[dict]:
    workspace_summary = summarize_workspace(workspace)
    return [
        {
            "role": "system",
            "content": (
                "You are DS-Agent for automated data science. "
                "Generate a complete Python script that reads local files, computes the answer, and writes the final CSV."
            ),
        },
        {
            "role": "user",
            "content": (
                "Solve this HDR-Bench extraction task.\n\n"
                f"[Task]\n{instruction}\n\n"
                f"[Working Directory]\n{workspace}\n\n"
                f"[Workspace Summary]\n{json.dumps(workspace_summary, ensure_ascii=False, indent=2)}\n\n"
                f"[Deliverable Spec]\n{json.dumps(deliverable_spec, ensure_ascii=False, indent=2)}\n\n"
                "[Constraints]\n"
                f"1. Read only files under {workspace}.\n"
                "2. Use pandas/sqlite3/duckdb as needed.\n"
                "3. Inspect actual schema and data before joining.\n"
                f"4. Write exactly one CSV to this absolute path: {output_csv}\n"
                "5. Return only one fenced Python block.\n"
            ),
        },
    ]


def _run_native(
    instruction: str,
    workspace: Path,
    deliverable_spec: dict,
    output_csv: Path,
) -> dict:
    cfg = load_llm_env()
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["api_base"])

    with tempfile.TemporaryDirectory(prefix="hdrbench_ds_agent_") as tmpdir:
        staged_workspace = Path(tmpdir) / "workspace"
        _stage_workspace(workspace, staged_workspace)

        messages = _build_native_messages(instruction, staged_workspace, deliverable_spec, output_csv)
        steps: list[dict] = []
        script_name = "ds_agent_candidate.py"
        token_usage = empty_token_usage()
        llm_calls = 0
        tool_calls = 0

        for _ in range(5):
            resp = create_chat_completion(cfg, client, messages)
            llm_calls += 1
            merge_token_usage(token_usage, response_token_usage(resp))
            text = response_text(resp).strip()
            steps.append({"assistant": text[:1200]})

            code = extract_python_block(text)
            if not code:
                messages.append({"role": "assistant", "content": text})
                messages.append(
                    {
                        "role": "user",
                        "content": "Return exactly one complete ```python``` block.",
                    }
                )
                continue

            (staged_workspace / script_name).write_text(code, encoding="utf-8")
            try:
                observation = execute_script(script_name=script_name, work_dir=str(staged_workspace), device="0")
            except Exception as exc:  # noqa: BLE001
                observation = f"Execution failed: {exc}"
            tool_calls += 1

            steps.append({"execution": observation[-1500:]})
            if csv_has_content(output_csv):
                break

            messages.append({"role": "assistant", "content": text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Script execution finished but output CSV is still missing/invalid.\n"
                        f"Observation:\n{observation[-2500:]}\n\n"
                        f"Rewrite the full Python script and ensure it writes {output_csv}."
                    ),
                }
            )

    return {
        "success": csv_has_content(output_csv),
        "engine": "ds_agent_native_codegen",
        "steps": steps,
        "llm_calls": llm_calls,
        "tool_calls": tool_calls,
        "token_usage": token_usage,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--deliverable-spec-json", required=True)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    output_csv = Path(args.output_csv).resolve()
    deliverable_spec = json.loads(args.deliverable_spec_json)
    required_columns = deliverable_spec.get("required_columns", [])
    ensure_parent(output_csv)

    meta: dict = {"success": False, "engine": "ds-agent", "native_skipped": False}
    if _force_fallback():
        meta["native_skipped"] = True
        meta["native_error"] = "forced_fallback"
    else:
        try:
            native = _run_native(args.instruction, workspace, deliverable_spec, output_csv)
            meta["native"] = native
            meta["success"] = bool(native.get("success")) and csv_has_content(output_csv)
        except Exception as exc:  # noqa: BLE001
            meta["native_error"] = str(exc)

    if not meta["success"]:
        fallback = run_fallback_code_agent(
            style_name="DS-Agent",
            instruction=args.instruction,
            workspace=workspace,
            deliverable_spec=deliverable_spec,
            output_csv=output_csv,
            extra_context=(
                "Use DS-Agent style: propose a complete runnable Python script, execute, inspect logs, and iterate."
            ),
        )
        meta["fallback"] = fallback
        meta["success"] = bool(fallback.get("success")) and csv_has_content(output_csv)

    normalize_output_csv_schema(output_csv, required_columns)
    if not csv_has_content(output_csv):
        pd.DataFrame(columns=required_columns).to_csv(output_csv, index=False)
        meta["success"] = False

    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
