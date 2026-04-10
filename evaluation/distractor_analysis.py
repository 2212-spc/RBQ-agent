from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


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
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def _tokenize(text: str) -> List[str]:
    return [tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if tok and tok not in STOPWORDS]


def _is_key_like(name: str) -> bool:
    lower = name.lower()
    return bool(re.fullmatch(r"k\d+", lower) or "id" in lower or lower.endswith("_key") or lower.endswith("key"))


def _is_date_like(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(50)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", utc=False, format="mixed")
    return float(parsed.notna().mean()) >= 0.8


def _is_numeric_like(series: pd.Series) -> bool:
    sample = series.dropna().head(50)
    if sample.empty:
        return False
    parsed = pd.to_numeric(sample, errors="coerce")
    return float(parsed.notna().mean()) >= 0.8


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _load_file_tables(file_path: Path) -> List[Tuple[str, pd.DataFrame]]:
    ext = file_path.suffix.lower()
    if ext == ".csv":
        return [(file_path.stem, pd.read_csv(file_path).head(50))]
    if ext == ".parquet":
        return [(file_path.stem, pd.read_parquet(file_path).head(50))]
    if ext == ".sqlite":
        conn = sqlite3.connect(str(file_path))
        try:
            table_names = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            return [
                (table_name, pd.read_sql_query(f"SELECT * FROM '{table_name}' LIMIT 50", conn))
                for table_name in table_names
            ]
        finally:
            conn.close()
    return []


def _summarize_file(file_path: Path) -> Dict[str, Any]:
    tables = _load_file_tables(file_path)
    column_tokens: set[str] = set()
    sample_tokens: set[str] = set()
    key_like_columns: set[str] = set()
    total_columns = 0
    numeric_cols = 0
    date_cols = 0
    text_cols = 0
    table_names: List[str] = []
    columns_by_table: Dict[str, List[str]] = {}

    for table_name, df in tables:
        table_names.append(table_name)
        columns = [str(col) for col in df.columns]
        columns_by_table[table_name] = columns
        total_columns += len(columns)
        for col in columns:
            column_tokens.update(_tokenize(col))
            if _is_key_like(col):
                key_like_columns.add(col)

        for col in columns:
            series = df[col]
            if _is_date_like(series):
                date_cols += 1
            elif _is_numeric_like(series):
                numeric_cols += 1
            else:
                text_cols += 1

        for row in df.head(10).to_dict(orient="records"):
            for value in row.values():
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    continue
                sample_tokens.update(_tokenize(str(value))[:8])

    total_columns = max(total_columns, 1)
    profile = {
        "numeric_ratio": numeric_cols / total_columns,
        "date_ratio": date_cols / total_columns,
        "text_ratio": text_cols / total_columns,
        "key_like_ratio": len(key_like_columns) / total_columns,
    }

    return {
        "file": file_path.name,
        "table_names": table_names,
        "columns_by_table": columns_by_table,
        "column_tokens": sorted(column_tokens),
        "sample_tokens": sorted(sample_tokens),
        "key_like_columns": sorted(key_like_columns),
        "profile": profile,
    }


def _profile_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = sorted(set(a) | set(b))
    distance = sum(abs(float(a.get(key, 0.0)) - float(b.get(key, 0.0))) for key in keys)
    return max(0.0, 1.0 - distance / max(len(keys), 1))


def _max_exact_column_overlap(columns_a: Dict[str, List[str]], columns_b: Dict[str, List[str]]) -> float:
    cols_a = {col for cols in columns_a.values() for col in cols}
    cols_b = {col for cols in columns_b.values() for col in cols}
    if not cols_a and not cols_b:
        return 1.0
    if not cols_a or not cols_b:
        return 0.0
    return len(cols_a & cols_b) / max(min(len(cols_a), len(cols_b)), 1)


def _similarity(gold: Dict[str, Any], distractor: Dict[str, Any]) -> Dict[str, float]:
    gold_col_tokens = set(gold["column_tokens"])
    distractor_col_tokens = set(distractor["column_tokens"])
    gold_sample_tokens = set(gold["sample_tokens"])
    distractor_sample_tokens = set(distractor["sample_tokens"])
    gold_key_tokens = {tok for col in gold["key_like_columns"] for tok in _tokenize(col)}
    distractor_key_tokens = {tok for col in distractor["key_like_columns"] for tok in _tokenize(col)}

    column_token_jaccard = _jaccard(gold_col_tokens, distractor_col_tokens)
    sample_token_jaccard = _jaccard(gold_sample_tokens, distractor_sample_tokens)
    key_token_jaccard = _jaccard(gold_key_tokens, distractor_key_tokens)
    exact_column_overlap = _max_exact_column_overlap(gold["columns_by_table"], distractor["columns_by_table"])
    profile_similarity = _profile_similarity(gold["profile"], distractor["profile"])
    hardness = (
        0.35 * column_token_jaccard
        + 0.25 * exact_column_overlap
        + 0.25 * profile_similarity
        + 0.15 * sample_token_jaccard
    )
    return {
        "column_token_jaccard": column_token_jaccard,
        "sample_token_jaccard": sample_token_jaccard,
        "key_token_jaccard": key_token_jaccard,
        "exact_column_overlap": exact_column_overlap,
        "profile_similarity": profile_similarity,
        "hardness_score": hardness,
    }


def analyze_benchmark(bench_root: Path, variants: List[str]) -> Dict[str, Any]:
    seed_dirs = sorted([p for p in bench_root.iterdir() if p.is_dir() and (p / "seed_report.json").exists()])
    case_records: List[Dict[str, Any]] = []

    for seed_dir in seed_dirs:
        seed_id = seed_dir.name
        for variant in variants:
            manifest_path = seed_dir / "variants" / variant / "manifest_private.json"
            if not manifest_path.exists():
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            workspace = Path(manifest["splits"]["l3"]["full"])
            gold_files = manifest.get("gold_files_dirty", [])
            distractors = manifest.get("distractors", [])

            gold_summaries = {
                gold_file: _summarize_file(workspace / gold_file)
                for gold_file in gold_files
                if (workspace / gold_file).exists()
            }

            for distractor in distractors:
                distractor_file = distractor["file"]
                distractor_path = workspace / distractor_file
                if not distractor_path.exists():
                    continue
                distractor_summary = _summarize_file(distractor_path)
                per_gold: Dict[str, Dict[str, float]] = {}
                best_gold = None
                best_score = -1.0
                best_metrics: Dict[str, float] | None = None
                for gold_file, gold_summary in gold_summaries.items():
                    metrics = _similarity(gold_summary, distractor_summary)
                    per_gold[gold_file] = metrics
                    if metrics["hardness_score"] > best_score:
                        best_gold = gold_file
                        best_score = metrics["hardness_score"]
                        best_metrics = metrics

                case_records.append(
                    {
                        "seed_id": seed_id,
                        "variant": variant,
                        "distractor_file": distractor_file,
                        "distractor_type": distractor.get("type", "unknown"),
                        "rows": distractor.get("rows", 0),
                        "best_gold_file": best_gold,
                        "best_metrics": best_metrics or {},
                        "all_gold_metrics": per_gold,
                    }
                )

    by_type: Dict[str, Dict[str, float]] = {}
    for distractor_type in sorted({record["distractor_type"] for record in case_records}):
        subset = [record for record in case_records if record["distractor_type"] == distractor_type]
        if not subset:
            continue
        hardness_values = [float(record["best_metrics"].get("hardness_score", 0.0)) for record in subset]
        by_type[distractor_type] = {
            "count": len(subset),
            "avg_hardness": sum(hardness_values) / len(hardness_values),
            "min_hardness": min(hardness_values),
            "max_hardness": max(hardness_values),
        }

    overall_hardness = [float(record["best_metrics"].get("hardness_score", 0.0)) for record in case_records]
    summary = {
        "bench_root": str(bench_root),
        "variants": variants,
        "num_distractors": len(case_records),
        "overall": {
            "avg_hardness": (sum(overall_hardness) / len(overall_hardness)) if overall_hardness else 0.0,
            "min_hardness": min(overall_hardness) if overall_hardness else 0.0,
            "max_hardness": max(overall_hardness) if overall_hardness else 0.0,
        },
        "by_type": by_type,
        "records": case_records,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze distractor hardness against gold files")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--variants", default="A", help="Comma-separated variants to analyze")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    variants = [item.strip() for item in args.variants.split(",") if item.strip()]
    summary = analyze_benchmark(Path(args.bench_root), variants=variants)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
