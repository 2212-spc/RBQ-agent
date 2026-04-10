from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from construction.build_hdrbench import build_hdrbench
from construction.phase0_seed_filter import build_seed_registry


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _dump_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _built_seed_ids(out_root: Path) -> set[str]:
    built: set[str] = set()
    if not out_root.exists():
        return built
    for child in out_root.iterdir():
        if child.is_dir() and (child / "seed_report.json").exists():
            built.add(child.name)
    return built


def _chunks(rows: List[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
    return [rows[i : i + chunk_size] for i in range(0, len(rows), chunk_size)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a large HDR-Bench root using the original Phase0-4 pipeline.")
    parser.add_argument("--out", required=True, help="Target benchmark root, e.g. outputs/hdrbench_full_v1")
    parser.add_argument("--seed_registry", default="", help="Optional existing seed registry jsonl")
    parser.add_argument("--spider_json", default="", help="Spider train/dev json used when seed_registry is omitted")
    parser.add_argument("--db_root", default="", help="Spider database root used when seed_registry is omitted")
    parser.add_argument("--max_seeds", type=int, default=5000)
    parser.add_argument("--per_db_limit", type=int, default=999)
    parser.add_argument("--chunk_size", type=int, default=100)
    parser.add_argument("--resume", action="store_true", help="Skip seeds already built in --out")
    parser.add_argument("--random_seed", type=int, default=13)
    parser.add_argument("--distractor_min", type=int, default=3)
    parser.add_argument("--distractor_max", type=int, default=5)
    parser.add_argument("--trimmed_ratio", type=float, default=0.5)
    parser.add_argument("--nonkey_rename_prob", type=float, default=0.7)
    parser.add_argument("--l3_apply_prob", type=float, default=0.6)
    parser.add_argument("--min_gold_rows", type=int, default=1)
    args = parser.parse_args()

    out_root = Path(args.out)
    build_root = out_root / "_build"
    build_root.mkdir(parents=True, exist_ok=True)

    if args.seed_registry:
        registry_path = Path(args.seed_registry)
    else:
        if not args.spider_json or not args.db_root:
            raise SystemExit("Provide --seed_registry OR both --spider_json and --db_root.")
        registry_path = build_root / "full_seed_registry.jsonl"
        build_seed_registry(
            spider_json=Path(args.spider_json),
            db_root=Path(args.db_root),
            out_registry=registry_path,
            max_seeds=int(args.max_seeds),
            per_db_limit=int(args.per_db_limit),
            random_seed=int(args.random_seed),
        )

    registry_rows = _load_jsonl(registry_path)
    if int(args.max_seeds) > 0:
        registry_rows = registry_rows[: int(args.max_seeds)]
    if args.resume:
        built = _built_seed_ids(out_root)
        registry_rows = [row for row in registry_rows if row["seed_id"] not in built]
    total_requested = len(registry_rows)

    registries_dir = build_root / "registries"
    summaries_dir = build_root / "chunk_summaries"
    registries_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    chunks = _chunks(registry_rows, int(args.chunk_size))
    chunk_summaries: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        chunk_name = f"chunk_{idx:03d}"
        chunk_registry = registries_dir / f"{chunk_name}.jsonl"
        _dump_jsonl(chunk_registry, chunk)
        summary = build_hdrbench(
            seed_registry=chunk_registry,
            out_root=out_root,
            random_seed=int(args.random_seed) + idx * 1009,
            max_seeds=len(chunk),
            distractor_min=int(args.distractor_min),
            distractor_max=int(args.distractor_max),
            trimmed_ratio=float(args.trimmed_ratio),
            nonkey_rename_prob=float(args.nonkey_rename_prob),
            l3_apply_prob=float(args.l3_apply_prob),
            min_gold_rows=int(args.min_gold_rows),
        )
        summary["chunk_name"] = chunk_name
        summary["chunk_registry"] = str(chunk_registry)
        _dump_json(summaries_dir / f"{chunk_name}.summary.json", summary)
        chunk_summaries.append(summary)

    aggregate = {
        "out_root": str(out_root),
        "seed_registry": str(registry_path),
        "resume": bool(args.resume),
        "total_requested_after_resume_filter": total_requested,
        "chunk_size": int(args.chunk_size),
        "num_chunks": len(chunks),
        "chunk_summaries": [
            {
                "chunk_name": item["chunk_name"],
                "built_seeds": item.get("built_seeds", 0),
                "failed_seeds": item.get("failed_seeds", 0),
            }
            for item in chunk_summaries
        ],
        "final_built_seed_dirs": len(_built_seed_ids(out_root)),
    }
    _dump_json(build_root / "full_build_summary.json", aggregate)
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
