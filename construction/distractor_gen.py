from __future__ import annotations

import random
import sqlite3
import string
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from construction.seed_tools import list_sqlite_tables


def _rand_name(rng: random.Random, ext: str) -> str:
    return f"tmp_{''.join(rng.choices(string.ascii_lowercase + string.digits, k=6))}{ext}"


def _read_table(db_path: str | Path, table: str) -> pd.DataFrame:
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(f"SELECT * FROM '{table}'", conn)
    finally:
        conn.close()


def _synthetic_noise(rng: random.Random, rows: int = 500) -> pd.DataFrame:
    np_rng = np.random.default_rng(rng.randint(1, 10_000_000))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="h"),
            "status": np_rng.choice([200, 301, 404, 500], size=rows),
            "latency_ms": np_rng.integers(5, 900, size=rows),
            "path": np_rng.choice(["/api/a", "/api/b", "/healthz"], size=rows),
        }
    )


def generate_distractors(
    seed: Dict[str, Any],
    used_tables: List[str],
    out_dir: str | Path,
    num_distractors: int,
    random_seed: int,
) -> List[Dict[str, Any]]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    rng = random.Random(random_seed)
    db_path = seed["db_path"]

    all_tables = list_sqlite_tables(db_path)
    unused_tables = [t for t in all_tables if t not in set(used_tables)]

    distractors: List[Dict[str, Any]] = []

    # Prefer real unused tables.
    for table in unused_tables[:num_distractors]:
        df = _read_table(db_path, table)
        storage = rng.choice(["csv", "parquet"])
        ext = ".csv" if storage == "csv" else ".parquet"
        file_name = _rand_name(rng, ext)
        file_path = out_path / file_name

        if storage == "csv":
            df.to_csv(file_path, index=False)
        else:
            df.to_parquet(file_path, index=False)

        distractors.append(
            {
                "file": file_name,
                "storage_type": storage,
                "origin": f"unused_table:{table}",
                "rows": int(len(df)),
            }
        )

    # Fill remainder with synthetic noise files.
    while len(distractors) < num_distractors:
        df = _synthetic_noise(rng, rows=rng.randint(200, 1200))
        storage = rng.choice(["csv", "parquet"])
        ext = ".csv" if storage == "csv" else ".parquet"
        file_name = _rand_name(rng, ext)
        file_path = out_path / file_name

        if storage == "csv":
            df.to_csv(file_path, index=False)
        else:
            df.to_parquet(file_path, index=False)

        distractors.append(
            {
                "file": file_name,
                "storage_type": storage,
                "origin": "synthetic_noise",
                "rows": int(len(df)),
            }
        )

    return distractors
