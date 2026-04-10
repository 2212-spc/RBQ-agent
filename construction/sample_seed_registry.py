from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _dump_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_seed_ids(path: Path) -> set[str]:
    rows = _load_jsonl(path)
    return {str(row["seed_id"]) for row in rows}


def sample_round_robin(rows: List[Dict[str, Any]], target_n: int) -> List[Dict[str, Any]]:
    by_db: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_db[str(row["db_id"])].append(row)

    ordered_dbs = sorted(by_db)
    selected: List[Dict[str, Any]] = []
    rank = 0
    while len(selected) < target_n:
        progressed = False
        for db_id in ordered_dbs:
            bucket = by_db[db_id]
            if rank < len(bucket):
                selected.append(bucket[rank])
                progressed = True
                if len(selected) >= target_n:
                    break
        if not progressed:
            break
        rank += 1
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample a balanced seed registry using round-robin over db_id buckets.")
    parser.add_argument("--in_registry", required=True)
    parser.add_argument("--out_registry", required=True)
    parser.add_argument("--target_n", type=int, required=True)
    parser.add_argument("--exclude_registry", default="", help="Optional registry whose seed_ids should be excluded before sampling")
    args = parser.parse_args()

    rows = _load_jsonl(Path(args.in_registry))
    if args.exclude_registry:
        excluded = _load_seed_ids(Path(args.exclude_registry))
        rows = [row for row in rows if str(row["seed_id"]) not in excluded]
    sampled = sample_round_robin(rows, int(args.target_n))
    _dump_jsonl(Path(args.out_registry), sampled)

    db_ids = {row["db_id"] for row in sampled}
    summary = {
        "in_registry": args.in_registry,
        "out_registry": args.out_registry,
        "requested_n": int(args.target_n),
        "sampled_n": len(sampled),
        "num_unique_dbs": len(db_ids),
        "sampling_strategy": "round_robin_by_db",
        "exclude_registry": args.exclude_registry or None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
