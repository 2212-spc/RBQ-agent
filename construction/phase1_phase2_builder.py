from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from construction.df_utils import compare_frames
from construction.seed_tools import sqlite_table_columns, sqlite_table_row_count
from construction.sql_rewrite import build_duckdb_script, execute_duckdb_script

VARIANTS = {
    "A": 1.0,
    "B": 0.6,
    "C": 0.3,
}


def _load_table(db_path: Path, table: str) -> pd.DataFrame:
    conn = sqlite3.connect(str(db_path))
    try:
        return pd.read_sql_query(f"SELECT * FROM '{table}'", conn)
    finally:
        conn.close()


def _choose_fact_table(db_path: Path, tables: List[str]) -> str:
    counts = [(t, sqlite_table_row_count(db_path, t)) for t in tables]
    counts.sort(key=lambda x: x[1], reverse=True)
    return counts[0][0]


def _initial_format_assignment(tables: List[str], fact_table: str) -> Dict[str, str]:
    formats: Dict[str, str] = {fact_table: "sqlite"}
    cycle = ["csv", "parquet"]
    idx = 0
    for t in tables:
        if t == fact_table:
            continue
        formats[t] = cycle[idx % 2]
        idx += 1
    return formats


def _flip_format(fmt: str) -> str:
    return "parquet" if fmt == "csv" else "csv"


def _enforce_cross_format_joins(formats: Dict[str, str], joins: List[Dict[str, str]], fact_table: str) -> Dict[str, str]:
    out = dict(formats)
    for edge in joins:
        lt = edge["left_table"]
        rt = edge["right_table"]
        if out[lt] != out[rt]:
            continue

        # never flip fact_table away from sqlite
        if rt != fact_table and out[rt] in {"csv", "parquet"}:
            out[rt] = _flip_format(out[rt])
        elif lt != fact_table and out[lt] in {"csv", "parquet"}:
            out[lt] = _flip_format(out[lt])
    return out


def _iterative_join_filter(
    sampled: Dict[str, pd.DataFrame], joins: List[Dict[str, str]], max_iter: int = 10
) -> Dict[str, pd.DataFrame]:
    out = {k: v.copy() for k, v in sampled.items()}
    for _ in range(max_iter):
        changed = False
        for edge in joins:
            lt, lc = edge["left_table"], edge["left_col"]
            rt, rc = edge["right_table"], edge["right_col"]

            lvals = set(out[lt][lc].dropna().astype(str).tolist())
            rvals = set(out[rt][rc].dropna().astype(str).tolist())
            inter = lvals & rvals

            new_l = out[lt][out[lt][lc].astype(str).isin(inter)]
            new_r = out[rt][out[rt][rc].astype(str).isin(inter)]

            if len(new_l) != len(out[lt]):
                out[lt] = new_l.reset_index(drop=True)
                changed = True
            if len(new_r) != len(out[rt]):
                out[rt] = new_r.reset_index(drop=True)
                changed = True

        if not changed:
            break
    return out


def _cascade_sample(
    tables: Dict[str, pd.DataFrame],
    joins: List[Dict[str, str]],
    ratio: float,
    rng: random.Random,
) -> Dict[str, pd.DataFrame]:
    if ratio >= 0.999:
        return {k: v.copy() for k, v in tables.items()}

    # Pick anchor as the smallest table among join-participating tables for stable key subset.
    join_tables = {j["left_table"] for j in joins} | {j["right_table"] for j in joins}
    candidates = [(t, len(df)) for t, df in tables.items() if t in join_tables]
    if not candidates:
        candidates = [(t, len(df)) for t, df in tables.items()]
    candidates.sort(key=lambda x: x[1])
    anchor = candidates[0][0]

    sampled = {k: v.copy() for k, v in tables.items()}
    anchor_df = sampled[anchor]
    n = max(1, int(len(anchor_df) * ratio))
    if n < len(anchor_df):
        sampled[anchor] = anchor_df.sample(n=n, random_state=rng.randint(1, 10_000_000)).reset_index(drop=True)
    sampled = _iterative_join_filter(sampled, joins, max_iter=15)

    # Guard: if any join table becomes empty, fallback to less aggressive sample.
    join_tables = {j["left_table"] for j in joins} | {j["right_table"] for j in joins}
    if any(len(sampled[t]) == 0 for t in join_tables):
        # one-step fallback
        ratio2 = min(0.9, (ratio + 1.0) / 2.0)
        sampled = {k: v.copy() for k, v in tables.items()}
        n2 = max(1, int(len(sampled[anchor]) * ratio2))
        if n2 < len(sampled[anchor]):
            sampled[anchor] = sampled[anchor].sample(n=n2, random_state=rng.randint(1, 10_000_000)).reset_index(drop=True)
        sampled = _iterative_join_filter(sampled, joins, max_iter=15)

    return sampled


