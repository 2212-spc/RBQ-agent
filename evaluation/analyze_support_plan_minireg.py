from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.motif_taxonomy import build_seed_motif_index
from evaluation.run_hdrbench_eval import _load_json
from evaluation.scorer import score_single


def _iter_seed_variant_records(
    bench_root: Path,
    result_root: Path,
    split: str,
    seed_ids: List[str],
    *,
    variant: str = "A",
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for seed_id in seed_ids:
        pub = _load_json(bench_root / seed_id / "variants" / variant / "manifest_public.json")
        result_csv = result_root / seed_id / variant / split / "full.csv"
        if not result_csv.exists():
            rows.append(
                {
                    "seed_id": seed_id,
                    "variant": variant,
                    "split": split,
                    "pass": False,
                    "score": 0.0,
                    "stage": "DELIVERY_FAIL",
                    "result_rows": 0,
                    "gold_rows": 0,
                    "exists": False,
                }
            )
            continue
        score = score_single(result_csv, pub["gold_path"], pub["deliverable_spec"])
        rows.append(
            {
                "seed_id": seed_id,
                "variant": variant,
                "split": split,
                "pass": bool(score.get("pass")),
                "score": float(score.get("score", 0.0)),
                "stage": score.get("stage"),
                "result_rows": int(score.get("result_rows", 0)),
                "gold_rows": int(score.get("gold_rows", 0)),
                "exists": True,
            }
        )
    return rows


def _summarize(rows: List[Dict[str, Any]], motif_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    passed = sum(int(row["pass"]) for row in rows)
    empty_fail = sum(int((not row["pass"]) and row["result_rows"] == 0) for row in rows)
    nonempty_fail = sum(int((not row["pass"]) and row["result_rows"] > 0) for row in rows)
    by_motif: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_motif[motif_index[row["seed_id"]]["base_label"]].append(row)
    motif_summary: Dict[str, Any] = {}
    for motif, motif_rows in sorted(by_motif.items()):
        motif_total = len(motif_rows)
        motif_summary[motif] = {
            "case_count": motif_total,
            "pass_rate": sum(int(row["pass"]) for row in motif_rows) / motif_total if motif_total else 0.0,
            "empty_fail_ratio": sum(int((not row["pass"]) and row["result_rows"] == 0) for row in motif_rows) / motif_total if motif_total else 0.0,
            "nonempty_fail_ratio": sum(int((not row["pass"]) and row["result_rows"] > 0) for row in motif_rows) / motif_total if motif_total else 0.0,
        }
    return {
        "case_count": total,
        "pass_rate": passed / total if total else 0.0,
        "empty_fail_ratio": empty_fail / total if total else 0.0,
        "nonempty_fail_ratio": nonempty_fail / total if total else 0.0,
        "by_motif": motif_summary,
    }


def _head_to_head(old_rows: List[Dict[str, Any]], new_rows: List[Dict[str, Any]], motif_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    pairs = {row["seed_id"]: row for row in old_rows}
    counts = {"new_only_pass": 0, "old_only_pass": 0, "both_pass": 0, "both_fail": 0}
    transition_counts = {
        "empty_to_nonempty_fail": 0,
        "nonempty_to_empty_fail": 0,
        "avg_score_delta": 0.0,
    }
    motif_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"new_only_pass": 0, "old_only_pass": 0, "both_pass": 0, "both_fail": 0})
    improvements: List[Dict[str, Any]] = []
    for new_row in new_rows:
        old_row = pairs[new_row["seed_id"]]
        motif = motif_index[new_row["seed_id"]]["base_label"]
        if new_row["pass"] and old_row["pass"]:
            key = "both_pass"
        elif new_row["pass"] and not old_row["pass"]:
            key = "new_only_pass"
        elif old_row["pass"] and not new_row["pass"]:
            key = "old_only_pass"
        else:
            key = "both_fail"
        counts[key] += 1
        motif_counts[motif][key] += 1
        transition_counts["avg_score_delta"] += (new_row["score"] - old_row["score"])
        if (not old_row["pass"]) and (not new_row["pass"]):
            if old_row["result_rows"] == 0 and new_row["result_rows"] > 0:
                transition_counts["empty_to_nonempty_fail"] += 1
            if old_row["result_rows"] > 0 and new_row["result_rows"] == 0:
                transition_counts["nonempty_to_empty_fail"] += 1
        if (new_row["score"] - old_row["score"]) != 0:
            improvements.append(
                {
                    "seed_id": new_row["seed_id"],
                    "motif": motif,
                    "old_score": old_row["score"],
                    "new_score": new_row["score"],
                    "old_stage": old_row["stage"],
                    "new_stage": new_row["stage"],
                    "old_result_rows": old_row["result_rows"],
                    "new_result_rows": new_row["result_rows"],
                }
            )
    improvements.sort(key=lambda item: item["new_score"] - item["old_score"], reverse=True)
    return {
        "overall": counts,
        "transitions": {
            "net_pass_delta": counts["new_only_pass"] - counts["old_only_pass"],
            "empty_to_nonempty_fail": transition_counts["empty_to_nonempty_fail"],
            "nonempty_to_empty_fail": transition_counts["nonempty_to_empty_fail"],
            "avg_score_delta": transition_counts["avg_score_delta"] / max(len(new_rows), 1),
        },
        "by_motif": dict(motif_counts),
        "top_score_changes": improvements[:20],
    }


def compare_minireg(
    bench_root: Path,
    old_result_root: Path,
    new_result_root: Path,
    split: str,
    seed_ids: List[str],
) -> Dict[str, Any]:
    motif_index = build_seed_motif_index(bench_root)
    old_rows = _iter_seed_variant_records(bench_root, old_result_root, split, seed_ids)
    new_rows = _iter_seed_variant_records(bench_root, new_result_root, split, seed_ids)
    return {
        "split": split,
        "seed_ids": seed_ids,
        "old": _summarize(old_rows, motif_index),
        "new": _summarize(new_rows, motif_index),
        "head_to_head": _head_to_head(old_rows, new_rows, motif_index),
        "old_rows": old_rows,
        "new_rows": new_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare old vs new support-plan results on a small regression subset.")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--old_result_root", required=True)
    parser.add_argument("--new_result_root", required=True)
    parser.add_argument("--split", required=True, choices=["l0", "l1", "l2", "l3"])
    parser.add_argument("--seed_ids", required=True, help="Comma-separated seed ids")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    seed_ids = [item.strip() for item in args.seed_ids.split(",") if item.strip()]
    payload = compare_minireg(
        bench_root=Path(args.bench_root),
        old_result_root=Path(args.old_result_root),
        new_result_root=Path(args.new_result_root),
        split=args.split,
        seed_ids=seed_ids,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
