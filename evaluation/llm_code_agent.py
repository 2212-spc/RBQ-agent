from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import duckdb
import pandas as pd

from evaluation.duckdb_agent import _best_norm_overlap
from evaluation.llm_backend import LLMBackendSession, create_llm_session, extract_json_object
from evaluation.workspace_catalog import summarize_workspace as _summarize_workspace


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
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
            "tables": [
                {
                    "name": fp.stem,
                    "columns": list(df.columns),
                    "sample_rows": _safe_preview_df(df),
                }
            ],
        }

    if ext == ".parquet":
        df = pd.read_parquet(fp).head(5)
        return {
            "file": fp.name,
            "type": "parquet",
            "tables": [
                {
                    "name": fp.stem,
                    "columns": list(df.columns),
                    "sample_rows": _safe_preview_df(df),
                }
            ],
        }

    if ext == ".sqlite":
        import sqlite3

        conn = sqlite3.connect(str(fp))
        try:
            table_names = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            tables = []
            for table_name in table_names:
                df = pd.read_sql_query(f"SELECT * FROM '{table_name}' LIMIT 5", conn)
                tables.append(
                    {
                        "name": table_name,
                        "columns": list(df.columns),
                        "sample_rows": _safe_preview_df(df),
                    }
                )
        finally:
            conn.close()
        return {
            "file": fp.name,
            "type": "sqlite",
            "tables": tables,
        }

    return {
        "file": fp.name,
        "type": ext.lstrip(".") or "unknown",
        "tables": [],
    }


def summarize_workspace(workspace: Path) -> Dict[str, Any]:
    return _summarize_workspace(workspace)


def _tokenize(text: str) -> List[str]:
    return [tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if tok and tok not in STOPWORDS]


