"""Run support_plan_agent on stratified l0/l1/l2 (variant A) and compare to baseline reports."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.run_hdrbench_eval import _load_json, run_eval


def _baseline_seeds(report_path: Path, split: str, variant: str, stride: int) -> list[str]:
    r = _load_json(report_path)
    ids = sorted(
        {str(x["seed_id"]) for x in r["records"] if x.get("split") == split and x.get("variant") == variant}
    )
    return ids[::stride]


def _subset_records(report_path: Path, split: str, variant: str, seed_set: set[str]) -> list[dict]:
    r = _load_json(report_path)
    return [
        x
        for x in r["records"]
        if x.get("split") == split and x.get("variant") == variant and str(x.get("seed_id")) in seed_set
    ]


def _summarize(recs: list[dict]) -> dict[str, Any]:
    n = len(recs)
    passed = sum(1 for x in recs if x.get("pass"))
    stages = Counter((x.get("stage") or "OK") for x in recs)
    return {"n": n, "pass": passed, "rate": round(passed / max(n, 1), 4), "stages": dict(stages)}


def _flips(old_recs: list[dict], new_recs: list[dict]) -> tuple[int, int]:
    bo = {str(x["seed_id"]): bool(x.get("pass")) for x in old_recs}
    bn = {str(x["seed_id"]): bool(x.get("pass")) for x in new_recs}
    fixed = reg = 0
    for sid in bo:
        if sid not in bn:
            continue
        if bo[sid] and not bn[sid]:
            reg += 1
        elif not bo[sid] and bn[sid]:
            fixed += 1
    return fixed, reg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench_root", type=Path, default=ROOT / "outputs/hdrbench_full150_v1")
    parser.add_argument("--baseline_dir", type=Path, default=ROOT / "outputs")
    parser.add_argument("--out_root", type=Path, default=ROOT / "outputs/support_plan_l012_reval")
    parser.add_argument("--stride", type=int, default=3, help="Take every Nth seed from sorted A-list (default 3 ≈ 56/167).")
    parser.add_argument("--variant", default="A")
    parser.add_argument("--access_mode", default="dev")
    parser.add_argument("--splits", default="l0,l1,l2", help="Comma-separated splits to run.")
    args = parser.parse_args()

    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    summary_rows: list[dict[str, Any]] = []

    for split in splits:
        baseline_name = f"full150_support_v3_{split}_ABC"
        baseline_path = args.baseline_dir / baseline_name / "report_support_plan_agent.json"
        if not baseline_path.exists():
            print(f"SKIP {split}: missing baseline {baseline_path}")
            continue

        seeds = _baseline_seeds(baseline_path, split, args.variant, args.stride)
        seed_set = set(seeds)
        out_dir = args.out_root / split
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n=== {split}  stratified n={len(seeds)}  -> {out_dir} ===")
        run_eval(
            bench_root=args.bench_root,
            mode="support_plan_agent",
            out_dir=out_dir,
            split_filter=split,
            view_filter="full",
            access_mode=args.access_mode,
            variant_filter=[args.variant],
            seed_filter=seeds,
        )

        new_report = out_dir / "report_support_plan_agent.json"
        old_recs = _subset_records(baseline_path, split, args.variant, seed_set)
        new_recs = _subset_records(new_report, split, args.variant, seed_set)
        so, sn = _summarize(old_recs), _summarize(new_recs)
        fixed, reg = _flips(old_recs, new_recs)

        row = {
            "split": split,
            "sample_n": len(seeds),
            "baseline": so,
            "current": sn,
            "delta_pass": sn["pass"] - so["pass"],
            "fixed_fail_to_pass": fixed,
            "regressed_pass_to_fail": reg,
        }
        summary_rows.append(row)
        print(json.dumps(row, ensure_ascii=False, indent=2))

    out_summary = args.out_root / "compare_l012_summary.json"
    out_summary.write_text(json.dumps(summary_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out_summary}")


if __name__ == "__main__":
    main()
