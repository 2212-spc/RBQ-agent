from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Tuple

import duckdb
import pandas as pd
from sqlglot import exp, parse_one

from construction.seed_tools import parse_sql_metadata


@dataclass
class SourceInfo:
    view_name: str
    file_name: str
    file_path: Path
    storage_type: str
    columns: List[str]
    sample: pd.DataFrame
    table_name: str | None = None


def _escape_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _scan_expr(source: SourceInfo) -> str:
    uri = _escape_path(source.file_path)
    if source.storage_type == "csv":
        return f"read_csv_auto('{uri}')"
    if source.storage_type == "parquet":
        return f"read_parquet('{uri}')"
    if source.storage_type == "sqlite":
        if not source.table_name:
            raise ValueError("sqlite source requires table_name")
        return f"sqlite_scan('{uri}', '{source.table_name}')"
    raise ValueError(f"Unsupported source type: {source.storage_type}")


def _norm_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _norm_sep(value: Any) -> str:
    text = _norm_text(value).lower()
    text = re.sub(r"[-_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _norm_digits(value: Any) -> str:
    text = _norm_text(value)
    digits = "".join(re.findall(r"\d+", text))
    if not digits:
        return text
    try:
        return str(int(digits))
    except Exception:  # noqa: BLE001
        return digits


def _norm_date(value: Any) -> str:
    if pd.isna(value):
        return ""
    parsed = pd.to_datetime([value], errors="coerce")
    if parsed.isna().all():
        return _norm_text(value)
    return parsed.strftime("%Y-%m-%d")[0]


def _sql_expr(norm_name: str, col_name: str) -> str:
    col = f'"{col_name}"'
    if norm_name == "digits":
        return f"CAST(regexp_extract(CAST({col} AS VARCHAR), '[0-9]+') AS BIGINT)"
    if norm_name == "sep":
        return f"replace(replace(lower(CAST({col} AS VARCHAR)), '-', ' '), '_', ' ')"
    if norm_name == "date":
        return (
            "coalesce("
            f"strftime(try_strptime(CAST({col} AS VARCHAR), '%d/%m/%Y'), '%Y-%m-%d'), "
            f"strftime(try_strptime(CAST({col} AS VARCHAR), '%m-%d-%Y'), '%Y-%m-%d'), "
            f"strftime(try_strptime(CAST({col} AS VARCHAR), '%d %b %Y'), '%Y-%m-%d'), "
            f"strftime(try_strptime(CAST({col} AS VARCHAR), '%Y-%m-%d'), '%Y-%m-%d'), "
            f"CAST({col} AS VARCHAR)"
            ")"
        )
    return col


def _tokenize(name: str) -> List[str]:
    return [tok for tok in re.split(r"[^a-z0-9]+", name.lower()) if tok]


def _name_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    ta = set(_tokenize(a))
    tb = set(_tokenize(b))
    if ta and tb:
        jaccard = len(ta & tb) / len(ta | tb)
    else:
        jaccard = 0.0
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(jaccard, seq)


def _is_key_like(col: str) -> bool:
    c = col.lower()
    return bool(re.fullmatch(r"k\d+", c) or "id" in c or c.endswith("_key") or c.endswith("key"))


def _discover_sources(workspace: Path) -> Tuple[List[SourceInfo], List[str]]:
    sources: List[SourceInfo] = []
    touched: List[str] = []
    for fp in sorted(workspace.iterdir()):
        if not fp.is_file():
            continue
        touched.append(fp.name)
        ext = fp.suffix.lower()
        if ext == ".csv":
            sample = pd.read_csv(fp, nrows=50)
            sources.append(
                SourceInfo(
                    view_name=fp.stem,
                    file_name=fp.name,
                    file_path=fp,
                    storage_type="csv",
                    columns=list(sample.columns),
                    sample=sample,
                )
            )
        elif ext == ".parquet":
            sample = pd.read_parquet(fp).head(50)
            sources.append(
                SourceInfo(
                    view_name=fp.stem,
                    file_name=fp.name,
                    file_path=fp,
                    storage_type="parquet",
                    columns=list(sample.columns),
                    sample=sample,
                )
            )
        elif ext == ".sqlite":
            conn = sqlite3.connect(str(fp))
            try:
                tables = [
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    ).fetchall()
                ]
                for table in tables:
                    sample = pd.read_sql_query(f"SELECT * FROM '{table}' LIMIT 50", conn)
                    sources.append(
                        SourceInfo(
                            view_name=table,
                            file_name=fp.name,
                            file_path=fp,
                            storage_type="sqlite",
                            columns=list(sample.columns),
                            sample=sample,
                            table_name=table,
                        )
                    )
            finally:
                conn.close()
    return sources, touched


