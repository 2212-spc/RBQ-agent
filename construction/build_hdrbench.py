from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from construction.phase0_seed_filter import build_seed_registry
from construction.phase1_phase2_builder import VARIANTS, build_universe_a_for_seed
from construction.phase3_friction_builder import build_universe_b_for_variant
from construction.phase4_validators import run_inverse_check, run_perfect_agent_check
from construction.seed_tools import dump_json, load_jsonl


def _safe_name(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in s)


def _write_variant_manifests(seed: Dict[str, Any], seed_dir: Path, variant: str) -> Dict[str, Any]:
    variant_root = seed_dir / "variants" / variant
    ua = variant_root / "universe_a"
    ul0 = variant_root / "universe_l0"
    ub = variant_root / "universe_b"

    dirty_manifest = json.loads((ub / "manifest_dirty.json").read_text(encoding="utf-8"))
    gold_path = ua / "gold.csv"
    gold_df_cols = list(__import__("pandas").read_csv(gold_path).columns)
    split_views = {
        "l0": {"full": str(ul0)},
        **dirty_manifest.get("splits", {}),
    }

    public = {
        "seed_id": seed["seed_id"],
        "variant": variant,
        "instruction": seed["question"],
        "views": dirty_manifest["views"],
        "splits": split_views,
        "deliverable_spec": {
            "format": "csv",
            "required_columns": gold_df_cols,
            "optional_columns": [],
            "order_required": False,
            "float_tolerance": 1e-6,
        },
        "gold_path": str(gold_path),
    }

    private = {
        "seed": seed,
        "variant": variant,
        "gold_sql": seed["gold_sql"],
        "universe_a": str(ua),
        "universe_l0": str(ul0),
        "universe_b": str(ub),
        "splits": split_views,
        **dirty_manifest,
    }

    dump_json(variant_root / "manifest_public.json", public)
    dump_json(variant_root / "manifest_private.json", private)
    return {"public": public, "private": private}


def _write_case_card(seed: Dict[str, Any], seed_dir: Path, variant: str) -> None:
    variant_root = seed_dir / "variants" / variant
    public = json.loads((variant_root / "manifest_public.json").read_text(encoding="utf-8"))
    private = json.loads((variant_root / "manifest_private.json").read_text(encoding="utf-8"))
    inverse = json.loads((variant_root / "inverse_check_report.json").read_text(encoding="utf-8"))
    perfect = json.loads((variant_root / "perfect_agent_report.json").read_text(encoding="utf-8"))

    clean_registry = private["table_registry_clean"]
    dirty_registry = private["table_registry_dirty"]
    value_transforms = private.get("value_transforms", {})

    table_lines = []
    for table, entry in clean_registry.items():
        table_lines.append(
            f"- {table}: {entry['storage_type']} -> {dirty_registry[table]['storage_type']} "
            f"({entry['row_count']} rows)"
        )

    lines = [
        f"# Case {seed['seed_id']} / Variant {variant}",
        "",
        "## Question",
        seed["question"],
        "",
        "## Gold SQL",
        "```sql",
        seed["gold_sql"],
        "```",
        "",
        "## Workspace",
        f"- L0 full: `{public['splits']['l0']['full']}`",
        f"- L1 full: `{public['splits']['l1']['full']}`",
        f"- L2 full: `{public['splits']['l2']['full']}`",
        f"- L3 full: `{public['splits']['l3']['full']}`",
        f"- L3 oracle: `{public['splits']['l3']['oracle']}`",
        f"- L3 trimmed: `{public['splits']['l3']['trimmed']}`",
        f"- Required columns: {', '.join(public['deliverable_spec']['required_columns'])}",
        "",
        "## Tables",
        *table_lines,
        "",
        "## Friction Summary",
        f"- Gold files: {len(private['gold_files_dirty'])}",
        f"- Distractors: {len(private['distractors'])}",
        f"- Key-column renames: {len(seed.get('key_columns', []))}",
        f"- Value transforms: {len(value_transforms)}",
        "",
        "## Validation",
        f"- inverse_check: {'PASS' if inverse.get('inverse_pass') else 'FAIL'}",
        f"- perfect_agent: {'PASS' if perfect.get('perfect_agent_pass') else 'FAIL'}",
        "",
    ]
    (variant_root / "case_card.md").write_text("\n".join(lines), encoding="utf-8")


