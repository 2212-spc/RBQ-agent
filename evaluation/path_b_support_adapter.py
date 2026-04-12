from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from evaluation.repo_agent_utils import csv_has_content, ensure_parent, normalize_output_csv_schema
from evaluation.support_plan_agent import run_support_plan_agent


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

    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
