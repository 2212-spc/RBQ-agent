from __future__ import annotations

import re
from typing import Any, Dict, List

from evaluation.workspace_catalog import tokenize


def name_overlap_score(a: str, b: str) -> float:
    ta = set(tokenize(a))
    tb = set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def question_tokens(instruction: str) -> List[str]:
    return tokenize(instruction)


def sample_value_overlap_score(
    slot_label: str,
    instruction: str,
    sample_values: List[Any],
    slot_role: str,
) -> tuple[float, List[str]]:
    """Score a column based on semantic patterns in its sample values.

    This is the key fallback for L2 where column names are obfuscated
    (e.g., "col_3") but sample values carry semantic signal
    (e.g., "$500,000" for a price column, "2020-01-15" for a date).

    Returns (score, reasons).
    """
    if not sample_values:
        return 0.0, []

    score = 0.0
    reasons: List[str] = []

    # Build semantic tokens from instruction + slot label
    semantic_tokens = set(tokenize(instruction)) | set(tokenize(slot_label))

    # Price / money patterns
    money_tokens = {"price", "cost", "amount", "value", "revenue", "salary", "payment", "fee", "budget", "income"}
    # Count / number patterns
    count_tokens = {"count", "number", "total", "quantity", "quantity"}
    # Date / time patterns
    time_tokens = {"date", "time", "year", "month", "day", "period", "when"}

    for sv in sample_values[:8]:
        sv_str = str(sv)
        sv_lower = sv_str.lower()

        # Money: "$500,000" or "500000" or "USD 500"
        if any(c in sv_str for c in ["$", "¥", "€", "£"]) or re.search(r"\d{1,3}(?:,\d{3})+(?:\.\d{2})?", sv_str):
            if semantic_tokens & money_tokens:
                score += 4.0
                reasons.append("sample_money_value")
            if slot_role == "measure":
                score += 2.0
        # Percentage
        if "%" in sv_str or re.search(r"\d+\.\d+%", sv_str):
            if "rate" in semantic_tokens or "percent" in semantic_tokens or "ratio" in semantic_tokens:
                score += 4.0
                reasons.append("sample_percentage_value")
        # Boolean-like
        if sv_lower in {"true", "false", "yes", "no", "1", "0"}:
            if "status" in semantic_tokens or "flag" in semantic_tokens or "active" in semantic_tokens:
                score += 3.0
                reasons.append("sample_boolean_value")
        # Date patterns
        if re.match(r"\d{4}[-/]\d{2}[-/]\d{2}", sv_str) or re.match(r"\d{2}[-/]\d{2}[-/]\d{4}", sv_str):
            if semantic_tokens & time_tokens:
                score += 4.0
                reasons.append("sample_date_value")
        # Year only
        if re.match(r"19\d{2}|20\d{2}$", sv_str):
            if "year" in semantic_tokens:
                score += 4.0
                reasons.append("sample_year_value")
        # Numeric with decimal (ratings, scores)
        if re.match(r"^\d+\.\d+$", sv_str):
            if "rating" in semantic_tokens or "score" in semantic_tokens or "average" in semantic_tokens:
                score += 3.5
                reasons.append("sample_rating_value")
        # Large integer (counts, IDs that look like counts)
        if re.match(r"^\d{1,6}$", sv_str) and int(sv_str) > 10:
            if semantic_tokens & count_tokens:
                score += 3.0
                reasons.append("sample_count_like")

    return score, reasons


