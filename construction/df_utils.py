from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict

import pandas as pd


def normalize_df(df: pd.DataFrame, float_tol: float = 1e-6) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    # Make duplicate column names deterministic and unique (can happen in SQL outputs).
    seen: Dict[str, int] = {}
    unique_cols = []
    for c in out.columns:
        k = str(c)
        idx = seen.get(k, 0)
        seen[k] = idx + 1
        unique_cols.append(k if idx == 0 else f"{k}__dup{idx}")
    out.columns = unique_cols

    cols = sorted(unique_cols)
    out = out[cols]
    for c in cols:
        series = out[c]
        if pd.api.types.is_numeric_dtype(series):
            out[c] = pd.to_numeric(series, errors="coerce").round(6)
        else:
            out[c] = series.astype(str).str.strip()
    return out.sort_values(cols).reset_index(drop=True)


def compare_frames(a: pd.DataFrame, b: pd.DataFrame, float_tol: float = 1e-6) -> bool:
    na = normalize_df(a, float_tol=float_tol)
    nb = normalize_df(b, float_tol=float_tol)
    if list(na.columns) != list(nb.columns) or len(na) != len(nb):
        return False
    if na.empty and nb.empty:
        return True

    for col in na.columns:
        sa = na[col]
        sb = nb[col]
        if pd.api.types.is_numeric_dtype(sa) and pd.api.types.is_numeric_dtype(sb):
            diff = (sa - sb).abs().fillna(0)
            if (diff > float_tol).any():
                return False
        else:
            if not sa.astype(str).equals(sb.astype(str)):
                return False
    return True


def read_table_from_registry(workspace_dir: str | Path, entry: Dict[str, Any]) -> pd.DataFrame:
    workspace = Path(workspace_dir)
    fp = workspace / entry["file"]
    storage = entry["storage_type"]
    if storage == "sqlite":
        conn = sqlite3.connect(str(fp))
        try:
            return pd.read_sql_query(f"SELECT * FROM '{entry['table_name']}'", conn)
        finally:
            conn.close()
    if storage == "csv":
        return pd.read_csv(fp)
    if storage == "parquet":
        return pd.read_parquet(fp)
    raise ValueError(f"Unsupported storage type: {storage}")


def write_table_to_registry(workspace_dir: str | Path, entry: Dict[str, Any], df: pd.DataFrame, file_name: str) -> None:
    workspace = Path(workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    fp = workspace / file_name
    storage = entry["storage_type"]
    if storage == "sqlite":
        conn = sqlite3.connect(str(fp))
        try:
            df.to_sql(entry["table_name"], conn, index=False, if_exists="replace")
        finally:
            conn.close()
        return
    if storage == "csv":
        df.to_csv(fp, index=False)
        return
    if storage == "parquet":
        df.to_parquet(fp, index=False)
        return
    raise ValueError(f"Unsupported storage type: {storage}")
