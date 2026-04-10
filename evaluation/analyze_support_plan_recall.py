from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.motif_taxonomy import build_seed_motif_index, summarize_seed_motifs
from evaluation.run_hdrbench_eval import _list_seed_dirs, _load_json
from evaluation.support_plan_agent.probes import audit_case_recall, prepare_case_context


def _aggregate_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"seed_count": 0}

    output_slot_total = sum(int(row.get("output_slot_total", 0)) for row in rows)
    filter_total = sum(int(row.get("filter_total", 0)) for row in rows)
    evidence_total = sum(int(row.get("evidence_total", 0)) for row in rows)
    join_path_total = sum(int(row.get("join_path_total", 0)) for row in rows)
    case_count = len(rows)

    metrics: Dict[str, Any] = {
        "seed_count": case_count,
        "output_slot_total": output_slot_total,
        "filter_total": filter_total,
        "evidence_total": evidence_total,
        "join_path_total": join_path_total,
        "ambiguous_count_star_cases": sum(int(bool(row.get("ambiguous_count_star"))) for row in rows),
    }
    for metric_name in rows[0]:
        if metric_name.endswith(("_recall_at_1", "_recall_at_3", "_recall_at_4", "_recall_at_6", "_reachable_at_2", "_reachable_at_3")):
            metrics[metric_name] = sum(float(row.get(metric_name, 0.0)) for row in rows) / case_count
    return metrics


def _group_summary(rows: List[Dict[str, Any]], group_keys: Iterable[str]) -> Dict[str, Any]:
    buckets: Dict[Tuple[str, ...], List[Dict[str, Any]]] = defaultdict(list)
    keys = list(group_keys)
    for row in rows:
        bucket_key = tuple(str(row.get(key, "")) for key in keys)
        buckets[bucket_key].append(row)
    summary: Dict[str, Any] = {}
    for bucket_key, bucket_rows in sorted(buckets.items()):
        label = " | ".join(bucket_key)
        summary[label] = {
            **{key: value for key, value in zip(keys, bucket_key)},
            **_aggregate_rows(bucket_rows),
        }
    return summary


def analyze_recall(
    bench_root: Path,
    *,
    variant: str = "A",
    splits: List[str] | None = None,
    sketch_mode: str = "fallback",
) -> Dict[str, Any]:
    split_names = splits or ["l0", "l1", "l2"]
    rows: List[Dict[str, Any]] = []
    seed_motifs = build_seed_motif_index(bench_root)

    for seed_dir in _list_seed_dirs(bench_root):
        pub_path = seed_dir / "variants" / variant / "manifest_public.json"
        pri_path = seed_dir / "variants" / variant / "manifest_private.json"
        if not pub_path.exists() or not pri_path.exists():
            continue
        pub = _load_json(pub_path)
        pri = _load_json(pri_path)
        for split in split_names:
            if split not in pub.get("splits", {}):
                continue
            context = prepare_case_context(pub, pri, split=split, view="full", sketch_mode=sketch_mode, namespace=f"support_plan_recall_{split}")
            row = audit_case_recall(context)
            row["motif"] = seed_motifs[context.seed_id]["base_label"]
            rows.append(row)

    return {
        "bench_root": str(bench_root),
        "variant": variant,
        "splits": split_names,
        "sketch_mode": sketch_mode,
        "seed_motif_taxonomy": summarize_seed_motifs(seed_motifs),
        "overall_summary": _aggregate_rows(rows),
        "summary_by_split": _group_summary(rows, ["split"]),
        "summary_by_split_motif": _group_summary(rows, ["split", "motif"]),
        "summary_by_split_filter_kind": _group_summary(rows, ["split", "filter_kind"]),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline recall audit for support-plan candidate generation.")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--variant", default="A")
    parser.add_argument("--splits", default="l0,l1,l2", help="Comma-separated split list, default l0,l1,l2")
    parser.add_argument("--sketch_mode", default="fallback", choices=["fallback", "live"])
    parser.add_argument("--out_dir", required=True)
    args = parser.parse_args()

    split_names = [item.strip() for item in args.splits.split(",") if item.strip()]
    payload = analyze_recall(
        bench_root=Path(args.bench_root),
        variant=args.variant,
        splits=split_names,
        sketch_mode=args.sketch_mode,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "support_plan_recall_summary.json"
    csv_path = out_dir / "support_plan_recall_rows.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(payload["rows"]).to_csv(csv_path, index=False)
    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "seed_count": payload["overall_summary"]["seed_count"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
