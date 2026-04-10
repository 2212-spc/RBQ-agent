from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import duckdb
import pandas as pd


def _escape_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _source_expr(entry: Dict[str, Any], workspace_dir: Path) -> str:
    storage = entry["storage_type"]
    file_path = workspace_dir / entry["file"]
    p = _escape_path(file_path.resolve())

    if storage == "sqlite":
        return f"sqlite_scan('{p}', '{entry['table_name']}')"
    if storage == "csv":
        return f"read_csv_auto('{p}')"
    if storage == "parquet":
        return f"read_parquet('{p}')"
    raise ValueError(f"Unsupported storage type: {storage}")


def build_duckdb_script(
    gold_sql: str,
    table_registry: Dict[str, Dict[str, Any]],
    workspace_dir: str | Path,
    table_name_mapping: Dict[str, str] | None = None,
    column_alias_mapping: Dict[str, Dict[str, str]] | None = None,
    column_inverse_sql: Dict[str, Dict[str, str]] | None = None,
) -> str:
    """
    Build a DuckDB script that registers source tables as temp views, then executes query.

    table_name_mapping: canonical_table -> dirty_table_view_name
    column_alias_mapping: canonical_table -> {canonical_col: dirty_col}
    """
    workspace_path = Path(workspace_dir)
    table_name_mapping = table_name_mapping or {}
    column_alias_mapping = column_alias_mapping or {}
    column_inverse_sql = column_inverse_sql or {}

    stmts = []
    for canonical_table, entry in table_registry.items():
        view_name = table_name_mapping.get(canonical_table, canonical_table)
        scan_expr = _source_expr(entry, workspace_path)
        canonical_cols = entry.get("columns") or entry.get("canonical_columns") or []

        col_map = column_alias_mapping.get(canonical_table)
        inv_map = column_inverse_sql.get(canonical_table, {})
        if col_map:
            projected_cols = []
            for canonical_col in canonical_cols:
                dirty_col = col_map.get(canonical_col, canonical_col)
                inv_template = inv_map.get(canonical_col)
                if inv_template:
                    expr = inv_template.format(col=f'"{dirty_col}"')
                    projected_cols.append(f'{expr} AS "{canonical_col}"')
                else:
                    projected_cols.append(f'"{dirty_col}" AS "{canonical_col}"')
            select_clause = ", ".join(projected_cols)
            view_sql = f'CREATE OR REPLACE TEMP VIEW "{view_name}" AS SELECT {select_clause} FROM {scan_expr};'
        else:
            view_sql = f'CREATE OR REPLACE TEMP VIEW "{view_name}" AS SELECT * FROM {scan_expr};'
        stmts.append(view_sql)

    stmts.append(gold_sql.strip().rstrip(";") + ";")
    return "\n".join(stmts)


def execute_duckdb_script(script: str) -> pd.DataFrame:
    conn = duckdb.connect(database=":memory:")
    try:
        statements = [s.strip() for s in script.split(";") if s.strip()]
        if not statements:
            raise ValueError("Script has no executable statements.")

        for stmt in statements[:-1]:
            conn.execute(stmt)

        df = conn.execute(statements[-1]).fetchdf()
        return df
    finally:
        conn.close()


def write_gold_artifact(
    gold_sql: str,
    table_registry: Dict[str, Dict[str, Any]],
    workspace_dir: str | Path,
    output_csv: str | Path,
    output_sql: str | Path,
) -> Tuple[pd.DataFrame, str]:
    script = build_duckdb_script(gold_sql, table_registry, workspace_dir)
    df = execute_duckdb_script(script)

    out_csv = Path(output_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)

    out_sql = Path(output_sql)
    out_sql.parent.mkdir(parents=True, exist_ok=True)
    out_sql.write_text(script, encoding="utf-8")

    return df, script