def _extract_filter_hints(gold_sql: str) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    tree = parse_one(gold_sql, read="sqlite")
    alias_map = {tbl.alias_or_name: tbl.name for tbl in tree.find_all(exp.Table)}
    hints: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    compare_types = (exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE)
    for node in tree.find_all(compare_types):
        left = node.left
        right = node.right
        if isinstance(left, exp.Column) and isinstance(right, exp.Literal):
            table = alias_map.get(left.table, left.table)
            if not table:
                continue
            hints.setdefault(table, {}).setdefault(left.name, []).append(
                {"op": node.key.upper(), "literal": right.this}
            )
        elif isinstance(right, exp.Column) and isinstance(left, exp.Literal):
            table = alias_map.get(right.table, right.table)
            if not table:
                continue
            hints.setdefault(table, {}).setdefault(right.name, []).append(
                {"op": node.key.upper(), "literal": left.this}
            )
    return hints


def _literal_match_score(series: pd.Series, hints: List[Dict[str, Any]]) -> float:
    if not hints:
        return 0.0
    score = 0.0
    sample = series.dropna().head(50)
    if sample.empty:
        return 0.0
    for hint in hints:
        literal = hint["literal"]
        op = hint["op"]
        if re.fullmatch(r"-?\d+(\.\d+)?", str(literal)):
            values = pd.to_numeric(sample, errors="coerce").dropna()
            if values.empty:
                continue
            target = float(literal)
            if op == "EQ":
                if (values == target).any():
                    score += 2.0
            elif op in {"GT", "GTE", "LT", "LTE"}:
                score += 1.0
        else:
            sval = str(literal).strip().strip("'").strip('"').lower()
            normalized = sample.astype(str).str.lower().str.strip()
            if normalized.eq(sval).any():
                score += 3.0
            elif normalized.str.contains(re.escape(sval), regex=True).any():
                score += 1.5
    return score


def _table_score(
    canonical_table: str,
    referenced_cols: List[str],
    source: SourceInfo,
    filter_hints: Dict[str, List[Dict[str, Any]]],
) -> float:
    score = 0.0
    if source.view_name.lower() == canonical_table.lower():
        score += 100.0

    source_cols = set(source.columns)
    exact_overlap = len([c for c in referenced_cols if c in source_cols])
    score += exact_overlap * 15.0

    nonkey_overlap = len([c for c in referenced_cols if c in source_cols and not _is_key_like(c)])
    score += nonkey_overlap * 10.0

    for canonical_col, hints in filter_hints.items():
        if canonical_col in source.columns:
            score += 10.0 + _literal_match_score(source.sample[canonical_col], hints)
        else:
            best = 0.0
            for source_col in source.columns:
                best = max(best, _literal_match_score(source.sample[source_col], hints))
            score += best

    if any(col in source_cols for col in referenced_cols):
        score += 5.0
    return score


def _candidate_key_columns(source: SourceInfo) -> List[str]:
    candidates = [c for c in source.columns if _is_key_like(c)]
    if candidates:
        return candidates
    return list(source.columns)


def _best_norm_overlap(left: pd.Series, right: pd.Series) -> Tuple[float, str, str]:
    strategies = {
        "identity": _norm_text,
        "digits": _norm_digits,
        "sep": _norm_sep,
        "date": _norm_date,
    }
    best = (0.0, "identity", "identity")
    for left_name, left_fn in strategies.items():
        lset = {left_fn(v) for v in left.dropna().tolist() if left_fn(v)}
        if not lset:
            continue
        for right_name, right_fn in strategies.items():
            rset = {right_fn(v) for v in right.dropna().tolist() if right_fn(v)}
            if not rset:
                continue
            inter = lset & rset
            union = lset | rset
            score = len(inter) / len(union) if union else 0.0
            if score > best[0]:
                best = (score, left_name, right_name)
    return best


