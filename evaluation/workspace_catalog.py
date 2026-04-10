from __future__ import annotations

import re
import sqlite3
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

import duckdb
import pandas as pd

from evaluation.duckdb_agent import _best_norm_overlap


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "show",
    "the",
    "to",
    "what",
    "which",
    "who",
    "with",
}

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    for token in re.split(r"[^a-z0-9]+", text.lower()):
        if not token or token in STOPWORDS:
            continue
        tokens.append(token)
        if len(token) > 3 and token.endswith("s"):
            singular = token[:-1]
            if singular and singular not in STOPWORDS:
                tokens.append(singular)
    return tokens


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug or "item"


def source_view_name(file_name: str, table_name: str | None) -> str:
    if table_name:
        return slugify(f"{Path(file_name).stem}_{table_name}")
    return slugify(Path(file_name).stem)


def extract_time_hints(text: str) -> Dict[str, List[int]]:
    lower = text.lower()
    years = [int(match) for match in re.findall(r"\b(19\d{2}|20\d{2})\b", lower)]
    months = sorted({month for token, month in MONTHS.items() if re.search(rf"\b{re.escape(token)}\b", lower)})
    return {"years": years, "months": months}


def _coerce_number_token(token: str) -> float | None:
    token = token.strip().lower()
    if token in NUMBER_WORDS:
        return float(NUMBER_WORDS[token])
    try:
        return float(token)
    except Exception:
        return None


def extract_numeric_filters(text: str) -> List[Dict[str, Any]]:
    lower = text.lower()
    patterns = [
        (r"(more than|greater than|over)\s+([a-z0-9]+)\s+([a-z_]+)", ">"),
        (r"(less than|under)\s+([a-z0-9]+)\s+([a-z_]+)", "<"),
        (r"(at least|no less than)\s+([a-z0-9]+)\s+([a-z_]+)", ">="),
        (r"(at most|no more than)\s+([a-z0-9]+)\s+([a-z_]+)", "<="),
    ]
    filters: List[Dict[str, Any]] = []
    for pattern, operator in patterns:
        for _, raw_value, attribute in re.findall(pattern, lower):
            value = _coerce_number_token(raw_value)
            if value is None:
                continue
            filters.append({"operator": operator, "value": value, "attribute": attribute})
    return filters


def _safe_preview_df(df: pd.DataFrame, limit: int = 3) -> List[Dict[str, Any]]:
    if df.empty:
        return []
    preview = df.head(limit).copy()
    preview = preview.where(pd.notna(preview), None)
    records = preview.to_dict(orient="records")
    for record in records:
        for key, value in list(record.items()):
            if isinstance(value, str) and len(value) > 120:
                record[key] = value[:117] + "..."
    return records


def _describe_file(fp: Path) -> Dict[str, Any]:
    ext = fp.suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(fp, nrows=5)
        return {
            "file": fp.name,
            "type": "csv",
            "tables": [{"name": fp.stem, "columns": list(df.columns), "sample_rows": _safe_preview_df(df)}],
        }
    if ext == ".parquet":
        df = pd.read_parquet(fp).head(5)
        return {
            "file": fp.name,
            "type": "parquet",
            "tables": [{"name": fp.stem, "columns": list(df.columns), "sample_rows": _safe_preview_df(df)}],
        }
    if ext == ".sqlite":
        conn = sqlite3.connect(str(fp))
        try:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            payload = []
            for table_name in tables:
                df = pd.read_sql_query(f"SELECT * FROM '{table_name}' LIMIT 5", conn)
                payload.append(
                    {
                        "name": table_name,
                        "columns": list(df.columns),
                        "sample_rows": _safe_preview_df(df),
                    }
                )
            return {"file": fp.name, "type": "sqlite", "tables": payload}
        finally:
            conn.close()
    return {"file": fp.name, "type": ext.lstrip(".") or "unknown", "tables": []}


def summarize_workspace(workspace: Path) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    for fp in sorted(workspace.iterdir()):
        if not fp.is_file():
            continue
        files.append(_describe_file(fp))
    return {"workspace_name": workspace.name, "files": files}


