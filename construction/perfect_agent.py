from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from construction.sql_rewrite import build_duckdb_script, execute_duckdb_script


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols = sorted(df.columns)
    out = df[cols].copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].round(6)
    return out.sort_values(cols).reset_index(drop=True)


def run_perfect_agent(
    case_dir: str | Path,
    manifest_private: Dict[str, Any],
) -> Dict[str, Any]:
    case_path = Path(case_dir)

    gold_sql = manifest_private["gold_sql"]
    table_registry_dirty = manifest_private["table_registry_dirty"]
    column_mapping_by_table = manifest_private["column_mapping_by_table"]

    dirty_full = case_path / "dirty_full"
    script = build_duckdb_script(
        gold_sql=gold_sql,
        table_registry=table_registry_dirty,
        workspace_dir=dirty_full,
        table_name_mapping=None,
        column_alias_mapping=column_mapping_by_table,
    )

    perfect_df = execute_duckdb_script(script)
    gold_df = pd.read_csv(case_path / "gold.csv")

    pass_flag = _normalize(perfect_df).equals(_normalize(gold_df))

    sql_path = case_path / "perfect_agent.sql"
    sql_path.write_text(script, encoding="utf-8")

    result_path = case_path / "perfect_result.csv"
    perfect_df.to_csv(result_path, index=False)

    payload = {
        "perfect_agent_pass": bool(pass_flag),
        "perfect_sql_path": str(sql_path),
        "perfect_result_path": str(result_path),
    }
    (case_path / "perfect_agent_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload
