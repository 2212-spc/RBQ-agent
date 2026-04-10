from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


def _load_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def attribute_failure(
    score: Dict[str, Any],
    result_csv: str | Path | None = None,
    manifest_private: Dict[str, Any] | None = None,
    agent_meta: Dict[str, Any] | None = None,
) -> str:
    if score.get("pass"):
        return "PASS"

    stage = score.get("stage")
    if stage in {"DELIVERY_FAIL", "SCHEMA_FAIL", "INSTANCE_FAIL", "QUERY_FAIL"}:
        base = stage
    else:
        base = "QUERY_FAIL"

    # Oracle-enhanced: if required dirty files were never touched, classify as discovery fail.
    if manifest_private and agent_meta:
        touched = set(agent_meta.get("files_touched", []))
        required = set(manifest_private.get("file_mapping", {}).values())
        gold_files = set(manifest_private.get("gold_files_dirty", []))
        distractor_files = {item.get("file") for item in manifest_private.get("distractors", []) if item.get("file")}
        planner_output = agent_meta.get("planner_output", {}) or {}
        relevant_files = {item for item in planner_output.get("relevant_files", []) if item}
        mapping_files = {
            item.get("source_file")
            for item in planner_output.get("output_mappings", [])
            if item.get("source_file")
        }
        if required and not required.issubset(touched):
            return "DISCOVERY_FAIL"
        if gold_files and relevant_files and relevant_files.isdisjoint(gold_files):
            return "DISCOVERY_FAIL"
        if mapping_files and mapping_files.issubset(distractor_files) and not (mapping_files & gold_files):
            return "DISCOVERY_FAIL"

    if base == "QUERY_FAIL" and result_csv and manifest_private:
        p = Path(result_csv)
        if p.exists():
            try:
                result = pd.read_csv(p)
            except Exception:  # noqa: BLE001
                return "DELIVERY_FAIL"

            dirty_col_values = set(manifest_private.get("column_mapping", {}).values())
            if dirty_col_values & set(result.columns):
                # Agent likely exposed physical dirty columns directly.
                return "SCHEMA_FAIL"

            if int(score.get("result_rows", 0)) == 0:
                return "INSTANCE_FAIL"

    return base


def main() -> None:
    parser = argparse.ArgumentParser(description="Infer attribution label from score + oracle manifests")
    parser.add_argument("--score_json", required=True)
    parser.add_argument("--result_csv", required=False)
    parser.add_argument("--manifest_private", required=False)
    parser.add_argument("--agent_meta", required=False, help="Path to agent metadata json")
    args = parser.parse_args()

    score = _load_json(args.score_json)
    priv = _load_json(args.manifest_private) if args.manifest_private else None
    meta = _load_json(args.agent_meta) if args.agent_meta else None
    label = attribute_failure(score, args.result_csv, priv, meta)
    print(label)


if __name__ == "__main__":
    main()
