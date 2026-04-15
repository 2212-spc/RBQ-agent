from __future__ import annotations

import argparse
import ctypes
import gc
import json
from pathlib import Path
from typing import Any, Dict, Tuple

from scorer import score_single

ORDER: list[Tuple[str, str, str]] = [
    ("l0", "full", "L0"),
    ("l1", "full", "L1"),
    ("l2", "full", "L2"),
    ("l3", "full", "L3-F"),
    ("l3", "oracle", "L3-O"),
    ("l3", "trimmed", "L3-T"),
]

try:
    _LIBC = ctypes.CDLL("libc.so.6")
except OSError:
    _LIBC = None


def _manifest_payload(bench_root: Path, seed_id: str, variant: str) -> Tuple[Dict[str, Any], Path]:
    manifest = bench_root / seed_id / "variants" / variant / "manifest_public.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    spec = payload["deliverable_spec"]
    gold_rel = payload["gold_path"].replace("\\", "/")
    if gold_rel.startswith("outputs/"):
        gold_path = bench_root.parent.parent / gold_rel
    else:
        gold_path = bench_root / gold_rel
    return spec, gold_path


def _iter_csvs(out_dir: Path):
    for result_path in out_dir.rglob("*.csv"):
        rel = result_path.relative_to(out_dir)
        if len(rel.parts) != 4:
            continue
        seed_id, variant, split, fname = rel.parts
        view = fname[:-4]
        yield result_path, seed_id, variant, split, view


def aggregate_completed_only(
    bench_root: Path,
    out_dir: Path,
    split_filter: str = "all",
    view_filter: str = "all",
) -> Dict[str, Any]:
    counts = {(split, view): {"passed": 0, "total": 0} for split, view, _ in ORDER}
    cache: Dict[Tuple[str, str], Tuple[Dict[str, Any], Path]] = {}

    processed = 0
    for result_path, seed_id, variant, split, view in _iter_csvs(out_dir):
        if split_filter != "all" and split != split_filter:
            continue
        if view_filter != "all" and view != view_filter:
            continue
        key = (split, view)
        if key not in counts:
            continue
        manifest_key = (seed_id, variant)
        if manifest_key not in cache:
            cache[manifest_key] = _manifest_payload(bench_root, seed_id, variant)
        spec, gold_path = cache[manifest_key]
        score = score_single(result_path=result_path, gold_path=gold_path, spec=spec)
        counts[key]["total"] += 1
        counts[key]["passed"] += int(bool(score.get("pass", False)))
        del score
        processed += 1
        if processed % 25 == 0:
            gc.collect()
            if _LIBC is not None:
                try:
                    _LIBC.malloc_trim(0)
                except Exception:
                    pass

    pass_rate_by_setting: Dict[str, float] = {}
    pass_count_by_setting: Dict[str, Dict[str, int]] = {}
    for split, view, _ in ORDER:
        stats = counts[(split, view)]
        total = stats["total"]
        passed = stats["passed"]
        setting = f"{split}.{view}"
        pass_rate_by_setting[setting] = (passed / total) if total else 0.0
        pass_count_by_setting[setting] = {"passed": passed, "total": total}

    report = {
        "aggregation": "completed_only",
        "bench_root": str(bench_root),
        "out_dir": str(out_dir),
        "num_records": sum(v["total"] for v in counts.values()),
        "pass_rate_by_setting": pass_rate_by_setting,
        "pass_count_by_setting": pass_count_by_setting,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate completed-only pass rates for an eval output directory.")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--split", default="all", choices=["all", "l0", "l1", "l2", "l3"])
    parser.add_argument("--view", default="all", choices=["all", "full", "oracle", "trimmed"])
    parser.add_argument("--write_json", default="", help="Optional output json path")
    args = parser.parse_args()

    report = aggregate_completed_only(
        bench_root=Path(args.bench_root),
        out_dir=Path(args.out),
        split_filter=args.split,
        view_filter=args.view,
    )
    if args.write_json:
        out_path = Path(args.write_json)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    rates = report["pass_rate_by_setting"]
    counts = report["pass_count_by_setting"]
    rate_values = []
    for split, view, label in ORDER:
        setting = f"{split}.{view}"
        rate = rates[setting] * 100.0
        passed = counts[setting]["passed"]
        total = counts[setting]["total"]
        rate_values.append(rate)
        print(f"{label}={rate:.2f} ({passed}/{total})")
    print(f"AVG={sum(rate_values)/len(rate_values):.2f}")


if __name__ == "__main__":
    main()
