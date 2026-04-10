from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

import duckdb
import pandas as pd

from construction.seed_tools import parse_sql_metadata
from evaluation.duckdb_agent import (
    SourceInfo,
    _best_norm_overlap,
    _build_agent_sql,
    _candidate_key_columns,
    _discover_sources,
    _extract_filter_hints,
    _is_key_like,
    _literal_match_score,
    _name_similarity,
    _table_score,
    _tokenize,
)

ROOT = Path(__file__).resolve().parents[1]


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
    "list",
    "of",
    "on",
    "or",
    "show",
    "that",
    "the",
    "to",
    "what",
    "which",
    "who",
    "whose",
    "with",
}


@dataclass
class SourceProfile:
    source_id: str
    question_score: float
    semantic_types: Dict[str, str]
    key_columns: List[str]
    row_count: int
    col_count: int


@dataclass
class TableCandidate:
    canonical_table: str
    source: SourceInfo
    score: float
    base_score: float
    question_score: float
    semantic_bonus: float


@dataclass
class ColumnOption:
    source_col: str
    confidence: float
    semantic_type: str
    literal_score: float
    name_score: float


@dataclass
class JoinOption:
    left_col: str
    right_col: str
    left_norm: str
    right_norm: str
    overlap: float
    confidence: float
    strategy: str


@dataclass
class SearchState:
    nonjoin_choice: Dict[str, int]
    join_choice: Dict[str, int]
    depth: int = 0


@dataclass
class LLMConfig:
    api_key: str
    api_base: str
    model: str
    timeout_seconds: int = 60
    cache_dir: Path = ROOT / "outputs" / "llm_cache"


def _source_id(source: SourceInfo) -> str:
    return f"{source.file_name}::{source.view_name}"


def _load_llm_config_from_file(path: Path) -> LLMConfig | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    api_key = str(payload.get("api_key", "")).strip()
    api_base = str(payload.get("api_base", "")).strip()
    model = str(payload.get("model", "")).strip()
    if not api_key or not api_base:
        return None
    return LLMConfig(
        api_key=api_key,
        api_base=api_base.rstrip("/"),
        model=model,
    )


def _load_llm_config_from_env() -> LLMConfig | None:
    api_key = os.environ.get("HDRBENCH_API_KEY", "").strip()
    api_base = os.environ.get("HDRBENCH_API_BASE", "").strip()
    model = os.environ.get("HDRBENCH_MODEL", "").strip()
    if not api_key or not api_base:
        explicit_path = os.environ.get("HDRBENCH_LLM_CONFIG", "").strip()
        candidate_paths = []
        if explicit_path:
            candidate_paths.append(Path(explicit_path))
        candidate_paths.append(ROOT / "outputs" / "local_llm_config.json")
        candidate_paths.append(ROOT / ".hdrbench_llm_config.json")
        for candidate in candidate_paths:
            config = _load_llm_config_from_file(candidate)
            if config is not None:
                return config
        return None
    return LLMConfig(
        api_key=api_key,
        api_base=api_base.rstrip("/"),
        model=model,
    )


def _http_json(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any] | None = None,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_llm_model(config: LLMConfig) -> str:
    if config.model:
        return config.model

    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        payload = _http_json(f"{config.api_base}/v1/models", headers=headers, payload=None, timeout_seconds=config.timeout_seconds)
        models = payload.get("data", [])
        if models:
            return str(models[0]["id"])
    except Exception:
        pass
    return "gpt-4.1-mini"