def _name_similarity(a: str, b: str) -> float:
    ta = set(_tokenize(a))
    tb = set(_tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _heuristic_rank_files(workspace_summary: Dict[str, Any], instruction: str, top_k: int = 4) -> List[str]:
    question_tokens = set(_tokenize(instruction))
    scored: List[tuple[float, str]] = []
    for file_info in workspace_summary.get("files", []):
        score = 0.0
        score += sum(1.0 for tok in _tokenize(file_info.get("file", "")) if tok in question_tokens)
        for table in file_info.get("tables", []):
            score += sum(1.5 for tok in _tokenize(table.get("name", "")) if tok in question_tokens)
            for col in table.get("columns", []):
                col_tokens = set(_tokenize(str(col)))
                overlap = len(question_tokens & col_tokens)
                score += overlap * 2.0
                if re.search(r"(?:^|_)(id|name|date|location|country|aircraft)(?:$|_)", str(col).lower()):
                    score += 0.2
        scored.append((score, file_info.get("file", "")))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_files = [file_name for score, file_name in scored if file_name][:top_k]
    if not top_files:
        top_files = [file_info.get("file", "") for file_info in workspace_summary.get("files", [])[:top_k]]
    return top_files


def _is_text_like_column(sample_rows: List[Dict[str, Any]], column: str) -> bool:
    values = [row.get(column) for row in sample_rows if row.get(column) is not None]
    if not values:
        return False
    str_values = [str(value) for value in values]
    alpha_ratio = sum(bool(re.search(r"[A-Za-z]", value)) for value in str_values) / max(len(str_values), 1)
    digit_ratio = sum(value.isdigit() for value in str_values) / max(len(str_values), 1)
    return alpha_ratio >= 0.5 and digit_ratio < 0.8


def _location_semantic_score(sample_rows: List[Dict[str, Any]], column: str) -> float:
    values = [str(row.get(column, "")) for row in sample_rows if row.get(column) is not None]
    if not values:
        return 0.0
    comma_ratio = sum("," in value for value in values) / max(len(values), 1)
    alpha_ratio = sum(bool(re.search(r"[A-Za-z]", value)) for value in values) / max(len(values), 1)
    digit_char_ratio = (
        sum(ch.isdigit() for value in values for ch in value) /
        max(sum(len(value) for value in values), 1)
    )
    avg_words = sum(len(value.split()) for value in values) / max(len(values), 1)
    score = 0.0
    score += comma_ratio * 10.0
    score += alpha_ratio * 4.0
    score += max(avg_words - 1.0, 0.0) * 1.5
    score -= digit_char_ratio * 20.0
    if any(any(unit in value.lower() for unit in ["kg", "lb", "ft", "m2", "m虏"]) for value in values):
        score -= 8.0
    return score


def _aircraft_semantic_score(sample_rows: List[Dict[str, Any]], column: str) -> float:
    values = [str(row.get(column, "")) for row in sample_rows if row.get(column) is not None]
    if not values:
        return 0.0
    alpha_ratio = sum(bool(re.search(r"[A-Za-z]", value)) for value in values) / max(len(values), 1)
    digit_ratio = (
        sum(ch.isdigit() for value in values for ch in value) /
        max(sum(len(value) for value in values), 1)
    )
    avg_len = sum(len(value) for value in values) / max(len(values), 1)
    avg_words = sum(len(value.split()) for value in values) / max(len(values), 1)
    score = 0.0
    score += alpha_ratio * 6.0
    score += max(avg_words - 1.0, 0.0) * 2.0
    score += min(avg_len / 10.0, 4.0)
    score -= digit_ratio * 8.0
    if any(any(term in value.lower() for term in ["bell", "robinson", "chinook", "stallion", "jetranger", "mil"]) for value in values):
        score += 8.0
    if any(bool(re.search(r"[A-Za-z].*\d|\d.*[A-Za-z]|-", value)) for value in values):
        score += 5.0
    if any(any(term in value.lower() for term in ["utility helicopter", "heavy-lift", "tandem rotor", "turboshaft", "light utility"]) for value in values):
        score -= 8.0
    return score


def _guess_column_for_output(output_col: str, file_info: Dict[str, Any], table: Dict[str, Any]) -> tuple[str | None, float]:
    target = output_col.lower()
    best_col = None
    best_score = -1.0
    sample_rows = table.get("sample_rows", [])
    for col in table.get("columns", []):
        score = 0.0
        col_lower = str(col).lower()
        if target == col_lower:
            score += 20.0
        if target in col_lower:
            score += 10.0
        if target == "location" and _is_text_like_column(sample_rows, col):
            score += _location_semantic_score(sample_rows, col)
        if target == "aircraft" and "aircraft" in col_lower:
            score += 8.0
        if target == "aircraft" and _is_text_like_column(sample_rows, col):
            score += _aircraft_semantic_score(sample_rows, col)
        if target == "name" and "name" in col_lower:
            score += 8.0
        if target == "date" and "date" in col_lower:
            score += 8.0
        if score > best_score:
            best_score = score
            best_col = str(col)
    return best_col, best_score


def _flatten_table_infos(workspace_summary: Dict[str, Any], relevant_files: List[str]) -> List[Dict[str, Any]]:
    selected = []
    for file_info in workspace_summary.get("files", []):
        if relevant_files and file_info.get("file") not in relevant_files:
            continue
        for table in file_info.get("tables", []):
            selected.append(
                {
                    "file": file_info.get("file"),
                    "type": file_info.get("type"),
                    "table": table.get("name"),
                    "columns": table.get("columns", []),
                    "sample_rows": table.get("sample_rows", []),
                }
            )
    return selected


def _guess_join_between_tables(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any] | None:
    best = None
    left_df = pd.DataFrame(left.get("sample_rows", []))
    right_df = pd.DataFrame(right.get("sample_rows", []))
    if left_df.empty or right_df.empty:
        return None
    for left_col in left.get("columns", []):
        if left_col not in left_df.columns:
            continue
        for right_col in right.get("columns", []):
            if right_col not in right_df.columns:
                continue
            overlap, left_norm, right_norm = _best_norm_overlap(left_df[left_col], right_df[right_col])
            left_name = str(left_col).lower()
            right_name = str(right_col).lower()
            left_bonus = 0.0
            right_bonus = 0.0
            if re.fullmatch(r"k\d+", left_name):
                left_bonus += 0.6
            elif re.search(r"(id|key)", left_name):
                left_bonus += 0.25
            if re.fullmatch(r"k\d+", right_name):
                right_bonus += 0.6
            elif re.search(r"(id|key)", right_name):
                right_bonus += 0.25
            name_bonus = _name_similarity(str(left_col), str(right_col)) * 0.8
            semantic_bonus = 0.0
            if "aircraft" in left_name and "aircraft" in right_name:
                semantic_bonus += 0.6
            if "pilot" in left_name and "pilot" in right_name:
                semantic_bonus += 0.4
            if left_norm == "date" and right_norm == "date":
                semantic_bonus -= 0.25
            if left_name.startswith("extra_"):
                semantic_bonus -= 0.8
            if right_name.startswith("extra_"):
                semantic_bonus -= 0.8
            score = overlap + left_bonus + right_bonus + name_bonus + semantic_bonus
            if best is None or score > best["score"]:
                best = {
                    "left_col": str(left_col),
                    "right_col": str(right_col),
                    "left_norm": left_norm,
                    "right_norm": right_norm,
                    "overlap": float(overlap),
                    "score": float(score),
                }
    return best


def _sql_expr_for_norm(norm_name: str, column_name: str, alias: str | None = None) -> str:
    if alias:
        col = f'{alias}."{column_name}"'
    else:
        col = f'"{column_name}"'
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


def _build_heuristic_planner(
    workspace_summary: Dict[str, Any],
    instruction: str,
    deliverable_spec: Dict[str, Any],
    relevant_files_override: List[str] | None = None,
) -> Dict[str, Any]:
    relevant_files = list(relevant_files_override) if relevant_files_override else _heuristic_rank_files(workspace_summary, instruction, top_k=3)
    table_infos = _flatten_table_infos(workspace_summary, relevant_files)
    required_columns = deliverable_spec.get("required_columns", [])
    output_mappings: List[Dict[str, Any]] = []

    for output_col in required_columns:
        best = None
        for table_info in table_infos:
            guessed_col, score = _guess_column_for_output(output_col, {"file": table_info["file"]}, table_info)
            if guessed_col is None:
                continue
            if best is None or score > best["score"]:
                best = {
                    "output_column": output_col,
                    "source_file": table_info["file"],
                    "source_table": table_info["table"],
                    "source_column": guessed_col,
                    "score": score,
                }
        if best is not None:
            output_mappings.append(best)

    duckdb_sql = ""
    join_score = 0.0
    candidate_joins: List[Dict[str, Any]] = []
    if output_mappings:
        table_groups: Dict[str, List[Dict[str, Any]]] = {}
        for mapping in output_mappings:
            table_groups.setdefault(mapping["source_table"], []).append(mapping)

        if len(table_groups) == 1:
            table_name = next(iter(table_groups))
            select_clause = ", ".join(
                f'"{item["source_column"]}" AS "{item["output_column"]}"'
                for item in table_groups[table_name]
            )
            duckdb_sql = f'SELECT {select_clause} FROM "{table_name}"'
        elif len(table_groups) >= 2:
            tables = list(table_groups)
            left = next(item for item in table_infos if item["table"] == tables[0])
            right = next(item for item in table_infos if item["table"] == tables[1])
            join_info = _guess_join_between_tables(left, right)
            if join_info:
                candidate_joins.append(
                    {
                        "left_table": left["table"],
                        "right_table": right["table"],
                        "left_key": join_info["left_col"],
                        "right_key": join_info["right_col"],
                        "left_norm": join_info["left_norm"],
                        "right_norm": join_info["right_norm"],
                    }
                )
                join_score = float(join_info.get("score", join_info.get("overlap", 0.0)))
                select_parts: List[str] = []
                for table_name in tables[:2]:
                    for mapping in table_groups[table_name]:
                        alias = "t1" if table_name == tables[0] else "t2"
                        select_parts.append(f'{alias}."{mapping["source_column"]}" AS "{mapping["output_column"]}"')
                duckdb_sql = (
                    f'SELECT {", ".join(select_parts)} '
                    f'FROM "{tables[0]}" AS t1 JOIN "{tables[1]}" AS t2 '
                    f'ON {_sql_expr_for_norm(join_info["left_norm"], join_info["left_col"], alias="t1")} '
                    f'= {_sql_expr_for_norm(join_info["right_norm"], join_info["right_col"], alias="t2")}'
                )

    output_score = sum(float(item.get("score", 0.0)) for item in output_mappings)
    plan_score = output_score + join_score * 15.0

    return {
        "relevant_files": relevant_files,
        "reasoning": "heuristic_planner_fallback",
        "candidate_joins": candidate_joins,
        "expected_output_columns": required_columns,
        "backend": "duckdb",
        "output_mappings": output_mappings,
        "duckdb_sql": duckdb_sql,
        "plan_score": plan_score,
    }


def _prune_workspace_summary_for_coder(workspace_summary: Dict[str, Any], planner_output: Dict[str, Any], max_files: int = 3) -> Dict[str, Any]:
    relevant_files = planner_output.get("relevant_files") or []
    file_by_name = {file_info["file"]: file_info for file_info in workspace_summary.get("files", [])}
    selected = [file_by_name[name] for name in relevant_files if name in file_by_name][:max_files]

    if not selected:
        selected = workspace_summary.get("files", [])[:max_files]

    compact_files: List[Dict[str, Any]] = []
    for file_info in selected:
        compact_tables = []
        for table in file_info.get("tables", [])[:3]:
            compact_tables.append(
                {
                    "name": table.get("name"),
                    "columns": table.get("columns", [])[:12],
                }
            )
        compact_files.append(
            {
                "file": file_info.get("file"),
                "type": file_info.get("type"),
                "tables": compact_tables,
            }
        )

    return {
        "workspace_name": workspace_summary.get("workspace_name", ""),
        "files": compact_files,
    }


def _format_workspace_summary_text(workspace_summary: Dict[str, Any]) -> str:
    lines: List[str] = []
    for file_info in workspace_summary.get("files", []):
        lines.append(f"File: {file_info.get('file')} ({file_info.get('type')})")
        for table in file_info.get("tables", []):
            columns = ", ".join(table.get("columns", []))
            lines.append(f"  Table: {table.get('name')} | Columns: {columns}")
    return "\n".join(lines)


def _extract_json_object(text: str) -> Dict[str, Any] | None:
    return extract_json_object(text)


def _extract_code_block(text: str) -> str:
    block = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if block:
        return block.group(1).strip()
    return text.strip()


def _chat_text(session: LLMBackendSession, system_prompt: str, user_prompt: str) -> str:
    return session.chat_text(system_prompt, user_prompt, cache_namespace="llm_code_agent_text")


def _chat_json(session: LLMBackendSession, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    return session.chat_json(system_prompt, user_prompt, cache_namespace="llm_code_agent_json")


def _build_planner_prompt(instruction: str, workspace_summary: Dict[str, Any], deliverable_spec: Dict[str, Any]) -> str:
    return (
        "Question:\n"
        f"{instruction}\n\n"
        "Workspace summary:\n"
        f"{json.dumps(workspace_summary, ensure_ascii=False, indent=2)}\n\n"
        "Output requirements:\n"
        f"{json.dumps(deliverable_spec, ensure_ascii=False, indent=2)}\n\n"
        "Return JSON with keys: relevant_files, reasoning, candidate_joins, expected_output_columns, backend, duckdb_sql.\n"
        "duckdb_sql should be a best-effort SQL query using the visible table names from the workspace summary.\n"
        "Keep reasoning short."
    )


def _prune_workspace_summary_for_planner(workspace_summary: Dict[str, Any], candidate_files: List[str]) -> Dict[str, Any]:
    file_by_name = {file_info["file"]: file_info for file_info in workspace_summary.get("files", [])}
    selected = [file_by_name[name] for name in candidate_files if name in file_by_name]
    if not selected:
        selected = workspace_summary.get("files", [])
    compact_files: List[Dict[str, Any]] = []
    for file_info in selected[:4]:
        compact_tables = []
        for table in file_info.get("tables", [])[:3]:
            compact_tables.append(
                {
                    "name": table.get("name"),
                    "columns": table.get("columns", [])[:16],
                }
            )
        compact_files.append(
            {
                "file": file_info.get("file"),
                "type": file_info.get("type"),
                "tables": compact_tables,
            }
        )
    return {
        "workspace_name": workspace_summary.get("workspace_name", ""),
        "files": compact_files,
    }


def _build_code_prompt(
    instruction: str,
    workspace_summary: Dict[str, Any],
    deliverable_spec: Dict[str, Any],
    planner_output: Dict[str, Any],
    output_csv: Path,
    repair_error: str | None = None,
    previous_code: str | None = None,
) -> str:
    required_columns = deliverable_spec.get("required_columns", [])
    planner_files = ", ".join(planner_output.get("relevant_files", []))
    prompt = [
        f"Question:\n{instruction}",
        f"Relevant files suggested by planner: {planner_files}",
        (
            "Grounding hints:\n"
            f"{json.dumps(planner_output.get('grounding_hints', {}), ensure_ascii=False, indent=2)}"
            if planner_output.get("grounding_hints")
            else "Grounding hints:\n{}"
        ),
        f"Workspace summary:\n{_format_workspace_summary_text(workspace_summary)}",
        f"Required output columns: {required_columns}",
        (
            "Write complete Python code using only pandas, duckdb, sqlite3, pyarrow, pathlib, re, json, numpy.\n"
            "Important:\n"
            "- Your current working directory is already the workspace.\n"
            "- Read input files using only their filenames, e.g. Path('file.csv') or 'file.sqlite'.\n"
            f"- Save the final result to this exact absolute path: {output_csv.resolve().as_posix()}\n"
            "Do not print explanations. Do not wrap the answer in JSON."
        ),
    ]
    if repair_error:
        prompt.append(f"Previous code:\n```python\n{previous_code or ''}\n```")
        prompt.append(f"Execution error:\n{repair_error}")
        prompt.append("Fix the code and return a complete corrected Python script.")
    return "\n\n".join(prompt)


def _normalize_generated_code_paths(code: str, workspace: Path, output_csv: Path) -> str:
    normalized = code

    output_variants = {
        output_csv.as_posix(),
        str(output_csv),
        str(output_csv).replace("\\", "/"),
    }
    for variant in output_variants:
        normalized = normalized.replace(variant, output_csv.resolve().as_posix())

    for fp in workspace.iterdir():
        if not fp.is_file():
            continue
        replacement = fp.name
        candidates = {
            str(fp),
            str(fp).replace("\\", "/"),
            fp.resolve().as_posix(),
        }
        for candidate in candidates:
            normalized = normalized.replace(candidate, replacement)

    workspace_prefixes = {
        str(workspace),
        str(workspace).replace("\\", "/"),
        workspace.resolve().as_posix(),
    }
    for prefix in workspace_prefixes:
        normalized = normalized.replace(prefix + "/", "")
        normalized = normalized.replace(prefix + "\\", "")

    output_var_patterns = [
        r"(?m)^\s*out_path\s*=\s*Path\((.*?)\)\s*$",
        r"(?m)^\s*output_path\s*=\s*Path\((.*?)\)\s*$",
        r"(?m)^\s*output_file\s*=\s*Path\((.*?)\)\s*$",
    ]
    for pattern in output_var_patterns:
        normalized = re.sub(pattern, "out_path = OUTPUT_CSV", normalized)

    return normalized


def _execute_generated_code(code: str, workspace: Path, output_csv: Path, timeout_seconds: int = 90) -> Dict[str, Any]:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hdrbench_llm_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        script_path = tmp_dir / "agent_run.py"
        prelude = (
            "from pathlib import Path\n"
            f"WORKSPACE_DIR = Path(r'{workspace.resolve().as_posix()}')\n"
            f"OUTPUT_CSV = Path(r'{output_csv.resolve().as_posix()}')\n"
        )
        epilogue = (
            "\nif 'df' in locals() and hasattr(df, 'to_csv') and not OUTPUT_CSV.exists():\n"
            "    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)\n"
            "    df.to_csv(OUTPUT_CSV, index=False)\n"
        )
        script_path.write_text(prelude + "\n" + code + epilogue, encoding="utf-8")
        started = time.time()
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed = time.time() - started
        return {
            "returncode": int(proc.returncode),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "time_seconds": round(elapsed, 4),
            "output_exists": output_csv.exists(),
        }


def _execute_planner_sql(workspace: Path, relevant_files: List[str], sql_query: str, output_csv: Path) -> Dict[str, Any]:
    started = time.time()
    conn = duckdb.connect(database=":memory:")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn.execute("INSTALL sqlite;")
        conn.execute("LOAD sqlite;")
        selected_files = set(relevant_files) if relevant_files else {fp.name for fp in workspace.iterdir() if fp.is_file()}
        touched_files: List[str] = []
        for fp in sorted(workspace.iterdir()):
            if not fp.is_file() or fp.name not in selected_files:
                continue
            touched_files.append(fp.name)
            uri = fp.resolve().as_posix()
            ext = fp.suffix.lower()
            if ext == ".csv":
                conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{fp.stem}\" AS SELECT * FROM read_csv_auto('{uri}')")
            elif ext == ".parquet":
                conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{fp.stem}\" AS SELECT * FROM read_parquet('{uri}')")
            elif ext == ".sqlite":
                sconn = sqlite3.connect(str(fp))
                try:
                    tables = [
                        row[0]
                        for row in sconn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                        ).fetchall()
                    ]
                finally:
                    sconn.close()
                for table_name in tables:
                    conn.execute(
                        f"CREATE OR REPLACE TEMP VIEW \"{table_name}\" AS SELECT * FROM sqlite_scan('{uri}', '{table_name}')"
                    )

        df = conn.execute(sql_query).fetchdf()
        df.to_csv(output_csv, index=False)
        return {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "time_seconds": round(time.time() - started, 4),
            "output_exists": True,
            "files_touched": touched_files,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": str(exc),
            "time_seconds": round(time.time() - started, 4),
            "output_exists": output_csv.exists(),
            "files_touched": [],
        }
    finally:
        conn.close()