def _map_tables(
    gold_sql: str,
    sources: List[SourceInfo],
) -> Tuple[Dict[str, SourceInfo], Dict[str, Any]]:
    meta = parse_sql_metadata(gold_sql)
    filter_hints = _extract_filter_hints(gold_sql)
    candidates_by_table: Dict[str, List[Tuple[float, SourceInfo]]] = {}
    for canonical_table in meta["tables"]:
        referenced_cols = meta.get("table_columns", {}).get(canonical_table, [])
        scores = []
        for source in sources:
            score = _table_score(canonical_table, referenced_cols, source, filter_hints.get(canonical_table, {}))
            scores.append((score, source))
        scores.sort(key=lambda x: x[0], reverse=True)
        if not scores:
            raise ValueError(f"No source candidates for canonical table {canonical_table}")
        candidates_by_table[canonical_table] = scores[:3]

    best_combo_score: float | None = None
    best_combo: Dict[str, SourceInfo] | None = None
    table_order = list(meta["tables"])
    join_key_columns = meta.get("join_key_columns", {})

    for combo in product(*[candidates_by_table[t] for t in table_order]):
        combo_views = [source.view_name for _score, source in combo]
        if len(set(combo_views)) != len(combo_views):
            continue

        combo_map = {table: source for table, (_score, source) in zip(table_order, combo)}
        combo_score = sum(score for score, _source in combo)

        for edge in meta.get("joins", []):
            left_source = combo_map[edge["left_table"]]
            right_source = combo_map[edge["right_table"]]
            left_candidates = _candidate_key_columns(left_source)
            right_candidates = _candidate_key_columns(right_source)
            if edge["left_col"] in left_source.columns:
                left_candidates = [edge["left_col"]] + [c for c in left_candidates if c != edge["left_col"]]
            if edge["right_col"] in right_source.columns:
                right_candidates = [edge["right_col"]] + [c for c in right_candidates if c != edge["right_col"]]

            best_join = 0.0
            for lcol in left_candidates:
                for rcol in right_candidates:
                    overlap, _lnorm, _rnorm = _best_norm_overlap(left_source.sample[lcol], right_source.sample[rcol])
                    exact_bonus = 0.2 if (
                        lcol in join_key_columns.get(edge["left_table"], [])
                        or rcol in join_key_columns.get(edge["right_table"], [])
                    ) else 0.0
                    best_join = max(best_join, overlap + exact_bonus)
            combo_score += best_join * 50.0

        if best_combo_score is None or combo_score > best_combo_score:
            best_combo_score = combo_score
            best_combo = combo_map

    if best_combo is None:
        raise ValueError("Failed to select a consistent source combination")

    debug: Dict[str, Any] = {}
    for canonical_table in table_order:
        chosen = best_combo[canonical_table]
        scored_candidates = candidates_by_table[canonical_table]
        selected_score = next(score for score, src in scored_candidates if src.view_name == chosen.view_name)
        debug[canonical_table] = {
            "selected_view": chosen.view_name,
            "selected_file": chosen.file_name,
            "score": round(float(selected_score), 4),
            "top_candidates": [
                {"view": src.view_name, "file": src.file_name, "score": round(float(score), 4)}
                for score, src in scored_candidates
            ],
        }
    return best_combo, debug