def _write_variant_canonical(
    sampled_tables: Dict[str, pd.DataFrame],
    formats: Dict[str, str],
    variant_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    variant_dir.mkdir(parents=True, exist_ok=True)

    sqlite_fp = variant_dir / "core_data.sqlite"
    if sqlite_fp.exists():
        sqlite_fp.unlink()

    table_registry: Dict[str, Dict[str, Any]] = {}

    sconn = sqlite3.connect(str(sqlite_fp))
    try:
        for table, df in sampled_tables.items():
            fmt = formats[table]
            if fmt == "sqlite":
                df.to_sql(table, sconn, index=False, if_exists="replace")
                table_registry[table] = {
                    "storage_type": "sqlite",
                    "file": sqlite_fp.name,
                    "table_name": table,
                    "columns": list(df.columns),
                    "row_count": int(len(df)),
                }
            elif fmt == "csv":
                fp = variant_dir / f"{table}.csv"
                df.to_csv(fp, index=False)
                table_registry[table] = {
                    "storage_type": "csv",
                    "file": fp.name,
                    "table_name": table,
                    "columns": list(df.columns),
                    "row_count": int(len(df)),
                }
            elif fmt == "parquet":
                fp = variant_dir / f"{table}.parquet"
                df.to_parquet(fp, index=False)
                table_registry[table] = {
                    "storage_type": "parquet",
                    "file": fp.name,
                    "table_name": table,
                    "columns": list(df.columns),
                    "row_count": int(len(df)),
                }
            else:
                raise ValueError(f"Unknown format {fmt}")
    finally:
        sconn.close()

    return table_registry


def _run_sql_on_variant_sqlite(tables: Dict[str, pd.DataFrame], sql: str, sqlite_path: Path) -> pd.DataFrame:
    if sqlite_path.exists():
        sqlite_path.unlink()
    conn = sqlite3.connect(str(sqlite_path))
    try:
        for table, df in tables.items():
            df.to_sql(table, conn, index=False, if_exists="replace")
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def _write_l0_baseline(
    seed: Dict[str, Any],
    sampled_tables: Dict[str, pd.DataFrame],
    gold_sql: str,
    l0_dir: Path,
) -> Dict[str, Any]:
    """Generate L0 baseline: sampled tables in one SQLite with original names."""
    l0_dir.mkdir(parents=True, exist_ok=True)

    sqlite_fp = l0_dir / f"{seed['db_id']}.sqlite"
    if sqlite_fp.exists():
        sqlite_fp.unlink()

    table_registry: Dict[str, Dict[str, Any]] = {}
    conn = sqlite3.connect(str(sqlite_fp))
    try:
        for table, df in sampled_tables.items():
            df.to_sql(table, conn, index=False, if_exists="replace")
            table_registry[table] = {
                "storage_type": "sqlite",
                "file": sqlite_fp.name,
                "table_name": table,
                "columns": list(df.columns),
                "row_count": int(len(df)),
            }

        gold_df = pd.read_sql_query(gold_sql, conn)
        gold_df.to_csv(l0_dir / "gold.csv", index=False)
    finally:
        conn.close()

    (l0_dir / "gold.sql").write_text(gold_sql, encoding="utf-8")
    l0_meta = {
        "db_id": seed["db_id"],
        "sqlite_path": str(sqlite_fp),
        "gold_sql_path": str(l0_dir / "gold.sql"),
        "gold_csv_path": str(l0_dir / "gold.csv"),
        "table_registry": table_registry,
        "gold_rows": int(len(gold_df)),
    }
    (l0_dir / "manifest_l0.json").write_text(json.dumps(l0_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return l0_meta


def build_universe_a_for_seed(
    seed: Dict[str, Any],
    out_seed_dir: Path,
    random_seed: int,
    min_gold_rows: int = 1,
) -> Dict[str, Any]:
    rng = random.Random(random_seed)

    db_path = Path(seed["db_path"])
    tables = list(seed["tables"])
    joins = list(seed["joins"])

    raw_tables = {t: _load_table(db_path, t) for t in tables}

    fact = _choose_fact_table(db_path, tables)
    formats = _initial_format_assignment(tables, fact)
    formats = _enforce_cross_format_joins(formats, joins, fact_table=fact)

    variants_root = out_seed_dir / "variants"
    variants_root.mkdir(parents=True, exist_ok=True)

    variant_summaries: Dict[str, Any] = {}

    for vid, ratio in VARIANTS.items():
        variant_dir = variants_root / vid / "universe_a"
        sampled = _cascade_sample(raw_tables, joins, ratio=ratio, rng=rng)

        # Guard against empty key tables.
        if any(len(sampled[t]) == 0 for t in tables):
            raise ValueError(f"Variant {vid} for {seed['seed_id']} produced empty table after cascade sampling")

        l0_dir = variants_root / vid / "universe_l0"
        l0_meta = _write_l0_baseline(seed, sampled, seed["gold_sql"], l0_dir)

        registry = _write_variant_canonical(sampled, formats, variant_dir)

        rewritten_script = build_duckdb_script(
            gold_sql=seed["gold_sql"],
            table_registry=registry,
            workspace_dir=variant_dir,
        )
        duck_df = execute_duckdb_script(rewritten_script)

        sqlite_check_path = variant_dir / "_variant_check.sqlite"
        sqlite_df = _run_sql_on_variant_sqlite(sampled, seed["gold_sql"], sqlite_check_path)
        l0_gold_df = pd.read_csv(l0_dir / "gold.csv")

        if not compare_frames(sqlite_df, duck_df, float_tol=1e-6):
            raise ValueError(f"Universe A validation failed for {seed['seed_id']} variant {vid}")
        if not compare_frames(sqlite_df, l0_gold_df, float_tol=1e-6):
            raise ValueError(f"L0 validation failed for {seed['seed_id']} variant {vid}")
        if len(duck_df) < min_gold_rows:
            raise ValueError(
                f"Universe A gold too small for {seed['seed_id']} variant {vid}: "
                f"{len(duck_df)} rows < min_gold_rows={min_gold_rows}"
            )

        (variant_dir / "rewritten_sql.sql").write_text(rewritten_script, encoding="utf-8")
        duck_df.to_csv(variant_dir / "gold.csv", index=False)
        if sqlite_check_path.exists():
            sqlite_check_path.unlink()

        explosion_log = {
            "seed_id": seed["seed_id"],
            "variant": vid,
            "db_id": seed["db_id"],
            "fact_table": fact,
            "formats": formats,
            "tables": tables,
            "joins": joins,
            "join_key_columns": seed.get("join_key_columns", {}),
            "table_registry": registry,
            "ratio": ratio,
        }
        (variant_dir / "explosion_log.json").write_text(
            json.dumps(explosion_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        variant_summaries[vid] = {
            "ratio": ratio,
            "rows": {t: int(len(df)) for t, df in sampled.items()},
            "universe_a_dir": str(variant_dir),
            "universe_l0_dir": str(l0_dir),
            "universe_l0": l0_meta,
        }

    seed_summary = {
        "seed_id": seed["seed_id"],
        "db_id": seed["db_id"],
        "variants": variant_summaries,
    }
    (out_seed_dir / "universe_a_summary.json").write_text(
        json.dumps(seed_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return seed_summary
