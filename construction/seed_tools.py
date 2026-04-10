from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlglot import exp, parse_one


def load_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def dump_json(path: str | Path, payload: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def list_sqlite_tables(db_path: str | Path) -> List[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def sqlite_table_columns(db_path: str | Path, table: str) -> List[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    finally:
        conn.close()
    return [r[1] for r in rows]


def sqlite_table_column_types(db_path: str | Path, table: str) -> Dict[str, str]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    finally:
        conn.close()
    # row[1] -> col name, row[2] -> declared type
    return {r[1]: str(r[2]).upper() for r in rows}


def sqlite_table_row_count(db_path: str | Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM '{table}'").fetchone()
    finally:
        conn.close()
    return int(row[0]) if row else 0


def _resolve_table(alias_or_name: Optional[str], alias_map: Dict[str, str]) -> Optional[str]:
    if not alias_or_name:
        return None
    return alias_map.get(alias_or_name, alias_or_name)


def parse_sql_metadata(sql: str) -> Dict[str, Any]:
    tree = parse_one(sql, read="sqlite")

    alias_map: Dict[str, str] = {}
    ordered_tables: List[str] = []
    for tbl in tree.find_all(exp.Table):
        table_name = tbl.name
        alias = tbl.alias_or_name
        if alias:
            alias_map[alias] = table_name
        if table_name not in ordered_tables:
            ordered_tables.append(table_name)

    table_columns: Dict[str, Set[str]] = defaultdict(set)
    for col in tree.find_all(exp.Column):
        table = _resolve_table(col.table, alias_map)
        if table:
            table_columns[table].add(col.name)

    joins: List[Dict[str, str]] = []
    join_key_columns: Dict[str, Set[str]] = defaultdict(set)
    where_columns: Dict[str, Set[str]] = defaultdict(set)
    groupby_columns: Dict[str, Set[str]] = defaultdict(set)

    for eq in tree.find_all(exp.EQ):
        left = eq.left
        right = eq.right
        if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
            continue

        l_table = _resolve_table(left.table, alias_map)
        r_table = _resolve_table(right.table, alias_map)
        if not l_table or not r_table or l_table == r_table:
            continue

        joins.append(
            {
                "left_table": l_table,
                "left_col": left.name,
                "right_table": r_table,
                "right_col": right.name,
            }
        )
        join_key_columns[l_table].add(left.name)
        join_key_columns[r_table].add(right.name)

    group = tree.args.get("group")
    if group:
        for g in group.expressions:
            if isinstance(g, exp.Column):
                t = _resolve_table(g.table, alias_map)
                if t:
                    groupby_columns[t].add(g.name)

    where = tree.args.get("where")
    if where:
        for col in where.find_all(exp.Column):
            t = _resolve_table(col.table, alias_map)
            if t:
                where_columns[t].add(col.name)

    key_columns_by_table: Dict[str, Set[str]] = defaultdict(set)
    for t, cols in join_key_columns.items():
        key_columns_by_table[t].update(cols)
    for t, cols in groupby_columns.items():
        key_columns_by_table[t].update(cols)
    for t, cols in where_columns.items():
        key_columns_by_table[t].update(cols)

    return {
        "tables": ordered_tables,
        "alias_map": alias_map,
        "table_columns": {k: sorted(v) for k, v in table_columns.items()},
        "joins": joins,
        "join_key_columns": {k: sorted(v) for k, v in join_key_columns.items()},
        "groupby_columns": {k: sorted(v) for k, v in groupby_columns.items()},
        "where_columns": {k: sorted(v) for k, v in where_columns.items()},
        "key_columns_by_table": {k: sorted(v) for k, v in key_columns_by_table.items()},
        "key_columns": sorted(
            {f"{t}.{c}" for t, cols in key_columns_by_table.items() for c in cols}
        ),
    }


def used_and_unused_tables(db_path: str | Path, used_tables: Iterable[str]) -> Tuple[List[str], List[str]]:
    all_tables = list_sqlite_tables(db_path)
    used = set(used_tables)
    unused = [t for t in all_tables if t not in used]
    return all_tables, unused


def choose_fact_table(db_path: str | Path, tables: Iterable[str]) -> str:
    candidates = list(tables)
    if not candidates:
        raise ValueError("No tables available to choose fact table.")
    counts = [(t, sqlite_table_row_count(db_path, t)) for t in candidates]
    counts.sort(key=lambda x: x[1], reverse=True)
    return counts[0][0]


def count_joins(sql_meta: Dict[str, Any]) -> int:
    return len(sql_meta.get("joins", []))


def ensure_min_join_count(sql_meta: Dict[str, Any], min_joins: int = 1) -> bool:
    return count_joins(sql_meta) >= min_joins