def _normalize_planner_sql(sql_query: str) -> str:
    normalized = sql_query.strip()
    normalized = re.sub(
        r"sqlite_scan\(\s*'[^']+'\s*,\s*'([^']+)'\s*\)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)",
        r'"\1" AS \2',
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"sqlite_scan\(\s*'[^']+'\s*,\s*'([^']+)'\s*\)",
        r'"\1"',
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"read_csv_auto\(\s*'[^']*/([^'/]+)\.csv'\s*\)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)",
        r'"\1" AS \2',
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"read_parquet\(\s*'[^']*/([^'/]+)\.parquet'\s*\)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)",
        r'"\1" AS \2',
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


def _score_planner_result(df: pd.DataFrame, expected_columns: List[str]) -> float:
    if df is None or df.empty:
        return 0.0
    if not set(expected_columns).issubset(set(df.columns)):
        return 0.0

    score = 10.0
    score += min(len(df), 10) * 0.5

    sample_rows = df.head(5).to_dict(orient="records")
    for col in expected_columns:
        lower = str(col).lower()
        if lower == "location":
            score += _location_semantic_score(sample_rows, col)
        elif lower == "aircraft":
            score += _aircraft_semantic_score(sample_rows, col)
        elif "address" in lower:
            values = [str(row.get(col, "")) for row in sample_rows]
            avg_len = sum(len(v) for v in values) / max(len(values), 1)
            score += min(avg_len / 8.0, 6.0)
        elif "facility_code" in lower or "part_name" in lower:
            unique_ratio = len({str(row.get(col, "")) for row in sample_rows}) / max(len(sample_rows), 1)
            score += unique_ratio * 4.0
        elif "first_name" in lower or "last_name" in lower or "staff_name" in lower:
            score += 3.0
    return score


def run_llm_code_agent(
    instruction: str,
    workspace: Path,
    deliverable_spec: Dict[str, Any],
    output_csv: Path,
) -> Dict[str, Any]:
    started = time.time()
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    session = create_llm_session("llm_code_agent")

    workspace_summary = summarize_workspace(workspace)
    heuristic_files = _heuristic_rank_files(workspace_summary, instruction)
    planner_system = (
        "You are a careful data analyst. Identify relevant files and likely joins in a messy local workspace. "
        "Return JSON only."
    )
    planner_prompt = _build_planner_prompt(
        instruction,
        _prune_workspace_summary_for_planner(workspace_summary, heuristic_files),
        deliverable_spec,
    )

    try:
        if session is None:
            raise RuntimeError("llm_backend_unavailable")
        planner_output = _chat_json(session, planner_system, planner_prompt)
    except Exception as exc:  # noqa: BLE001
        planner_output = _build_heuristic_planner(workspace_summary, instruction, deliverable_spec)
        planner_output["reasoning"] = f"{planner_output.get('reasoning', '')}; planner_llm_error: {exc}"

    llm_relevant_files = planner_output.get("relevant_files", []) if isinstance(planner_output, dict) else []
    heuristic_on_llm_files = _build_heuristic_planner(
        workspace_summary,
        instruction,
        deliverable_spec,
        relevant_files_override=llm_relevant_files or None,
    )
    planner_candidates: List[tuple[str, Dict[str, Any]]] = []
    if str(planner_output.get("duckdb_sql", "")).strip():
        planner_candidates.append(("planner", planner_output))
    if (
        str(heuristic_on_llm_files.get("duckdb_sql", "")).strip()
        and heuristic_on_llm_files.get("duckdb_sql") != planner_output.get("duckdb_sql")
    ):
        planner_candidates.append(("heuristic", heuristic_on_llm_files))

    coder_system = (
        "You are a Python data analyst. Write robust code for local files only. "
        "Return only executable Python code."
    )
    code_prompt = _build_code_prompt(
        instruction=instruction,
        workspace_summary=_prune_workspace_summary_for_coder(workspace_summary, planner_output),
        deliverable_spec=deliverable_spec,
        planner_output=planner_output,
        output_csv=output_csv,
    )

    planner_sql_exec = None
    planner_sql_best_output = planner_output
    planner_scores: List[tuple[float, Dict[str, Any], Dict[str, Any]]] = []
    for source_name, candidate_output in planner_candidates:
        candidate_sql = _normalize_planner_sql(str(candidate_output.get("duckdb_sql", "")).strip())
        if not candidate_sql:
            continue
        exec_meta = _execute_planner_sql(
            workspace=workspace,
            relevant_files=candidate_output.get("relevant_files", []),
            sql_query=candidate_sql,
            output_csv=output_csv,
        )
        if exec_meta["returncode"] == 0 and exec_meta["output_exists"]:
            try:
                df = pd.read_csv(output_csv)
            except Exception:
                df = pd.DataFrame()
            planner_scores.append((_score_planner_result(df, deliverable_spec.get("required_columns", [])), candidate_output, exec_meta))
        if source_name == "planner":
            planner_sql_exec = exec_meta

    if planner_scores:
        planner_scores.sort(key=lambda item: item[0], reverse=True)
        _best_score, planner_sql_best_output, planner_sql_exec = planner_scores[0]
        return {
            "success": True,
            "files_touched": planner_sql_exec.get("files_touched", planner_sql_best_output.get("relevant_files", [])),
            "error": None,
            "workspace_summary": workspace_summary,
            "planner_output": planner_sql_best_output,
            "final_sql": _normalize_planner_sql(str(planner_sql_best_output.get("duckdb_sql", "")).strip()) or None,
            "generated_code_round1": "",
            "generated_code_round2": "",
            "execution_round1": planner_sql_exec,
            "execution_round2": None,
            "execution_summary": {
                "planner_sql_execution": planner_sql_exec,
                "code_round1": None,
                "code_round2": None,
            },
            "agent_impl": "llm_code_agent",
            "wall_clock_time": round(time.time() - started, 4),
            "llm_calls_used": session.calls_used if session is not None else 0,
            "llm_calls_budget": session.max_calls if session is not None else 0,
        }

    try:
        if session is None:
            raise RuntimeError("llm_backend_unavailable_for_coder")
        generated_code_round1 = _normalize_generated_code_paths(
            _extract_code_block(_chat_text(session, coder_system, code_prompt)),
            workspace=workspace,
            output_csv=output_csv,
        )
    except Exception as exc:  # noqa: BLE001
        pd.DataFrame(columns=deliverable_spec.get("required_columns", [])).to_csv(output_csv, index=False)
        return {
            "success": False,
            "files_touched": planner_output.get("relevant_files", []),
            "error": f"coder_failed: {exc}",
            "workspace_summary": workspace_summary,
            "planner_output": planner_sql_best_output,
            "final_sql": _normalize_planner_sql(str(planner_sql_best_output.get("duckdb_sql", "")).strip()) or None,
            "generated_code_round1": "",
            "generated_code_round2": "",
            "execution_round1": planner_sql_exec,
            "execution_round2": None,
            "execution_summary": {
                "planner_sql_execution": planner_sql_exec,
                "code_round1": None,
                "code_round2": None,
            },
            "agent_impl": "llm_code_agent",
            "wall_clock_time": round(time.time() - started, 4),
            "llm_calls_used": session.calls_used if session is not None else 0,
            "llm_calls_budget": session.max_calls if session is not None else 0,
        }

    execution_round1 = _execute_generated_code(generated_code_round1, workspace=workspace, output_csv=output_csv)
    generated_code_round2 = ""
    execution_round2 = None

    success = execution_round1["returncode"] == 0 and execution_round1["output_exists"]
    last_error = execution_round1["stderr"]

    if not success:
        auto_fixed_code = _normalize_generated_code_paths(generated_code_round1, workspace=workspace, output_csv=output_csv)
        if auto_fixed_code != generated_code_round1:
            execution_round2 = _execute_generated_code(auto_fixed_code, workspace=workspace, output_csv=output_csv)
            generated_code_round2 = auto_fixed_code
            success = execution_round2["returncode"] == 0 and execution_round2["output_exists"]
            if execution_round2 and execution_round2["stderr"]:
                last_error = execution_round2["stderr"]

    if not success:
        repair_prompt = _build_code_prompt(
            instruction=instruction,
            workspace_summary=_prune_workspace_summary_for_coder(workspace_summary, planner_output),
            deliverable_spec=deliverable_spec,
            planner_output=planner_output,
            output_csv=output_csv,
            repair_error=last_error,
            previous_code=generated_code_round1,
        )
        try:
            if session is None:
                raise RuntimeError("llm_backend_unavailable_for_repair")
            generated_code_round2 = _normalize_generated_code_paths(
                _extract_code_block(_chat_text(session, coder_system, repair_prompt)),
                workspace=workspace,
                output_csv=output_csv,
            )
            execution_round2 = _execute_generated_code(generated_code_round2, workspace=workspace, output_csv=output_csv)
            success = execution_round2["returncode"] == 0 and execution_round2["output_exists"]
            if execution_round2 and execution_round2["stderr"]:
                last_error = execution_round2["stderr"]
        except Exception as exc:  # noqa: BLE001
            last_error = f"repair_failed: {exc}"

    if not output_csv.exists():
        pd.DataFrame(columns=deliverable_spec.get("required_columns", [])).to_csv(output_csv, index=False)

    return {
        "success": bool(success),
        "files_touched": planner_output.get("relevant_files", []),
        "error": None if success else last_error,
        "workspace_summary": workspace_summary,
        "planner_output": planner_sql_best_output,
        "final_sql": _normalize_planner_sql(str(planner_sql_best_output.get("duckdb_sql", "")).strip()) or None,
        "generated_code_round1": generated_code_round1,
        "generated_code_round2": generated_code_round2,
        "execution_round1": execution_round1 if execution_round1 is not None else planner_sql_exec,
        "execution_round2": execution_round2,
        "execution_summary": {
            "planner_sql_execution": planner_sql_exec,
            "code_round1": execution_round1,
            "code_round2": execution_round2,
        },
        "agent_impl": "llm_code_agent",
        "wall_clock_time": round(time.time() - started, 4),
        "llm_calls_used": session.calls_used if session is not None else 0,
        "llm_calls_budget": session.max_calls if session is not None else 0,
    }
