from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from construction.seed_tools import choose_fact_table, sqlite_table_columns


FORMAT_CYCLE = ["csv", "parquet"]


def _load_table(db_path: str | Path, table: str) -> pd.DataFrame:
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(f"SELECT * FROM '{table}'", conn)
    finally:
        conn.close()


def explode_seed(
    seed: Dict[str, Any],
    sql_meta: Dict[str, Any],
    clean_dir: str | Path,
) -> Dict[str, Any]:
    clean_path = Path(clean_dir)
    clean_path.mkdir(parents=True, exist_ok=True)

    db_path = seed["db_path"]
    used_tables: List[str] = list(sql_meta.get("tables", []))
    if not used_tables:
        raise ValueError(f"Seed {seed['seed_id']} has no tables parsed from SQL.")

    fact_table = choose_fact_table(db_path, used_tables)
    table_registry: Dict[str, Dict[str, Any]] = {}

    # 1) Write fact table into SQLite to mimic core business store.
    sqlite_file = clean_path / "core_data.sqlite"
    if sqlite_file.exists():
        sqlite_file.unlink()

    sqlite_conn = sqlite3.connect(str(sqlite_file))
    try:
        fact_df = _load_table(db_path, fact_table)
        fact_df.to_sql(fact_table, sqlite_conn, index=False, if_exists="replace")
        table_registry[fact_table] = {
            "storage_type": "sqlite",
            "file": sqlite_file.name,
            "table_name": fact_table,
            "columns": sqlite_table_columns(db_path, fact_table),
            "row_count": int(len(fact_df)),
        }
    finally:
        sqlite_conn.close()

    # 2) Split remaining tables into CSV/Parquet one table per file.
    format_idx = 0
    for table in used_tables:
        if table == fact_table:
            continue

        df = _load_table(db_path, table)
        storage_type = FORMAT_CYCLE[format_idx % len(FORMAT_CYCLE)]
        format_idx += 1

        if storage_type == "csv":
            out_file = clean_path / f"{table}.csv"
            df.to_csv(out_file, index=False)
        else:
            out_file = clean_path / f"{table}.parquet"
            df.to_parquet(out_file, index=False)

        table_registry[table] = {
            "storage_type": storage_type,
            "file": out_file.name,
            "table_name": table,
            "columns": list(df.columns),
            "row_count": int(len(df)),
        }

    explosion_log = {
        "seed_id": seed["seed_id"],
        "db_id": seed["db_id"],
        "fact_table": fact_table,
        "tables": used_tables,
        "table_registry": table_registry,
        "join_edges": sql_meta.get("joins", []),
        "join_key_columns": sql_meta.get("join_key_columns", {}),
    }

    (clean_path / "explosion_log.json").write_text(
        json.dumps(explosion_log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return explosion_log
