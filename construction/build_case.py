from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from construction.distractor_gen import generate_distractors
from construction.exploder import explode_seed
from construction.friction_L1L2 import apply_l1_l2_friction
from construction.perfect_agent import run_perfect_agent
from construction.seed_tools import dump_json, load_jsonl, parse_sql_metadata
from construction.sql_rewrite import write_gold_artifact


def _safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", s)


def _copy_selected(src_dir: Path, dst_dir: Path, keep_files: set[str]) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for fp in src_dir.iterdir():
        if fp.is_file() and fp.name in keep_files:
            shutil.copy2(fp, dst_dir / fp.name)


def _write_case_card(case_dir: Path, payload: Dict[str, Any]) -> None:
    md = []
    md.append(f"# Case: {payload['seed_id']}")
    md.append("")
    md.append("## Question")
    md.append(payload["question"])
    md.append("")
    md.append("## Gold SQL")
    md.append("```sql")
    md.append(payload["gold_sql"])
    md.append("```")
    md.append("")
    md.append("## Workspace summary")
    md.append(f"- gold files: {payload['num_gold_files']}")
    md.append(f"- distractors: {payload['num_distractors']}")
    md.append("- views: full/oracle/trimmed")
    md.append("")
    md.append("## Friction summary")
    md.append(f"- L1 file renames: {payload['l1_count']}")
    md.append(f"- L2 column renames: {payload['l2_col_rename_count']}")
    md.append(f"- dummy cols added: {payload['l2_dummy_count']}")
    md.append("")
    md.append("## Proof of solvability")
    md.append(f"- perfect_agent: {'PASS' if payload['perfect_pass'] else 'FAIL'}")
    md.append("- perfect SQL path: perfect_agent.sql")
    md.append("")
    md.append("## Quick baseline demo")
    md.append("- baseline: direct_sql_agent (to be run via evaluation/run_demo.py)")

    (case_dir / "case_card.md").write_text("\n".join(md), encoding="utf-8")


