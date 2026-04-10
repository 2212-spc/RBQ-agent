from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from construction.df_utils import compare_frames
from construction.seed_tools import (
    dump_json,
    parse_sql_metadata,
    sqlite_table_column_types,
)

ALLOWED_KEY_TYPES = {"INT", "INTEGER", "TEXT", "DATE", "VARCHAR", "CHAR"}
BLOCKED_KEY_TYPES = {"REAL", "FLOAT", "DOUBLE", "BLOB", "BOOLEAN", "NUMERIC", "DECIMAL"}
BLOCKLIST_SQL_TOKENS = {
    "GROUP_CONCAT",
    "STRFTIME",
    "JULIANDAY",
}


def _load_spider_examples(spider_json: Path) -> List[Dict[str, Any]]:
    payload = json.loads(spider_json.read_text(encoding="utf-8"))
    out: List[Dict[str, Any]] = []
    for i, ex in enumerate(payload):
        sql = ex.get("query") or ex.get("sql")
        if not isinstance(sql, str):
            continue
        out.append(
            {
                "seed_id": f"spider__{ex['db_id']}__{i:05d}",
                "db_id": ex["db_id"],
                "question": ex.get("question", ""),
                "gold_sql": sql,
            }
        )
    return out


def _db_path_for(db_root: Path, db_id: str) -> Path:
    return db_root / db_id / f"{db_id}.sqlite"