def _choose_nonjoin_column(
    canonical_col: str,
    source: SourceInfo,
    used_columns: set[str],
    filter_hints: List[Dict[str, Any]],
) -> str:
    if canonical_col in source.columns and canonical_col not in used_columns:
        return canonical_col

    scored: List[Tuple[float, str]] = []
    for source_col in source.columns:
        if source_col in used_columns:
            continue
        score = _name_similarity(canonical_col, source_col) * 5.0
        score += _literal_match_score(source.sample[source_col], filter_hints)
        if _is_key_like(source_col) and not _is_key_like(canonical_col):
            score -= 1.0
        scored.append((score, source_col))
    if not scored:
        raise ValueError(f"No source columns available for {canonical_col}")
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _build_column_mappings(
    gold_sql: str,
    table_map: Dict[str, SourceInfo],
) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]], Dict[str, Any]]:
    meta = parse_sql_metadata(gold_sql)
    filter_hints = _extract_filter_hints(gold_sql)
    join_key_columns = {k: set(v) for k, v in meta.get("join_key_columns", {}).items()}

    col_map: Dict[str, Dict[str, str]] = {}
    inverse_map: Dict[str, Dict[str, str]] = {}
    debug: Dict[str, Any] = {}

    for canonical_table, source in table_map.items():
        used_columns: set[str] = set()
        col_map[canonical_table] = {}
        inverse_map[canonical_table] = {}
        debug[canonical_table] = {}
        for canonical_col in meta.get("table_columns", {}).get(canonical_table, []):
            if canonical_col in join_key_columns.get(canonical_table, set()):
                continue
            chosen = _choose_nonjoin_column(
                canonical_col=canonical_col,
                source=source,
                used_columns=used_columns,
                filter_hints=filter_hints.get(canonical_table, {}).get(canonical_col, []),
            )
            used_columns.add(chosen)
            col_map[canonical_table][canonical_col] = chosen
            inverse_map[canonical_table][canonical_col] = "identity"
            debug[canonical_table][canonical_col] = {"source_col": chosen, "norm": "identity"}

    for edge in meta.get("joins", []):
        left_table = edge["left_table"]
        right_table = edge["right_table"]
        left_canonical = edge["left_col"]
        right_canonical = edge["right_col"]

        left_source = table_map[left_table]
        right_source = table_map[right_table]

        left_candidates = _candidate_key_columns(left_source)
        right_candidates = _candidate_key_columns(right_source)

        if left_canonical in left_source.columns:
            left_candidates = [left_canonical] + [c for c in left_candidates if c != left_canonical]
        if right_canonical in right_source.columns:
            right_candidates = [right_canonical] + [c for c in right_candidates if c != right_canonical]

        best_pair: Tuple[float, str, str, str, str] | None = None
        for lcol in left_candidates:
            for rcol in right_candidates:
                score, lnorm, rnorm = _best_norm_overlap(left_source.sample[lcol], right_source.sample[rcol])
                exact_bonus = 0.2 if lcol == left_canonical or rcol == right_canonical else 0.0
                final_score = score + exact_bonus
                if best_pair is None or final_score > best_pair[0]:
                    best_pair = (final_score, lcol, rcol, lnorm, rnorm)

        if best_pair is None:
            raise ValueError(f"Failed to map join columns for {left_table}.{left_canonical}")

        _, lcol, rcol, lnorm, rnorm = best_pair
        col_map[left_table][left_canonical] = lcol
        col_map[right_table][right_canonical] = rcol
        inverse_map[left_table][left_canonical] = lnorm
        inverse_map[right_table][right_canonical] = rnorm
        debug[left_table][left_canonical] = {"source_col": lcol, "norm": lnorm}
        debug[right_table][right_canonical] = {"source_col": rcol, "norm": rnorm}

    return col_map, inverse_map, debug


def _build_agent_sql(
    gold_sql: str,
    table_map: Dict[str, SourceInfo],
    column_map: Dict[str, Dict[str, str]],
    inverse_map: Dict[str, Dict[str, str]],
) -> str:
    stmts: List[str] = []
    for canonical_table, source in table_map.items():
        projections = []
        for canonical_col, source_col in column_map[canonical_table].items():
            norm_name = inverse_map[canonical_table].get(canonical_col, "identity")
            expr = _sql_expr(norm_name, source_col)
            projections.append(f'{expr} AS "{canonical_col}"')
        select_clause = ", ".join(projections)
        stmts.append(
            f'CREATE OR REPLACE TEMP VIEW "{canonical_table}" AS '
            f"SELECT {select_clause} FROM {_scan_expr(source)};"
        )
    stmts.append(gold_sql.strip().rstrip(";") + ";")
    return "\n".join(stmts)


def run_duckdb_agent(
    instruction: str,
    workspace: Path,
    gold_sql: str | None,
    output_csv: Path,
) -> Dict[str, Any]:
    del instruction  # The MVP baseline uses the logical plan and solves discovery/alignment.

    if not gold_sql:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(output_csv, index=False)
        return {
            "success": False,
            "files_touched": [],
            "error": "gold_sql unavailable: duckdb_agent currently supports dev mode only",
            "selected_tables": {},
            "selected_columns": {},
            "sql_script": "",
        }

    sources, touched = _discover_sources(workspace)
    table_map, table_debug = _map_tables(gold_sql, sources)
    column_map, inverse_map, column_debug = _build_column_mappings(gold_sql, table_map)
    sql_script = _build_agent_sql(gold_sql, table_map, column_map, inverse_map)

    conn = duckdb.connect(database=":memory:")
    try:
        conn.execute("INSTALL sqlite;")
        conn.execute("LOAD sqlite;")
        stmts = [stmt.strip() for stmt in sql_script.split(";") if stmt.strip()]
        for stmt in stmts[:-1]:
            conn.execute(stmt)
        df = conn.execute(stmts[-1]).fetchdf()
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, index=False)
        return {
            "success": True,
            "files_touched": touched,
            "error": None,
            "selected_tables": table_debug,
            "selected_columns": column_debug,
            "sql_script": sql_script,
        }
    except Exception as exc:  # noqa: BLE001
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(output_csv, index=False)
        return {
            "success": False,
            "files_touched": touched,
            "error": str(exc),
            "selected_tables": table_debug,
            "selected_columns": column_debug,
            "sql_script": sql_script,
        }
    finally:
        conn.close()