@dataclass(slots=True)
class ColumnProfile:
    source_id: str
    column_name: str
    dtype: str
    null_rate: float
    unique_ratio: float
    numeric_ratio: float
    date_ratio: float
    alpha_ratio: float
    digit_ratio: float
    avg_length: float
    sample_values: List[str]
    key_like: bool
    text_like: bool
    time_like: bool
    measure_like: bool


@dataclass(slots=True)
class SourceProfile:
    source_id: str
    file_name: str
    file_path: Path
    storage_type: str
    table_name: str | None
    raw_view_name: str
    row_count: int
    role_hint: str
    sample_rows: List[Dict[str, Any]]
    column_profiles: Dict[str, ColumnProfile]

    @property
    def columns(self) -> List[str]:
        return list(self.column_profiles)

    @property
    def key_columns(self) -> List[str]:
        return [name for name, profile in self.column_profiles.items() if profile.key_like]


@dataclass(slots=True)
class JoinEdge:
    edge_id: str
    left_source_id: str
    right_source_id: str
    left_column: str
    right_column: str
    left_transform: str
    right_transform: str
    overlap: float


@dataclass(slots=True)
class WorkspaceCatalog:
    workspace: Path
    sources: Dict[str, SourceProfile]
    join_edges: List[JoinEdge]
    files_touched: List[str] = field(default_factory=list)

    def source(self, source_id: str) -> SourceProfile:
        return self.sources[source_id]

    def join_neighbors(self, source_id: str) -> List[JoinEdge]:
        return [
            edge
            for edge in self.join_edges
            if edge.left_source_id == source_id or edge.right_source_id == source_id
        ]

    def find_best_edge(self, left_source_id: str, right_source_id: str) -> JoinEdge | None:
        candidates = [
            edge
            for edge in self.join_edges
            if {edge.left_source_id, edge.right_source_id} == {left_source_id, right_source_id}
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda edge: edge.overlap)

    def find_best_path(self, start_source_id: str, target_source_id: str, max_hops: int = 2) -> List[JoinEdge]:
        if start_source_id == target_source_id:
            return []
        direct = self.find_best_edge(start_source_id, target_source_id)
        if max_hops < 2:
            return [direct] if direct is not None else []

        best_path: List[JoinEdge] = []
        best_score = -1.0
        for mid_source_id in self.sources:
            if mid_source_id in {start_source_id, target_source_id}:
                continue
            left = self.find_best_edge(start_source_id, mid_source_id)
            right = self.find_best_edge(mid_source_id, target_source_id)
            if left is None or right is None:
                continue
            score = left.overlap + right.overlap
            if score > best_score:
                best_score = score
                best_path = [left, right]

        # Compare by average overlap per hop so that a 2-hop path must have
        # higher per-edge quality than the direct edge to win.
        # This avoids wrong direct-edge shortcuts in junction-table schemas
        # (e.g. Host_ID=Party_ID) while still keeping strong 1-hop FKs.
        if best_path and (direct is None or best_score > 2.0 * direct.overlap):
            return best_path
        return [direct] if direct is not None else []


