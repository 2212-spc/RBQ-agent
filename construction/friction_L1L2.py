from __future__ import annotations

import random
import sqlite3
import string
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


def _random_file_name(rng: random.Random, ext: str) -> str:
    token = "".join(rng.choices(string.ascii_lowercase + string.digits, k=6))
    return f"dump_{token}{ext}"


def _random_col_name(rng: random.Random, used: set[str], idx: int) -> str:
    candidates = [
        f"col_{idx}",
        f"field_{idx:02d}",
        f"fk_{rng.randint(10, 999)}",
        f"v_{''.join(rng.choices(string.ascii_lowercase, k=3))}",
    ]
    for c in candidates:
        if c not in used:
            return c
    while True:
        c = f"c_{''.join(rng.choices(string.ascii_lowercase + string.digits, k=5))}"
        if c not in used:
            return c


def _load_table(clean_dir: Path, entry: Dict[str, Any]) -> pd.DataFrame:
    storage = entry["storage_type"]
    file_path = clean_dir / entry["file"]
    if storage == "sqlite":
        conn = sqlite3.connect(str(file_path))
        try:
            return pd.read_sql_query(f"SELECT * FROM '{entry['table_name']}'", conn)
        finally:
            conn.close()
    if storage == "csv":
        return pd.read_csv(file_path)
    if storage == "parquet":
        return pd.read_parquet(file_path)
    raise ValueError(f"Unsupported storage type: {storage}")


def _write_table(dirty_dir: Path, entry: Dict[str, Any], df: pd.DataFrame, dirty_file: str) -> None:
    storage = entry["storage_type"]
    file_path = dirty_dir / dirty_file
    if storage == "sqlite":
        conn = sqlite3.connect(str(file_path))
        try:
            df.to_sql(entry["table_name"], conn, index=False, if_exists="replace")
        finally:
            conn.close()
    elif storage == "csv":
        df.to_csv(file_path, index=False)
    elif storage == "parquet":
        df.to_parquet(file_path, index=False)
    else:
        raise ValueError(f"Unsupported storage type: {storage}")


def apply_l1_l2_friction(
    clean_dir: str | Path,
    dirty_full_dir: str | Path,
    explosion_log: Dict[str, Any],
    rename_ratio: float,
    join_key_rename_ratio: float,
    dummy_cols_min: int,
    dummy_cols_max: int,
    random_seed: int,
) -> Dict[str, Any]:
    clean_path = Path(clean_dir)
    dirty_path = Path(dirty_full_dir)
    dirty_path.mkdir(parents=True, exist_ok=True)

    rng = random.Random(random_seed)
    np_rng = np.random.default_rng(random_seed)

    table_registry = explosion_log["table_registry"]
    join_keys = {
        t: set(cols)
        for t, cols in explosion_log.get("join_key_columns", {}).items()
    }

    file_mapping: Dict[str, str] = {}
    used_file_names: set[str] = set()

    # L1: rename each source file exactly once.
    for entry in table_registry.values():
        original_file = entry["file"]
        if original_file in file_mapping:
            continue
        ext = Path(original_file).suffix
        new_name = _random_file_name(rng, ext)
        while new_name in used_file_names:
            new_name = _random_file_name(rng, ext)
        file_mapping[original_file] = new_name
        used_file_names.add(new_name)

    friction_trace: List[Dict[str, Any]] = []
    for src, dst in file_mapping.items():
        friction_trace.append(
            {
                "level": "L1",
                "type": "file_rename",
                "original": src,
                "transformed": dst,
            }
        )

    # L2: column rename + dummy columns with global uniqueness.
    global_used_cols: set[str] = set()
    column_mapping_flat: Dict[str, str] = {}
    column_mapping_by_table: Dict[str, Dict[str, str]] = {}
    dirty_registry: Dict[str, Dict[str, Any]] = {}

    # To avoid duplicated writes for sqlite file shared by multiple tables, collect per table writes first.
    staged_tables: List[Tuple[str, Dict[str, Any], pd.DataFrame, str]] = []

    for table_name, entry in table_registry.items():
        df = _load_table(clean_path, entry)
        mapping: Dict[str, str] = {}

        for idx, col in enumerate(entry["columns"]):
            is_join_key = col in join_keys.get(table_name, set())
            should_rename = (rng.random() < rename_ratio) or (
                is_join_key and rng.random() < join_key_rename_ratio
            )

            if should_rename or col in global_used_cols:
                new_col = _random_col_name(rng, global_used_cols, idx)
            else:
                new_col = col
                if new_col in global_used_cols:
                    new_col = _random_col_name(rng, global_used_cols, idx)

            mapping[col] = new_col
            global_used_cols.add(new_col)

            if new_col != col:
                friction_trace.append(
                    {
                        "level": "L2",
                        "type": "col_rename",
                        "table": table_name,
                        "original": col,
                        "transformed": new_col,
                        "is_key": bool(is_join_key),
                    }
                )

        renamed_df = df.rename(columns=mapping)

        # Dummy columns.
        n_dummy = rng.randint(dummy_cols_min, dummy_cols_max)
        for _ in range(n_dummy):
            dummy_name = _random_col_name(rng, global_used_cols, rng.randint(100, 999))
            renamed_df[dummy_name] = np_rng.integers(0, 1000, size=len(renamed_df)) if len(renamed_df) else []
            global_used_cols.add(dummy_name)
            friction_trace.append(
                {
                    "level": "L2",
                    "type": "col_add_dummy",
                    "table": table_name,
                    "transformed": dummy_name,
                    "is_key": False,
                }
            )

        for c_old, c_new in mapping.items():
            column_mapping_flat[f"{table_name}.{c_old}"] = c_new

        column_mapping_by_table[table_name] = mapping

        dirty_file = file_mapping[entry["file"]]
        staged_tables.append((table_name, entry, renamed_df, dirty_file))

    for table_name, entry, renamed_df, dirty_file in staged_tables:
        _write_table(dirty_path, entry, renamed_df, dirty_file)

        dirty_registry[table_name] = {
            "storage_type": entry["storage_type"],
            "file": dirty_file,
            "table_name": entry["table_name"],
            "columns": entry["columns"],
            "dirty_columns": list(renamed_df.columns),
            "row_count": int(len(renamed_df)),
        }

    return {
        "file_mapping": file_mapping,
        "column_mapping": column_mapping_flat,
        "column_mapping_by_table": column_mapping_by_table,
        "friction_trace": friction_trace,
        "table_registry_dirty": dirty_registry,
        "gold_files_dirty": sorted({v for v in file_mapping.values()}),
    }
