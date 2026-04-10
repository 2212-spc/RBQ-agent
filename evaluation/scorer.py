from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd


def _normalize_df(df: pd.DataFrame, required_cols: list[str], tolerance: float) -> pd.DataFrame:
    out = df[required_cols].copy()
    for c in out.columns:
        if pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].astype(float).round(6)
        else:
            out[c] = out[c].astype(str).str.strip()
    return out


def _row_signature(df: pd.DataFrame) -> pd.Series:
    return df.apply(lambda row: "||".join(str(v) for v in row.tolist()), axis=1)


def score_single(result_path: str | Path, gold_path: str | Path, spec: Dict[str, Any]) -> Dict[str, Any]:
    result_path = Path(result_path)
    gold_path = Path(gold_path)

    if not result_path.exists():
        return {"pass": False, "score": 0.0, "stage": "DELIVERY_FAIL", "detail": "result file missing"}

    try:
        result = pd.read_csv(result_path)
    except Exception as exc:  # noqa: BLE001
        return {
            "pass": False,
            "score": 0.0,
            "stage": "DELIVERY_FAIL",
            "detail": f"result parse error: {exc}",
        }

    gold = pd.read_csv(gold_path)
    required_cols = list(spec.get("required_columns", list(gold.columns)))

    if not set(required_cols).issubset(set(result.columns)):
        missing = sorted(set(required_cols) - set(result.columns))
        return {
            "pass": False,
            "score": 0.1,
            "stage": "SCHEMA_FAIL",
            "detail": f"missing columns: {missing}",
            "missing_columns": missing,
        }

    tolerance = float(spec.get("float_tolerance", 1e-6))
    result_norm = _normalize_df(result, required_cols, tolerance)
    gold_norm = _normalize_df(gold, required_cols, tolerance)

    if len(result_norm) == 0 and len(gold_norm) == 0:
        return {
            "pass": True,
            "score": 1.0,
            "stage": None,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "result_rows": 0,
            "gold_rows": 0,
        }

    if len(result_norm) == 0:
        return {
            "pass": False,
            "score": 0.0,
            "stage": "QUERY_FAIL",
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "result_rows": 0,
            "gold_rows": int(len(gold_norm)),
        }

    if not bool(spec.get("order_required", False)):
        result_norm = result_norm.sort_values(required_cols).reset_index(drop=True)
        gold_norm = gold_norm.sort_values(required_cols).reset_index(drop=True)

    sig_res = _row_signature(result_norm)
    sig_gold = _row_signature(gold_norm)

    res_counts = sig_res.value_counts().to_dict()
    gold_counts = sig_gold.value_counts().to_dict()

    matched = 0
    for row_sig, cnt in res_counts.items():
        matched += min(cnt, gold_counts.get(row_sig, 0))

    precision = matched / max(len(sig_res), 1)
    recall = matched / max(len(sig_gold), 1)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    pass_flag = f1 >= 0.999
    if pass_flag:
        stage = None
    elif precision < 0.5 and recall > 0.5:
        stage = "INSTANCE_FAIL"
    elif precision > 0.5 and recall < 0.5:
        stage = "QUERY_FAIL"
    else:
        stage = "QUERY_FAIL"

    return {
        "pass": pass_flag,
        "score": 1.0 if pass_flag else float(f1),
        "stage": stage,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "result_rows": int(len(result_norm)),
        "gold_rows": int(len(gold_norm)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a single result CSV against gold CSV.")
    parser.add_argument("--result", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--spec_json", required=True, help="Path to deliverable spec json")
    args = parser.parse_args()

    spec = json.loads(Path(args.spec_json).read_text(encoding="utf-8"))
    out = score_single(args.result, args.gold, spec)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