def _semantic_key(text: str) -> str:
    """Normalize a string to a comparable key by lowercasing and removing spaces/punctuation."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def infer_output_role(label: str, instruction: str) -> str:
    lower = label.lower()
    qtokens = set(question_tokens(instruction))
    if any(token in lower for token in ["count", "number", "total", "avg", "average", "sum", "max", "min"]):
        return "measure"
    if any(token in lower for token in ["date", "year", "month", "time"]):
        return "time"
    if any(token in lower for token in ["id", "key"]):
        return "key"
    if "code" in lower:
        return "code"
    if "status" in lower:
        return "status"
    if "description" in lower or "detail" in lower:
        return "description"
    if "location" in lower or "address" in lower or "city" in lower or "country" in lower:
        return "location"
    if "name" in lower or lower in qtokens:
        return "entity"
    return "attribute"


def normalize_json_list(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            out.append(dict(item))
    return out


def _clean_order_target(text: str) -> str | None:
    cleaned = re.sub(r"[?.,;:]+$", "", text.strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"^(the|a|an)\s+", "", cleaned)
    cleaned = re.split(r"\b(where|with|that|which|who|when|while|after|before|because|having)\b", cleaned, maxsplit=1)[0].strip()
    return cleaned or None


def extract_order_target(instruction: str) -> str | None:
    lower = instruction.lower()
    patterns = [
        r"\bin\s+(?:ascending|descending)\s+order\s+of\s+([a-z0-9_ ]+)",
        r"\b(?:ordered|sorted)\s+by\s+([a-z0-9_ ]+)",
        r"\border\s+by\s+([a-z0-9_ ]+)",
        r"\bsort\s+by\s+([a-z0-9_ ]+)",
        r"\b(?:highest|lowest|largest|smallest|greatest|minimum|maximum)\s+([a-z0-9_ ]+)",
        r"\b(?:shortest|earliest|latest|longest|fastest|slowest)\s+([a-z0-9_ ]+)",
        r"\b(?:first|second|third|last)\s+([a-z0-9_ ]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return _clean_order_target(match.group(1))
    return None


def infer_operator_hints(instruction: str) -> Dict[str, Any]:
    lower = instruction.lower()

    def _wb(*words: str) -> bool:
        """Return True if any of *words appears as a whole word in lower."""
        return any(bool(re.search(r"\b" + re.escape(w) + r"\b", lower)) for w in words)

    explicit_order_phrase = bool(
        re.search(r"\b(?:in\s+(?:ascending|descending)\s+order\s+of|(?:ordered|sorted|sort|order)\s+by)\b", lower)
    )
    order_target = extract_order_target(instruction)

    aggregation = None
    if _wb("count") or "number of" in lower or "how many" in lower or _wb("least", "fewest", "most"):
        aggregation = "count"
    elif "average" in lower or re.search(r"\bavg\b", lower):
        aggregation = "avg"
    elif _wb("sum") or _wb("total"):
        aggregation = "sum"
    elif (_wb("maximum") or re.search(r"\bmax\b", lower) or (_wb("highest") and not explicit_order_phrase)):
        aggregation = "max"
    elif (_wb("minimum") or re.search(r"\bmin\b", lower) or (_wb("lowest") and not explicit_order_phrase)):
        aggregation = "min"

    direction = None
    if _wb("ascending") or "ascending order" in lower:
        direction = "asc"
    elif _wb("descending") or "descending order" in lower:
        direction = "desc"
    elif _wb("least", "fewest", "lowest", "smallest", "minimum", "shortest", "earliest"):
        direction = "asc"
    elif _wb("most", "highest", "largest", "greatest", "maximum", "longest", "latest"):
        direction = "desc"

    limit = 1 if direction and not explicit_order_phrase else None
    group_by = _wb("by", "per")
    exists = _wb("exist", "exists", "whether") or "any " in lower
    intersection = _wb("both") or "all of" in lower
    return {
        "aggregation": aggregation,
        "direction": direction,
        "limit": limit,
        "target": order_target,
        "group_by": group_by,
        "exists": exists,
        "intersection": intersection,
    }


def normalize_operator_direction(direction: str | None) -> str | None:
    """Map LLM/heuristic strings (e.g. ascending) to canonical asc/desc for operator_plan."""
    if not direction:
        return None
    d = str(direction).strip().lower().replace(" ", "")
    if d in ("asc", "ascending"):
        return "asc"
    if d in ("desc", "descending"):
        return "desc"
    return None


def normalize_sql_order_direction(direction: str | None) -> str:
    """Emit DuckDB-valid ORDER BY tokens (ASC | DESC), never ASCENDING/DESCENDING."""
    if not direction:
        return "ASC"
    d = str(direction).strip().lower().replace(" ", "")
    if d in ("asc", "ascending"):
        return "ASC"
    if d in ("desc", "descending"):
        return "DESC"
    u = str(direction).strip().upper()
    if u in ("ASC", "DESC"):
        return u
    return "ASC"