def build_one_case(
    seed: Dict[str, Any],
    out_dir: Path,
    cfg: Dict[str, Any],
    distractors_n: int,
    trimmed_k: int,
    random_seed: int,
) -> Dict[str, Any]:
    seed_id = _safe_name(seed["seed_id"])
    case_dir = out_dir / seed_id

    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)

    clean_dir = case_dir / "clean"
    dirty_full = case_dir / "dirty_full"
    dirty_oracle = case_dir / "dirty_oracle"
    dirty_trimmed = case_dir / "dirty_trimmed"

    sql_meta = parse_sql_metadata(seed["gold_sql"])
    if len(sql_meta.get("tables", [])) < 2:
        raise ValueError(f"Seed {seed['seed_id']} skipped: requires >=2 tables.")
    if len(sql_meta.get("joins", [])) < 1:
        raise ValueError(f"Seed {seed['seed_id']} skipped: requires >=1 join.")

    explosion_log = explode_seed(seed=seed, sql_meta=sql_meta, clean_dir=clean_dir)

    gold_csv_path = case_dir / "gold.csv"
    rewritten_sql_path = case_dir / "gold_rewritten.sql"
    gold_df, _ = write_gold_artifact(
        gold_sql=seed["gold_sql"],
        table_registry=explosion_log["table_registry"],
        workspace_dir=clean_dir,
        output_csv=gold_csv_path,
        output_sql=rewritten_sql_path,
    )

    friction = apply_l1_l2_friction(
        clean_dir=clean_dir,
        dirty_full_dir=dirty_full,
        explosion_log=explosion_log,
        rename_ratio=float(cfg.get("rename_ratio", 0.7)),
        join_key_rename_ratio=float(cfg.get("join_key_rename_ratio", 1.0)),
        dummy_cols_min=int(cfg.get("dummy_cols_min", 1)),
        dummy_cols_max=int(cfg.get("dummy_cols_max", 3)),
        random_seed=random_seed,
    )

    distractors = generate_distractors(
        seed=seed,
        used_tables=sql_meta["tables"],
        out_dir=dirty_full,
        num_distractors=distractors_n,
        random_seed=random_seed + 97,
    )

    gold_files = set(friction["gold_files_dirty"])
    distractor_files = [d["file"] for d in distractors]

    _copy_selected(dirty_full, dirty_oracle, keep_files=gold_files)

    trimmed_keep = set(gold_files)
    trimmed_keep.update(distractor_files[:trimmed_k])
    _copy_selected(dirty_full, dirty_trimmed, keep_files=trimmed_keep)

    deliverable_spec = {
        "format": "csv",
        "required_columns": list(gold_df.columns),
        "optional_columns": [],
        "order_required": False,
        "float_tolerance": 1e-6,
    }

    manifest_public = {
        "seed_id": seed["seed_id"],
        "instruction": seed["question"],
        "views": {
            "full": str(dirty_full),
            "oracle": str(dirty_oracle),
            "trimmed": str(dirty_trimmed),
        },
        "deliverable_spec": deliverable_spec,
        "gold_path": str(gold_csv_path),
    }

    manifest_private = {
        "seed_id": seed["seed_id"],
        "db_id": seed["db_id"],
        "db_path": seed["db_path"],
        "question": seed["question"],
        "gold_sql": seed["gold_sql"],
        "explosion_log": explosion_log,
        "table_registry_dirty": friction["table_registry_dirty"],
        "file_mapping": friction["file_mapping"],
        "column_mapping": friction["column_mapping"],
        "column_mapping_by_table": friction["column_mapping_by_table"],
        "friction_trace": friction["friction_trace"],
        "distractors": distractors,
    }

    dump_json(case_dir / "manifest_public.json", manifest_public)
    dump_json(case_dir / "manifest_private.json", manifest_private)

    perfect_report = run_perfect_agent(case_dir=case_dir, manifest_private=manifest_private)
    manifest_private["perfect_agent"] = perfect_report
    dump_json(case_dir / "manifest_private.json", manifest_private)

    l1_count = sum(1 for x in friction["friction_trace"] if x["level"] == "L1")
    l2_col_rename_count = sum(
        1 for x in friction["friction_trace"] if x["level"] == "L2" and x["type"] == "col_rename"
    )
    l2_dummy_count = sum(
        1 for x in friction["friction_trace"] if x["level"] == "L2" and x["type"] == "col_add_dummy"
    )

    _write_case_card(
        case_dir,
        {
            "seed_id": seed["seed_id"],
            "question": seed["question"],
            "gold_sql": seed["gold_sql"],
            "num_gold_files": len(gold_files),
            "num_distractors": len(distractors),
            "l1_count": l1_count,
            "l2_col_rename_count": l2_col_rename_count,
            "l2_dummy_count": l2_dummy_count,
            "perfect_pass": perfect_report["perfect_agent_pass"],
        },
    )

    return {
        "seed_id": seed["seed_id"],
        "case_dir": str(case_dir),
        "perfect_pass": bool(perfect_report["perfect_agent_pass"]),
        "num_distractors": len(distractors),
        "num_gold_files": len(gold_files),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build HDR-Bench MVP cases.")
    parser.add_argument("--seeds", required=True, help="Path to seed_mvp.jsonl")
    parser.add_argument("--out", required=True, help="Output cases root directory")
    parser.add_argument("--n", type=int, default=3, help="Number of cases to build")
    parser.add_argument("--difficulty", default="L2", choices=["L1", "L2"], help="MVP supports L1/L2")
    parser.add_argument("--distractors", type=int, default=10)
    parser.add_argument("--trimmed_k", type=int, default=3)
    parser.add_argument("--random_seed", type=int, default=13)
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "config.yaml"),
        help="Path to config.yaml",
    )
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}

    seeds = load_jsonl(args.seeds)
    rng = random.Random(args.random_seed)
    if len(seeds) > args.n:
        seeds = rng.sample(seeds, args.n)

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []

    for i, seed in enumerate(seeds):
        try:
            case_result = build_one_case(
                seed=seed,
                out_dir=out_root,
                cfg=cfg,
                distractors_n=args.distractors,
                trimmed_k=args.trimmed_k,
                random_seed=args.random_seed + i * 101,
            )
            results.append(case_result)
            print(f"[OK] {seed['seed_id']} -> {case_result['case_dir']}")
        except Exception as exc:  # noqa: BLE001
            failures.append({"seed_id": seed.get("seed_id", f"idx_{i}"), "error": str(exc)})
            print(f"[FAIL] {seed.get('seed_id', i)}: {exc}")

    summary = {
        "requested": args.n,
        "built": len(results),
        "failed": len(failures),
        "results": results,
        "failures": failures,
    }

    summary_path = out_root / "build_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Summary saved: {summary_path}")


if __name__ == "__main__":
    main()