def _extract_json_object(text: str) -> Dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _chat_json(
    config: LLMConfig,
    system_prompt: str,
    user_prompt: str,
    cache_namespace: str,
) -> Dict[str, Any] | None:
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    model = _resolve_llm_model(config)
    cache_key = hashlib.sha256(
        json.dumps(
            {
                "model": model,
                "system": system_prompt,
                "user": user_prompt,
                "ns": cache_namespace,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    cache_path = config.cache_dir / f"{cache_key}.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = _http_json(
            f"{config.api_base}/v1/chat/completions",
            headers=headers,
            payload=payload,
            timeout_seconds=config.timeout_seconds,
        )
    except Exception:
        try:
            payload.pop("response_format", None)
            response = _http_json(
                f"{config.api_base}/v1/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=config.timeout_seconds,
            )
        except urllib_error.URLError:
            return None
        except Exception:
            return None

    try:
        content = response["choices"][0]["message"]["content"]
        parsed = _extract_json_object(content)
        if parsed is not None:
            cache_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        return parsed
    except Exception:
        return None


def _is_numeric_series(series: pd.Series) -> bool:
    sample = series.dropna().head(50)
    if sample.empty:
        return False
    parsed = pd.to_numeric(sample, errors="coerce")
    return float(parsed.notna().mean()) >= 0.8


def _is_date_series(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(50)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", utc=False, format="mixed")
    return float(parsed.notna().mean()) >= 0.8


def _infer_semantic_type(col_name: str, series: pd.Series) -> str:
    cname = col_name.lower()
    if _is_key_like(col_name):
        return "id"
    if any(tok in cname for tok in {"date", "time", "year", "month", "day"}):
        return "date"
    if any(tok in cname for tok in {"name", "title", "city", "location", "company", "first", "last"}):
        return "name"
    if any(tok in cname for tok in {"count", "number", "amount", "price", "salary", "total", "value", "score"}):
        return "measure"
    if _is_date_series(series):
        return "date"
    if _is_numeric_series(series):
        return "numeric"
    return "text"


def _question_tokens(instruction: str) -> List[str]:
    return [tok for tok in _tokenize(instruction) if tok not in STOPWORDS]


def _question_score(tokens: List[str], source: SourceInfo) -> float:
    if not tokens:
        return 0.0
    col_tokens = {tok for col in source.columns for tok in _tokenize(col)}
    sample_values = source.sample.fillna("").astype(str).values.flatten().tolist()
    sample_text = " ".join(sample_values[:80]).lower()

    score = 0.0
    for tok in tokens:
        if tok in col_tokens:
            score += 1.5
        if tok and tok in sample_text:
            score += 0.5
    return score


def _canonical_semantic_type(canonical_col: str, hints: List[Dict[str, Any]], is_join: bool) -> str:
    if is_join or _is_key_like(canonical_col):
        return "id"
    cname = canonical_col.lower()
    if any(tok in cname for tok in {"date", "time", "year", "month", "day"}):
        return "date"
    if any(tok in cname for tok in {"name", "title", "city", "location", "company", "first", "last"}):
        return "name"
    if any(tok in cname for tok in {"count", "number", "amount", "price", "salary", "total", "value", "score"}):
        return "measure"
    for hint in hints:
        literal = str(hint.get("literal", "")).strip().strip("'").strip('"')
        if re.fullmatch(r"-?\d+(\.\d+)?", literal):
            return "numeric"
    return "text"


def _semantic_match_bonus(expected: str, actual: str) -> float:
    if expected == actual:
        return 6.0
    if expected == "id" and actual in {"id", "numeric"}:
        return 4.0
    if expected == "measure" and actual in {"measure", "numeric"}:
        return 3.0
    if expected == "name" and actual in {"name", "text"}:
        return 3.0
    if expected == "text" and actual in {"name", "text"}:
        return 2.0
    if expected == "date" and actual != "date":
        return -6.0
    if expected in {"name", "text"} and actual in {"numeric", "measure", "date", "id"}:
        return -6.0
    if expected in {"measure", "numeric"} and actual in {"date", "name"}:
        return -4.0
    if expected == "id" and actual in {"date", "name", "text"}:
        return -4.0
    return 0.0


def _profile_sources(instruction: str, sources: List[SourceInfo]) -> Dict[str, SourceProfile]:
    tokens = _question_tokens(instruction)
    profiles: Dict[str, SourceProfile] = {}
    for source in sources:
        source_id = _source_id(source)
        semantic_types = {
            col: _infer_semantic_type(col, source.sample[col])
            for col in source.columns
        }
        key_columns = [col for col in source.columns if semantic_types.get(col) == "id"] or _candidate_key_columns(source)
        profiles[source_id] = SourceProfile(
            source_id=source_id,
            question_score=_question_score(tokens, source),
            semantic_types=semantic_types,
            key_columns=key_columns[:10],
            row_count=int(len(source.sample)),
            col_count=int(len(source.columns)),
        )
    return profiles


def _build_relation_graph(
    sources: List[SourceInfo],
    profiles: Dict[str, SourceProfile],
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    graph: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for i, left in enumerate(sources):
        left_id = _source_id(left)
        left_keys = profiles[left_id].key_columns[:8] or left.columns[:8]
        for right in sources[i + 1:]:
            right_id = _source_id(right)
            right_keys = profiles[right_id].key_columns[:8] or right.columns[:8]
            best = {
                "score": 0.0,
                "left_col": None,
                "right_col": None,
                "left_norm": "identity",
                "right_norm": "identity",
            }
            for left_col in left_keys:
                for right_col in right_keys:
                    overlap, left_norm, right_norm = _best_norm_overlap(left.sample[left_col], right.sample[right_col])
                    if overlap > best["score"]:
                        best = {
                            "score": float(overlap),
                            "left_col": left_col,
                            "right_col": right_col,
                            "left_norm": left_norm,
                            "right_norm": right_norm,
                        }
            graph[tuple(sorted((left_id, right_id)))] = best
    return graph


def _rank_table_candidates(
    instruction: str,
    gold_sql: str,
    sources: List[SourceInfo],
    profiles: Dict[str, SourceProfile],
    top_k: int = 4,
) -> Dict[str, List[TableCandidate]]:
    del instruction
    meta = parse_sql_metadata(gold_sql)
    filter_hints = _extract_filter_hints(gold_sql)
    join_key_columns = {k: set(v) for k, v in meta.get("join_key_columns", {}).items()}

    candidates_by_table: Dict[str, List[TableCandidate]] = {}
    for canonical_table in meta["tables"]:
        referenced_cols = meta.get("table_columns", {}).get(canonical_table, [])
        table_candidates: List[TableCandidate] = []
        for source in sources:
            source_id = _source_id(source)
            profile = profiles[source_id]
            base_score = _table_score(
                canonical_table,
                referenced_cols,
                source,
                filter_hints.get(canonical_table, {}),
            )

            semantic_bonus = 0.0
            for canonical_col in referenced_cols:
                expected = _canonical_semantic_type(
                    canonical_col,
                    filter_hints.get(canonical_table, {}).get(canonical_col, []),
                    canonical_col in join_key_columns.get(canonical_table, set()),
                )
                actual_best = max(
                    (
                        _semantic_match_bonus(expected, profile.semantic_types.get(source_col, "text"))
                        for source_col in source.columns
                    ),
                    default=0.0,
                )
                semantic_bonus += actual_best

            total_score = base_score + profile.question_score + semantic_bonus
            table_candidates.append(
                TableCandidate(
                    canonical_table=canonical_table,
                    source=source,
                    score=float(total_score),
                    base_score=float(base_score),
                    question_score=float(profile.question_score),
                    semantic_bonus=float(semantic_bonus),
                )
            )

        table_candidates.sort(key=lambda item: item.score, reverse=True)
        candidates_by_table[canonical_table] = table_candidates[:top_k]
    return candidates_by_table


def _enumerate_table_combos(
    meta: Dict[str, Any],
    candidates_by_table: Dict[str, List[TableCandidate]],
    relation_graph: Dict[Tuple[str, str], Dict[str, Any]],
    max_combos: int = 8,
) -> List[Dict[str, Any]]:
    table_order = list(meta["tables"])
    combos: List[Dict[str, Any]] = []
    for candidate_tuple in product(*[candidates_by_table[table] for table in table_order]):
        source_ids = [_source_id(candidate.source) for candidate in candidate_tuple]
        if len(set(source_ids)) != len(source_ids):
            continue

        combo_map = {table: candidate.source for table, candidate in zip(table_order, candidate_tuple)}
        combo_score = sum(candidate.score for candidate in candidate_tuple)
        relation_debug: List[Dict[str, Any]] = []
        for edge in meta.get("joins", []):
            left_id = _source_id(combo_map[edge["left_table"]])
            right_id = _source_id(combo_map[edge["right_table"]])
            rel = relation_graph.get(tuple(sorted((left_id, right_id))), {"score": 0.0})
            combo_score += float(rel.get("score", 0.0)) * 35.0
            relation_debug.append(
                {
                    "left_table": edge["left_table"],
                    "right_table": edge["right_table"],
                    "relation_score": round(float(rel.get("score", 0.0)), 4),
                }
            )

        combos.append(
            {
                "score": float(combo_score),
                "table_map": combo_map,
                "selected_tables": {
                    table: {
                        "selected_view": candidate.source.view_name,
                        "selected_file": candidate.source.file_name,
                        "score": round(candidate.score, 4),
                        "base_score": round(candidate.base_score, 4),
                        "question_score": round(candidate.question_score, 4),
                        "semantic_bonus": round(candidate.semantic_bonus, 4),
                    }
                    for table, candidate in zip(table_order, candidate_tuple)
                },
                "relation_debug": relation_debug,
            }
        )

    combos.sort(key=lambda item: item["score"], reverse=True)
    return combos[:max_combos]


def _rank_nonjoin_options(
    canonical_table: str,
    canonical_col: str,
    source: SourceInfo,
    source_profile: SourceProfile,
    filter_hints: Dict[str, Dict[str, List[Dict[str, Any]]]],
) -> List[ColumnOption]:
    hints = filter_hints.get(canonical_table, {}).get(canonical_col, [])
    expected_semantic = _canonical_semantic_type(canonical_col, hints, is_join=False)
    options: List[ColumnOption] = []

    for source_col in source.columns:
        actual_semantic = source_profile.semantic_types.get(source_col, "text")
        name_score = _name_similarity(canonical_col, source_col)
        literal_score = _literal_match_score(source.sample[source_col], hints)
        confidence = 0.0
        if source_col == canonical_col:
            confidence += 60.0
        confidence += name_score * 25.0
        confidence += literal_score * 8.0
        confidence += _semantic_match_bonus(expected_semantic, actual_semantic)
        if _is_key_like(source_col):
            confidence -= 5.0
        if hints and literal_score == 0.0:
            confidence -= 2.0

        options.append(
            ColumnOption(
                source_col=source_col,
                confidence=float(confidence),
                semantic_type=actual_semantic,
                literal_score=float(literal_score),
                name_score=float(name_score),
            )
        )

    options.sort(key=lambda item: item.confidence, reverse=True)
    return options[:4]


def _join_strategy(left_norm: str, right_norm: str) -> str:
    if left_norm == "identity" and right_norm == "identity":
        return "exact"
    if "sep" in {left_norm, right_norm}:
        return "semantic"
    return "normalized"


def _rank_join_options(
    edge: Dict[str, str],
    table_map: Dict[str, SourceInfo],
    profiles: Dict[str, SourceProfile],
) -> List[JoinOption]:
    left_source = table_map[edge["left_table"]]
    right_source = table_map[edge["right_table"]]
    left_profile = profiles[_source_id(left_source)]
    right_profile = profiles[_source_id(right_source)]

    left_candidates = left_profile.key_columns[:8] or _candidate_key_columns(left_source)[:8]
    right_candidates = right_profile.key_columns[:8] or _candidate_key_columns(right_source)[:8]
    if edge["left_col"] in left_source.columns and edge["left_col"] not in left_candidates:
        left_candidates = [edge["left_col"]] + left_candidates
    if edge["right_col"] in right_source.columns and edge["right_col"] not in right_candidates:
        right_candidates = [edge["right_col"]] + right_candidates

    options: List[JoinOption] = []
    seen_pairs: set[Tuple[str, str, str, str]] = set()
    for left_col in left_candidates:
        for right_col in right_candidates:
            overlap, left_norm, right_norm = _best_norm_overlap(
                left_source.sample[left_col],
                right_source.sample[right_col],
            )
            actual_left = left_profile.semantic_types.get(left_col, "text")
            actual_right = right_profile.semantic_types.get(right_col, "text")
            confidence = overlap * 120.0
            if left_col == edge["left_col"]:
                confidence += 12.0
            if right_col == edge["right_col"]:
                confidence += 12.0
            if actual_left == "id":
                confidence += 5.0
            if actual_right == "id":
                confidence += 5.0
            if actual_left == actual_right:
                confidence += 4.0

            key = (left_col, right_col, left_norm, right_norm)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)

            options.append(
                JoinOption(
                    left_col=left_col,
                    right_col=right_col,
                    left_norm=left_norm,
                    right_norm=right_norm,
                    overlap=float(overlap),
                    confidence=float(confidence),
                    strategy=_join_strategy(left_norm, right_norm),
                )
            )

    options.sort(key=lambda item: item.confidence, reverse=True)
    return options[:4]


def _build_alignment_options(
    meta: Dict[str, Any],
    table_map: Dict[str, SourceInfo],
    profiles: Dict[str, SourceProfile],
    filter_hints: Dict[str, Dict[str, List[Dict[str, Any]]]],
) -> Tuple[Dict[str, List[ColumnOption]], Dict[str, List[JoinOption]], Dict[str, Any]]:
    join_key_columns = {k: set(v) for k, v in meta.get("join_key_columns", {}).items()}
    nonjoin_options: Dict[str, List[ColumnOption]] = {}
    join_options: Dict[str, List[JoinOption]] = {}

    for table, source in table_map.items():
        profile = profiles[_source_id(source)]
        for canonical_col in meta.get("table_columns", {}).get(table, []):
            if canonical_col in join_key_columns.get(table, set()):
                continue
            key = f"{table}.{canonical_col}"
            nonjoin_options[key] = _rank_nonjoin_options(table, canonical_col, source, profile, filter_hints)

    for edge in meta.get("joins", []):
        key = f"{edge['left_table']}.{edge['left_col']}={edge['right_table']}.{edge['right_col']}"
        join_options[key] = _rank_join_options(edge, table_map, profiles)

    debug = {
        "nonjoin_options": {
            key: [
                {
                    "source_col": option.source_col,
                    "confidence": round(option.confidence, 4),
                    "semantic_type": option.semantic_type,
                }
                for option in options
            ]
            for key, options in nonjoin_options.items()
        },
        "join_options": {
            key: [
                {
                    "left_col": option.left_col,
                    "right_col": option.right_col,
                    "strategy": option.strategy,
                    "overlap": round(option.overlap, 4),
                    "confidence": round(option.confidence, 4),
                }
                for option in options
            ]
            for key, options in join_options.items()
        },
    }
    return nonjoin_options, join_options, debug


def _assemble_mapping(
    meta: Dict[str, Any],
    nonjoin_options: Dict[str, List[ColumnOption]],
    join_options: Dict[str, List[JoinOption]],
    state: SearchState,
) -> Tuple[Dict[str, Dict[str, str]] | None, Dict[str, Dict[str, str]] | None, Dict[str, Any]]:
    column_map: Dict[str, Dict[str, str]] = {table: {} for table in meta["tables"]}
    inverse_map: Dict[str, Dict[str, str]] = {table: {} for table in meta["tables"]}
    selected_columns: Dict[str, Dict[str, Any]] = {table: {} for table in meta["tables"]}
    join_validation: Dict[str, Dict[str, Any]] = {}
    selected_source_cols: Dict[str, set[str]] = {table: set() for table in meta["tables"]}
    resolved_nonjoin_choice: Dict[str, int] = {}

    for edge in meta.get("joins", []):
        key = f"{edge['left_table']}.{edge['left_col']}={edge['right_table']}.{edge['right_col']}"
        options = join_options.get(key, [])
        if not options:
            return None, None, {"error": f"no join options for {key}"}
        selected_index = min(state.join_choice.get(key, 0), len(options) - 1)
        option = options[selected_index]

        left_existing = column_map[edge["left_table"]].get(edge["left_col"])
        right_existing = column_map[edge["right_table"]].get(edge["right_col"])
        if left_existing and left_existing != option.left_col:
            return None, None, {"error": f"inconsistent left join mapping for {edge['left_table']}.{edge['left_col']}"}
        if right_existing and right_existing != option.right_col:
            return None, None, {"error": f"inconsistent right join mapping for {edge['right_table']}.{edge['right_col']}"}

        column_map[edge["left_table"]][edge["left_col"]] = option.left_col
        column_map[edge["right_table"]][edge["right_col"]] = option.right_col
        inverse_map[edge["left_table"]][edge["left_col"]] = option.left_norm
        inverse_map[edge["right_table"]][edge["right_col"]] = option.right_norm
        selected_source_cols[edge["left_table"]].add(option.left_col)
        selected_source_cols[edge["right_table"]].add(option.right_col)

        selected_columns[edge["left_table"]][edge["left_col"]] = {
            "source_col": option.left_col,
            "norm": option.left_norm,
            "confidence": round(option.confidence, 4),
        }
        selected_columns[edge["right_table"]][edge["right_col"]] = {
            "source_col": option.right_col,
            "norm": option.right_norm,
            "confidence": round(option.confidence, 4),
        }
        join_validation[key] = {
            "left_col": option.left_col,
            "right_col": option.right_col,
            "left_norm": option.left_norm,
            "right_norm": option.right_norm,
            "overlap": round(option.overlap, 4),
            "strategy": option.strategy,
            "confidence": round(option.confidence, 4),
        }

    join_key_columns = {k: set(v) for k, v in meta.get("join_key_columns", {}).items()}
    for table in meta["tables"]:
        for canonical_col in meta.get("table_columns", {}).get(table, []):
            if canonical_col in join_key_columns.get(table, set()):
                continue
            key = f"{table}.{canonical_col}"
            options = nonjoin_options.get(key, [])
            if not options:
                return None, None, {"error": f"no nonjoin options for {key}"}

            start_index = min(state.nonjoin_choice.get(key, 0), len(options) - 1)
            chosen_index = None
            chosen_option = None
            for idx in range(start_index, len(options)):
                candidate = options[idx]
                if candidate.source_col in selected_source_cols[table]:
                    continue
                chosen_index = idx
                chosen_option = candidate
                break

            if chosen_option is None:
                return None, None, {"error": f"no usable nonjoin option for {key}"}

            resolved_nonjoin_choice[key] = chosen_index
            selected_source_cols[table].add(chosen_option.source_col)
            column_map[table][canonical_col] = chosen_option.source_col
            inverse_map[table][canonical_col] = "identity"
            selected_columns[table][canonical_col] = {
                "source_col": chosen_option.source_col,
                "norm": "identity",
                "confidence": round(chosen_option.confidence, 4),
            }

    return column_map, inverse_map, {
        "selected_columns": selected_columns,
        "join_validation": join_validation,
        "resolved_nonjoin_choice": resolved_nonjoin_choice,
    }


def _execute_sql_script(sql_script: str) -> Tuple[bool, pd.DataFrame, str | None]:
    conn = duckdb.connect(database=":memory:")
    try:
        conn.execute("INSTALL sqlite;")
        conn.execute("LOAD sqlite;")
        statements = [stmt.strip() for stmt in sql_script.split(";") if stmt.strip()]
        for stmt in statements[:-1]:
            conn.execute(stmt)
        df = conn.execute(statements[-1]).fetchdf()
        return True, df, None
    except Exception as exc:  # noqa: BLE001
        return False, pd.DataFrame(), str(exc)
    finally:
        conn.close()


def _result_reason(success: bool, df: pd.DataFrame, error: str | None) -> str:
    if not success:
        message = (error or "").lower()
        if "convert" in message or "cast" in message:
            return "type_error"
        return "execution_error"
    if df.empty:
        return "empty"
    return "ok"


def _state_score(
    combo_score: float,
    join_validation: Dict[str, Dict[str, Any]],
    selected_columns: Dict[str, Dict[str, Any]],
    success: bool,
    df: pd.DataFrame,
) -> float:
    score = combo_score
    score += sum(item["confidence"] for item in join_validation.values())
    for table_values in selected_columns.values():
        score += sum(value["confidence"] * 0.3 for value in table_values.values())
    if success:
        score += 180.0
    if success and not df.empty:
        score += 60.0
    if success and df.empty:
        score -= 25.0
    return float(score)


def _next_states(
    state: SearchState,
    evaluation: Dict[str, Any],
    nonjoin_options: Dict[str, List[ColumnOption]],
    join_options: Dict[str, List[JoinOption]],
    filter_hints: Dict[str, Dict[str, List[Dict[str, Any]]]],
) -> List[SearchState]:
    targets: List[Tuple[float, str, str]] = []
    reason = evaluation["reason"]
    resolved_nonjoin_choice = evaluation.get("resolved_nonjoin_choice", {})
    join_validation = evaluation.get("join_validation", {})
    selected_columns = evaluation.get("selected_columns", {})

    if reason in {"empty", "execution_error"}:
        for key, value in join_validation.items():
            targets.append((float(value.get("overlap", 0.0)), "join", key))

    filter_keys = {
        f"{table}.{col}"
        for table, cols in filter_hints.items()
        for col in cols
    }
    for table, cols in selected_columns.items():
        for canonical_col, value in cols.items():
            key = f"{table}.{canonical_col}"
            if key in join_options:
                continue
            confidence = float(value.get("confidence", 0.0))
            if reason == "type_error" and key in filter_keys:
                confidence -= 20.0
            targets.append((confidence, "nonjoin", key))

    targets.sort(key=lambda item: item[0])

    next_states: List[SearchState] = []
    for _metric, kind, key in targets:
        if kind == "join":
            current_index = state.join_choice.get(key, 0)
            if current_index + 1 >= len(join_options.get(key, [])):
                continue
            new_state = SearchState(
                nonjoin_choice=copy.deepcopy(state.nonjoin_choice),
                join_choice=copy.deepcopy(state.join_choice),
                depth=state.depth + 1,
            )
            new_state.join_choice[key] = current_index + 1
            next_states.append(new_state)
        else:
            current_index = resolved_nonjoin_choice.get(key, state.nonjoin_choice.get(key, 0))
            if current_index + 1 >= len(nonjoin_options.get(key, [])):
                continue
            new_state = SearchState(
                nonjoin_choice=copy.deepcopy(state.nonjoin_choice),
                join_choice=copy.deepcopy(state.join_choice),
                depth=state.depth + 1,
            )
            new_state.nonjoin_choice[key] = current_index + 1
            next_states.append(new_state)
        if len(next_states) >= 4:
            break
    return next_states


def _state_signature(state: SearchState) -> Tuple[Tuple[Tuple[str, int], ...], Tuple[Tuple[str, int], ...]]:
    return (
        tuple(sorted(state.nonjoin_choice.items())),
        tuple(sorted(state.join_choice.items())),
    )


def run_hdrbench_agent(
    instruction: str,
    workspace: Path,
    gold_sql: str | None,
    output_csv: Path,
    max_table_combos: int = 8,
    max_states_per_combo: int = 6,
    max_total_attempts: int = 18,
) -> Dict[str, Any]:
    if not gold_sql:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(output_csv, index=False)
        return {
            "success": False,
            "files_touched": [],
            "error": "gold_sql unavailable: hdrbench_agent currently supports dev mode only",
            "selected_tables": {},
            "selected_columns": {},
            "join_validation": {},
            "sql_script": "",
            "trace": {},
        }

    sources, touched = _discover_sources(workspace)
    profiles = _profile_sources(instruction, sources)
    relation_graph = _build_relation_graph(sources, profiles)
    meta = parse_sql_metadata(gold_sql)
    filter_hints = _extract_filter_hints(gold_sql)
    candidates_by_table = _rank_table_candidates(instruction, gold_sql, sources, profiles)
    table_combos = _enumerate_table_combos(meta, candidates_by_table, relation_graph, max_combos=max_table_combos)

    trace: Dict[str, Any] = {
        "module_m1": {
            "question_tokens": _question_tokens(instruction),
            "profiles": {
                source_id: {
                    "question_score": round(profile.question_score, 4),
                    "key_columns": profile.key_columns,
                    "semantic_types": profile.semantic_types,
                }
                for source_id, profile in profiles.items()
            },
            "candidate_tables": {
                table: [
                    {
                        "view": candidate.source.view_name,
                        "file": candidate.source.file_name,
                        "score": round(candidate.score, 4),
                    }
                    for candidate in candidates
                ]
                for table, candidates in candidates_by_table.items()
            },
        },
        "combos": [],
    }

    best_result: Dict[str, Any] | None = None
    total_attempts = 0

    for combo_index, combo in enumerate(table_combos):
        if total_attempts >= max_total_attempts:
            break

        nonjoin_options, join_options, alignment_debug = _build_alignment_options(
            meta,
            combo["table_map"],
            profiles,
            filter_hints,
        )
        combo_trace = {
            "combo_index": combo_index,
            "combo_score": round(combo["score"], 4),
            "selected_tables": combo["selected_tables"],
            "relation_debug": combo["relation_debug"],
            "alignment": alignment_debug,
            "attempts": [],
        }
        trace["combos"].append(combo_trace)

        queue: List[SearchState] = [SearchState(nonjoin_choice={}, join_choice={})]
        visited = {_state_signature(queue[0])}
        combo_attempts = 0

        while queue and combo_attempts < max_states_per_combo and total_attempts < max_total_attempts:
            state = queue.pop(0)
            column_map, inverse_map, assembly = _assemble_mapping(meta, nonjoin_options, join_options, state)
            total_attempts += 1
            combo_attempts += 1

            if column_map is None or inverse_map is None:
                evaluation = {
                    "success": False,
                    "reason": "assembly_error",
                    "error": assembly.get("error", "unknown assembly error"),
                    "score": combo["score"] - 50.0,
                    "selected_columns": {},
                    "join_validation": {},
                    "resolved_nonjoin_choice": {},
                    "sql_script": "",
                    "result_rows": 0,
                }
            else:
                sql_script = _build_agent_sql(gold_sql, combo["table_map"], column_map, inverse_map)
                success, df, error = _execute_sql_script(sql_script)
                evaluation = {
                    "success": success,
                    "reason": _result_reason(success, df, error),
                    "error": error,
                    "sql_script": sql_script,
                    "selected_columns": assembly["selected_columns"],
                    "join_validation": assembly["join_validation"],
                    "resolved_nonjoin_choice": assembly["resolved_nonjoin_choice"],
                    "result_rows": int(len(df)),
                    "df": df,
                }
                evaluation["score"] = _state_score(
                    combo["score"],
                    assembly["join_validation"],
                    assembly["selected_columns"],
                    success,
                    df,
                )

            combo_trace["attempts"].append(
                {
                    "depth": state.depth,
                    "reason": evaluation["reason"],
                    "score": round(float(evaluation["score"]), 4),
                    "error": evaluation.get("error"),
                    "result_rows": evaluation.get("result_rows", 0),
                    "join_validation": evaluation.get("join_validation", {}),
                    "selected_columns": evaluation.get("selected_columns", {}),
                }
            )

            if (
                best_result is None
                or (evaluation["success"] and not best_result.get("success"))
                or (evaluation["success"] == best_result.get("success") and evaluation["score"] > best_result["score"])
            ):
                best_result = {
                    "success": evaluation["success"],
                    "error": evaluation.get("error"),
                    "reason": evaluation["reason"],
                    "score": evaluation["score"],
                    "df": evaluation.get("df", pd.DataFrame()),
                    "sql_script": evaluation.get("sql_script", ""),
                    "selected_tables": combo["selected_tables"],
                    "selected_columns": evaluation.get("selected_columns", {}),
                    "join_validation": evaluation.get("join_validation", {}),
                }

            if evaluation["success"] and evaluation["reason"] == "ok":
                if all(item.get("overlap", 0.0) > 0.0 for item in evaluation["join_validation"].values()):
                    queue = []
                    break

            for next_state in _next_states(state, evaluation, nonjoin_options, join_options, filter_hints):
                signature = _state_signature(next_state)
                if signature in visited:
                    continue
                visited.add(signature)
                queue.append(next_state)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    if best_result and best_result.get("success"):
        best_df = best_result.get("df", pd.DataFrame())
        best_df.to_csv(output_csv, index=False)
        return {
            "success": True,
            "files_touched": touched,
            "error": None,
            "selected_tables": best_result.get("selected_tables", {}),
            "selected_columns": best_result.get("selected_columns", {}),
            "join_validation": best_result.get("join_validation", {}),
            "sql_script": best_result.get("sql_script", ""),
            "trace": trace,
        }

    pd.DataFrame().to_csv(output_csv, index=False)
    return {
        "success": False,
        "files_touched": touched,
        "error": None if best_result is None else best_result.get("error"),
        "selected_tables": {} if best_result is None else best_result.get("selected_tables", {}),
        "selected_columns": {} if best_result is None else best_result.get("selected_columns", {}),
        "join_validation": {} if best_result is None else best_result.get("join_validation", {}),
        "sql_script": "" if best_result is None else best_result.get("sql_script", ""),
        "trace": trace,
    }