def _run_sqlite(db_path: Path, sql: str) -> pd.DataFrame:
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def _run_duckdb_with_sqlite_scan(db_path: Path, sql: str) -> pd.DataFrame:
    conn = duckdb.connect(database=":memory:")
    try:
        conn.execute("INSTALL sqlite;")
        conn.execute("LOAD sqlite;")

        sconn = sqlite3.connect(str(db_path))
        try:
            tables = [
                r[0]
                for r in sconn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
        finally:
            sconn.close()

        db_uri = str(db_path).replace("\\", "/")
        for t in tables:
            conn.execute(
                f"CREATE OR REPLACE TEMP VIEW \"{t}\" AS SELECT * FROM sqlite_scan('{db_uri}', '{t}')"
            )

        return conn.execute(sql).fetchdf()
    finally:
        conn.close()


def _has_explicit_join_on(sql: str) -> bool:
    # Cheap guard before AST parse.
    s = sql.upper()
    return " JOIN " in s and " ON " in s


def _contains_blocked_token(sql: str) -> bool:
    s = sql.upper()
    return any(tok in s for tok in BLOCKLIST_SQL_TOKENS)


def _valid_key_types(db_path: Path, sql_meta: Dict[str, Any]) -> tuple[bool, Dict[str, str], str]:
    key_types: Dict[str, str] = {}
    for table, cols in sql_meta.get("key_columns_by_table", {}).items():
        types = sqlite_table_column_types(db_path, table)
        for col in cols:
            decl = types.get(col, "").upper() or "TEXT"
            # map declarations like VARCHAR(100) -> VARCHAR
            base = decl.split("(")[0].strip() if decl else "TEXT"
            key = f"{table}.{col}"
            key_types[key] = base
            if base in BLOCKED_KEY_TYPES:
                return False, key_types, f"blocked key type {key}:{base}"
            if base not in ALLOWED_KEY_TYPES:
                return False, key_types, f"unsupported key type {key}:{base}"
    return True, key_types, ""


def _result_shape(df: pd.DataFrame) -> Dict[str, int]:
    return {"rows": int(len(df)), "cols": int(len(df.columns))}


def build_seed_registry(
    spider_json: Path,
    db_root: Path,
    out_registry: Path,
    max_seeds: int,
    per_db_limit: int,
    random_seed: int,
) -> Dict[str, Any]:
    examples = _load_spider_examples(spider_json)
    # deterministic ordering for reproducibility.
    examples = sorted(examples, key=lambda x: (x["db_id"], x["seed_id"]))

    candidate_records: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    for ex in examples:
        db_id = ex["db_id"]

        db_path = _db_path_for(db_root, db_id)
        if not db_path.exists():
            skipped.append({"seed_id": ex["seed_id"], "reason": f"db not found: {db_path}"})
            continue

        sql = ex["gold_sql"].strip()
        if _contains_blocked_token(sql):
            skipped.append({"seed_id": ex["seed_id"], "reason": "contains blocked function token"})
            continue

        if not _has_explicit_join_on(sql):
            skipped.append({"seed_id": ex["seed_id"], "reason": "not explicit JOIN ... ON"})
            continue

        try:
            meta = parse_sql_metadata(sql)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"seed_id": ex["seed_id"], "reason": f"parse error: {exc}"})
            continue

        if len(meta.get("tables", [])) < 2:
            skipped.append({"seed_id": ex["seed_id"], "reason": "<2 tables"})
            continue
        if len(meta.get("joins", [])) < 1:
            skipped.append({"seed_id": ex["seed_id"], "reason": "<1 join edge"})
            continue

        ok_types, key_types, type_reason = _valid_key_types(db_path, meta)
        if not ok_types:
            skipped.append({"seed_id": ex["seed_id"], "reason": type_reason})
            continue

        try:
            sqlite_df = _run_sqlite(db_path, sql)
            duck_df = _run_duckdb_with_sqlite_scan(db_path, sql)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"seed_id": ex["seed_id"], "reason": f"execution fail: {exc}"})
            continue

        if len(sqlite_df) < 1:
            skipped.append({"seed_id": ex["seed_id"], "reason": "empty sqlite result"})
            continue

        if not compare_frames(sqlite_df, duck_df, float_tol=1e-6):
            skipped.append({"seed_id": ex["seed_id"], "reason": "sqlite/duckdb mismatch"})
            continue

        record = {
            "seed_id": ex["seed_id"],
            "db_id": db_id,
            "db_path": str(db_path),
            "question": ex["question"],
            "gold_sql": sql,
            "tables": meta.get("tables", []),
            "join_keys": [
                f"{j['left_table']}.{j['left_col']}={j['right_table']}.{j['right_col']}"
                for j in meta.get("joins", [])
            ],
            "joins": meta.get("joins", []),
            "join_key_columns": meta.get("join_key_columns", {}),
            "key_columns": meta.get("key_columns", []),
            "key_columns_by_table": meta.get("key_columns_by_table", {}),
            "key_column_types": key_types,
            "result_shape": _result_shape(sqlite_df),
        }
        candidate_records.append(record)

    if not candidate_records:
        out_registry.parent.mkdir(parents=True, exist_ok=True)
        out_registry.write_text("", encoding="utf-8")
        summary = {
            "spider_json": str(spider_json),
            "db_root": str(db_root),
            "requested_max": max_seeds,
            "kept": 0,
            "skipped": len(skipped),
            "per_db_count": {},
            "registry_path": str(out_registry),
            "q05_rows": None,
            "q95_rows": None,
        }
        dump_json(out_registry.with_suffix(".summary.json"), summary)
        dump_json(out_registry.with_suffix(".skipped.json"), {"skipped": skipped})
        return summary

    # Q5-Q95 filter on result rows.
    row_counts = np.array([r["result_shape"]["rows"] for r in candidate_records], dtype=float)
    q05 = float(np.quantile(row_counts, 0.05))
    q95 = float(np.quantile(row_counts, 0.95))

    ranged = []
    for r in candidate_records:
        rows = r["result_shape"]["rows"]
        if rows < q05 or rows > q95:
            skipped.append({"seed_id": r["seed_id"], "reason": f"rows out of q05-q95: {rows}"})
            continue
        ranged.append(r)

    # deterministic selection under per-db cap and max_seeds
    ranged = sorted(ranged, key=lambda x: (x["db_id"], x["seed_id"]))
    kept: List[Dict[str, Any]] = []
    per_db_count: Dict[str, int] = {}
    for r in ranged:
        if len(kept) >= max_seeds:
            break
        db_id = r["db_id"]
        if per_db_count.get(db_id, 0) >= per_db_limit:
            continue
        kept.append(r)
        per_db_count[db_id] = per_db_count.get(db_id, 0) + 1

    out_registry.parent.mkdir(parents=True, exist_ok=True)
    with out_registry.open("w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {
        "spider_json": str(spider_json),
        "db_root": str(db_root),
        "requested_max": max_seeds,
        "kept": len(kept),
        "skipped": len(skipped),
        "per_db_count": per_db_count,
        "registry_path": str(out_registry),
        "q05_rows": q05,
        "q95_rows": q95,
        "candidates_before_quantile_filter": len(candidate_records),
    }
    dump_json(out_registry.with_suffix(".summary.json"), summary)
    dump_json(out_registry.with_suffix(".skipped.json"), {"skipped": skipped})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase0 seed filtering for HDR-Bench")
    parser.add_argument("--spider_json", required=True, help="Path to Spider train/dev json")
    parser.add_argument("--db_root", required=True, help="Path to Spider database root dir")
    parser.add_argument("--out", required=True, help="Output seed_registry.jsonl")
    parser.add_argument("--max_seeds", type=int, default=12)
    parser.add_argument("--per_db_limit", type=int, default=3)
    parser.add_argument("--random_seed", type=int, default=13)
    args = parser.parse_args()

    summary = build_seed_registry(
        spider_json=Path(args.spider_json),
        db_root=Path(args.db_root),
        out_registry=Path(args.out),
        max_seeds=int(args.max_seeds),
        per_db_limit=int(args.per_db_limit),
        random_seed=int(args.random_seed),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