def _safe_sample_values(series: pd.Series, limit: int = 20) -> List[str]:
    values = []
    unique = series.dropna().unique()
    # Use a spread sample: head + tail + random middle for better coverage
    if len(unique) <= limit:
        sampled = unique
    else:
        head_n = min(limit // 3, len(unique))
        tail_n = min(limit // 3, len(unique) - head_n)
        mid_n = limit - head_n - tail_n
        sampled = list(unique[:head_n]) + list(unique[-tail_n:])
        mid_indices = range(head_n, len(unique) - tail_n)
        if mid_n > 0 and len(mid_indices) > 0:
            import random
            rng = random.Random(42)  # deterministic
            mid_sample = rng.sample(range(head_n, len(unique) - tail_n), min(mid_n, len(mid_indices)))
            sampled.extend(unique[i] for i in mid_sample)
    for value in sampled[:limit]:
        text = str(value)
        if len(text) > 80:
            text = text[:77] + "..."
        values.append(text)
    return values


def _build_column_profile(source_id: str, column_name: str, series: pd.Series) -> ColumnProfile:
    sample = series.dropna().head(50)
    str_sample = sample.astype(str) if not sample.empty else pd.Series(dtype="object")
    numeric_ratio = pd.to_numeric(sample, errors="coerce").notna().mean() if not sample.empty else 0.0
    if not sample.empty:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            date_ratio = pd.to_datetime(sample.astype(str), errors="coerce").notna().mean()
    else:
        date_ratio = 0.0
    alpha_ratio = str_sample.str.contains(r"[A-Za-z]", regex=True).mean() if not sample.empty else 0.0
    digit_ratio = str_sample.str.contains(r"\d", regex=True).mean() if not sample.empty else 0.0
    avg_length = str_sample.map(len).mean() if not sample.empty else 0.0
    non_null = series.dropna()
    unique_ratio = non_null.nunique() / max(len(non_null), 1) if len(non_null) else 0.0
    null_rate = series.isna().mean() if len(series) else 0.0
    lower_name = column_name.lower()
    text_like = alpha_ratio >= 0.5 and numeric_ratio < 0.8
    key_like = (
        "id" in lower_name
        or "key" in lower_name
        or "code" in lower_name
        or lower_name.startswith("k")
        or (
            unique_ratio > 0.8
            and (
                numeric_ratio >= 0.5
                or digit_ratio >= 0.6
                or (avg_length <= 12 and not text_like)
            )
        )
    )
    time_like = date_ratio >= 0.6 or any(token in lower_name for token in ["date", "year", "month", "time"])
    measure_like = numeric_ratio >= 0.7 and unique_ratio < 0.95
    return ColumnProfile(
        source_id=source_id,
        column_name=column_name,
        dtype=str(series.dtype),
        null_rate=float(null_rate),
        unique_ratio=float(unique_ratio),
        numeric_ratio=float(numeric_ratio),
        date_ratio=float(date_ratio),
        alpha_ratio=float(alpha_ratio),
        digit_ratio=float(digit_ratio),
        avg_length=float(avg_length),
        sample_values=_safe_sample_values(series),
        key_like=bool(key_like),
        text_like=bool(text_like),
        time_like=bool(time_like),
        measure_like=bool(measure_like),
    )


def _infer_role_hint(column_profiles: Dict[str, ColumnProfile]) -> str:
    num_key = sum(1 for profile in column_profiles.values() if profile.key_like)
    num_measure = sum(1 for profile in column_profiles.values() if profile.measure_like)
    num_text = sum(1 for profile in column_profiles.values() if profile.text_like)
    if num_measure >= 1 and num_key >= 1:
        return "fact"
    if num_text >= 1 and num_key >= 1 and num_measure == 0:
        return "dimension"
    return "unknown"


def _profile_df(
    df: pd.DataFrame,
    source_id: str,
    file_name: str,
    file_path: Path,
    storage_type: str,
    table_name: str | None,
) -> SourceProfile:
    column_profiles = {
        column_name: _build_column_profile(source_id, column_name, df[column_name])
        for column_name in df.columns
    }
    sample_rows = df.head(8).where(pd.notna(df.head(8)), None).to_dict(orient="records")
    return SourceProfile(
        source_id=source_id,
        file_name=file_name,
        file_path=file_path,
        storage_type=storage_type,
        table_name=table_name,
        raw_view_name=source_view_name(file_name, table_name),
        row_count=int(len(df)),
        role_hint=_infer_role_hint(column_profiles),
        sample_rows=sample_rows,
        column_profiles=column_profiles,
    )


def profile_workspace(workspace: Path) -> Dict[str, SourceProfile]:
    sources: Dict[str, SourceProfile] = {}
    for file_path in sorted(workspace.iterdir()):
        if not file_path.is_file():
            continue
        lower_name = file_path.name.lower()
        if lower_name == "gold.csv" or lower_name.startswith("manifest_") or lower_name.endswith(".json"):
            continue
        ext = file_path.suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(file_path)
            source_id = f"{file_path.name}::{file_path.stem}"
            sources[source_id] = _profile_df(df, source_id, file_path.name, file_path, "csv", file_path.stem)
        elif ext == ".parquet":
            try:
                df = pd.read_parquet(file_path)
            except Exception:
                conn = duckdb.connect(database=":memory:")
                try:
                    uri = str(file_path.resolve()).replace("\\", "/")
                    df = conn.execute(f"SELECT * FROM read_parquet('{uri}')").fetchdf()
                finally:
                    conn.close()
            source_id = f"{file_path.name}::{file_path.stem}"
            sources[source_id] = _profile_df(df, source_id, file_path.name, file_path, "parquet", file_path.stem)
        elif ext == ".sqlite":
            conn = sqlite3.connect(str(file_path))
            try:
                tables = [
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    ).fetchall()
                ]
                for table_name in tables:
                    df = pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
                    source_id = f"{file_path.name}::{table_name}"
                    sources[source_id] = _profile_df(df, source_id, file_path.name, file_path, "sqlite", table_name)
            finally:
                conn.close()
    return sources


def _fk_candidate_columns(source: SourceProfile, all_source_ids: List[str]) -> List[str]:
    """Identify columns that might be FK references based on naming patterns."""
    fk_cols: List[str] = []
    # Extract table-like name segments from all source IDs
    table_names: set[str] = set()
    for sid in all_source_ids:
        # source_id format: "file::table" or just "table"
        parts = sid.split("::")
        tname = parts[-1].lower().replace("_", "")
        table_names.add(tname)
        # Also add subparts (e.g., "debate_people" -> "debate", "people")
        for part in parts[-1].lower().split("_"):
            if len(part) > 2:
                table_names.add(part)

    for col in source.columns:
        lower = col.lower()
        # Already a key column? skip (handled separately)
        if source.column_profiles[col].key_like:
            continue
        # Check if column name references another table
        col_stripped = lower.replace("_", "")
        for tname in table_names:
            # Include columns whose stripped name *contains* a known table name,
            # including the exact-match case (e.g. "Country" column referencing
            # the "country" table — previously excluded by a != guard).
            if tname in col_stripped:
                fk_cols.append(col)
                break
    return fk_cols


def build_join_edges(sources: Dict[str, SourceProfile], min_overlap: float = 0.05) -> List[JoinEdge]:
    edges: List[JoinEdge] = []
    source_items = list(sources.items())
    all_source_ids = [sid for sid, _ in source_items]
    for idx, (left_source_id, left_source) in enumerate(source_items):
        left_key_cols = left_source.key_columns or left_source.columns[:8]
        left_fk_cols = _fk_candidate_columns(left_source, all_source_ids)
        left_candidate_columns = list(dict.fromkeys(left_key_cols + left_fk_cols))  # dedupe preserving order
        for right_source_id, right_source in source_items[idx + 1 :]:
            right_key_cols = right_source.key_columns or right_source.columns[:8]
            right_fk_cols = _fk_candidate_columns(right_source, all_source_ids)
            right_candidate_columns = list(dict.fromkeys(right_key_cols + right_fk_cols))
            best_edges: List[JoinEdge] = []
            for left_col in left_candidate_columns[:8]:
                left_values = pd.Series(left_source.column_profiles[left_col].sample_values)
                for right_col in right_candidate_columns[:8]:
                    right_values = pd.Series(right_source.column_profiles[right_col].sample_values)
                    overlap, left_transform, right_transform = _best_norm_overlap(left_values, right_values)
                    if overlap < min_overlap:
                        continue
                    # Boost overlap when column names match (FK-pattern awareness)
                    left_lower = left_col.lower().replace("_", "").replace("-", "")
                    right_lower = right_col.lower().replace("_", "").replace("-", "")
                    if left_lower == right_lower:
                        overlap = min(overlap * 1.5 + 0.15, 1.0)
                    elif left_lower.endswith("id") and right_lower.endswith("id"):
                        # Both are ID columns but different names - slight penalty
                        overlap *= 0.85
                    best_edges.append(
                        JoinEdge(
                            edge_id=f"{slugify(left_source_id)}__{slugify(right_source_id)}__{slugify(left_col)}__{slugify(right_col)}",
                            left_source_id=left_source_id,
                            right_source_id=right_source_id,
                            left_column=left_col,
                            right_column=right_col,
                            left_transform=left_transform,
                            right_transform=right_transform,
                            overlap=float(overlap),
                        )
                    )
            best_edges.sort(key=lambda edge: edge.overlap, reverse=True)
            edges.extend(best_edges[:4])
    return edges


def build_workspace_catalog(workspace: Path) -> WorkspaceCatalog:
    sources = profile_workspace(workspace)
    join_edges = build_join_edges(sources)
    files_touched = sorted({source.file_name for source in sources.values()})
    return WorkspaceCatalog(workspace=workspace, sources=sources, join_edges=join_edges, files_touched=files_touched)


def transform_sql_expr(transform_name: str, col_ref: str) -> str:
    if transform_name == "digits":
        return (
            "coalesce("
            f"nullif(ltrim(regexp_replace(CAST({col_ref} AS VARCHAR), '[^0-9]', '', 'g'), '0'), ''), "
            "'0'"
            ")"
        )
    if transform_name == "sep":
        return f"regexp_replace(lower(CAST({col_ref} AS VARCHAR)), '[-_]+', ' ', 'g')"
    if transform_name == "date":
        return (
            "coalesce("
            f"strftime(try_strptime(CAST({col_ref} AS VARCHAR), '%Y-%m-%d'), '%Y-%m-%d'), "
            f"strftime(try_strptime(CAST({col_ref} AS VARCHAR), '%m/%d/%Y'), '%Y-%m-%d'), "
            f"strftime(try_strptime(CAST({col_ref} AS VARCHAR), '%d/%m/%Y'), '%Y-%m-%d'), "
            f"strftime(try_strptime(CAST({col_ref} AS VARCHAR), '%m-%d-%Y'), '%Y-%m-%d'), "
            f"strftime(try_strptime(CAST({col_ref} AS VARCHAR), '%d %b %Y'), '%Y-%m-%d'), "
            f"CAST({col_ref} AS VARCHAR)"
            ")"
        )
    return f"CAST({col_ref} AS VARCHAR)"


def month_predicate_sql(col_ref: str, months: Iterable[int]) -> str:
    month_list = ", ".join(str(month) for month in sorted(set(months)))
    return f"CAST(strftime({col_ref}, '%m') AS INTEGER) IN ({month_list})"


def year_predicate_sql(col_ref: str, years: Iterable[int]) -> str:
    year_list = ", ".join(str(year) for year in sorted(set(years)))
    return f"CAST(strftime({col_ref}, '%Y') AS INTEGER) IN ({year_list})"


def register_catalog_views(conn: duckdb.DuckDBPyConnection, catalog: WorkspaceCatalog) -> None:
    conn.execute("INSTALL sqlite;")
    conn.execute("LOAD sqlite;")
    for source in catalog.sources.values():
        uri = str(source.file_path.resolve()).replace("\\", "/")
        if source.storage_type == "csv":
            conn.execute(
                f'CREATE OR REPLACE TEMP VIEW "{source.raw_view_name}" AS SELECT * FROM read_csv_auto(\'{uri}\')'
            )
        elif source.storage_type == "parquet":
            conn.execute(
                f'CREATE OR REPLACE TEMP VIEW "{source.raw_view_name}" AS SELECT * FROM read_parquet(\'{uri}\')'
            )
        elif source.storage_type == "sqlite":
            conn.execute(
                f'CREATE OR REPLACE TEMP VIEW "{source.raw_view_name}" AS SELECT * FROM sqlite_scan(\'{uri}\', \'{source.table_name}\')'
            )


def execute_duckdb_sql(
    catalog: WorkspaceCatalog,
    sql_query: str,
    output_csv: Path | None = None,
) -> Dict[str, Any]:
    conn = duckdb.connect(database=":memory:")
    try:
        register_catalog_views(conn, catalog)
        df = conn.execute(sql_query).fetchdf()
        if output_csv is not None:
            output_csv.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_csv, index=False)
        return {
            "success": True,
            "row_count": int(len(df)),
            "columns": list(df.columns),
            "preview": _safe_preview_df(df),
            "files_touched": catalog.files_touched,
        }
    except Exception as exc:
        return {
            "success": False,
            "row_count": 0,
            "columns": [],
            "preview": [],
            "files_touched": catalog.files_touched,
            "error": str(exc),
        }
    finally:
        conn.close()