def build_hdrbench(
    seed_registry: Path,
    out_root: Path,
    random_seed: int,
    max_seeds: int,
    distractor_min: int,
    distractor_max: int,
    trimmed_ratio: float,
    nonkey_rename_prob: float,
    l3_apply_prob: float,
    min_gold_rows: int,
) -> Dict[str, Any]:
    rng = random.Random(random_seed)
    seeds = load_jsonl(seed_registry)

    out_root.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "seed_registry": str(seed_registry),
        "out_root": str(out_root),
        "requested_seeds": max_seeds,
        "built_seeds": 0,
        "failed_seeds": 0,
        "seeds": [],
        "failures": [],
    }

    target = max_seeds
    built_success = 0
    for idx, seed in enumerate(seeds):
        if built_success >= target:
            break
        seed_id = _safe_name(seed["seed_id"])
        seed_dir = out_root / seed_id
        if seed_dir.exists():
            shutil.rmtree(seed_dir)
        seed_dir.mkdir(parents=True, exist_ok=True)

        try:
            ua_summary = build_universe_a_for_seed(
                seed=seed,
                out_seed_dir=seed_dir,
                random_seed=random_seed + idx * 71,
                min_gold_rows=min_gold_rows,
            )

            variant_reports: Dict[str, Any] = {}
            all_variants_ok = True
            for vid in VARIANTS:
                vroot = seed_dir / "variants" / vid
                _dirty = build_universe_b_for_variant(
                    seed=seed,
                    variant_id=vid,
                    variant_root=vroot,
                    random_seed=random_seed + idx * 997 + ord(vid),
                    nonkey_rename_prob=nonkey_rename_prob,
                    l3_apply_prob=l3_apply_prob,
                    distractor_min=distractor_min,
                    distractor_max=distractor_max,
                    trimmed_ratio=trimmed_ratio,
                )

                inv_report = run_inverse_check(seed=seed, variant_root=vroot)
                pa_report = run_perfect_agent_check(seed=seed, variant_root=vroot)
                _m = _write_variant_manifests(seed, seed_dir, vid)
                _write_case_card(seed, seed_dir, vid)

                ok = bool(inv_report.get("inverse_pass")) and bool(pa_report.get("perfect_agent_pass"))
                all_variants_ok = all_variants_ok and ok
                variant_reports[vid] = {
                    "inverse": inv_report,
                    "perfect_agent": pa_report,
                    "passed": ok,
                }

            seed_report = {
                "seed_id": seed["seed_id"],
                "db_id": seed["db_id"],
                "universe_a": ua_summary,
                "variants": variant_reports,
                "seed_passed": all_variants_ok,
            }
            dump_json(seed_dir / "seed_report.json", seed_report)

            summary["seeds"].append({
                "seed_id": seed["seed_id"],
                "db_id": seed["db_id"],
                "seed_passed": all_variants_ok,
            })
            summary["built_seeds"] += 1
            if all_variants_ok:
                built_success += 1

        except Exception as exc:  # noqa: BLE001
            if seed_dir.exists():
                shutil.rmtree(seed_dir)
            summary["failed_seeds"] += 1
            summary["failures"].append({"seed_id": seed["seed_id"], "error": str(exc)})

    dump_json(out_root / "build_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build complete-protocol HDR-Bench mini")
    parser.add_argument("--seed_registry", default="", help="Path to phase0 seed_registry.jsonl")
    parser.add_argument("--spider_json", default="", help="If seed_registry missing, build it from Spider json")
    parser.add_argument("--db_root", default="", help="Spider database root")
    parser.add_argument("--out", required=True, help="Output root, e.g. outputs/hdrbench_v01")
    parser.add_argument("--max_seeds", type=int, default=12)
    parser.add_argument("--per_db_limit", type=int, default=3)
    parser.add_argument("--random_seed", type=int, default=13)
    parser.add_argument("--distractor_min", type=int, default=3)
    parser.add_argument("--distractor_max", type=int, default=5)
    parser.add_argument("--trimmed_ratio", type=float, default=0.5)
    parser.add_argument("--nonkey_rename_prob", type=float, default=0.7)
    parser.add_argument("--l3_apply_prob", type=float, default=0.6)
    parser.add_argument("--min_gold_rows", type=int, default=1)
    args = parser.parse_args()

    out_root = Path(args.out)

    if args.seed_registry:
        seed_registry = Path(args.seed_registry)
    else:
        if not args.spider_json or not args.db_root:
            raise SystemExit("Provide --seed_registry OR both --spider_json and --db_root")
        seed_registry = out_root / "seed_registry.jsonl"
        build_seed_registry(
            spider_json=Path(args.spider_json),
            db_root=Path(args.db_root),
            out_registry=seed_registry,
            max_seeds=int(args.max_seeds),
            per_db_limit=int(args.per_db_limit),
            random_seed=int(args.random_seed),
        )

    summary = build_hdrbench(
        seed_registry=seed_registry,
        out_root=out_root,
        random_seed=int(args.random_seed),
        max_seeds=int(args.max_seeds),
        distractor_min=int(args.distractor_min),
        distractor_max=int(args.distractor_max),
        trimmed_ratio=float(args.trimmed_ratio),
        nonkey_rename_prob=float(args.nonkey_rename_prob),
        l3_apply_prob=float(args.l3_apply_prob),
        min_gold_rows=int(args.min_gold_rows),
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
