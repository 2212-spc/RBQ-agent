from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.scorer import score_single
from evaluation.attribution import attribute_failure
from construction.sql_rewrite import build_duckdb_script, execute_duckdb_script


VARIANTS = ["A", "B", "C"]
SUPPORTED_MODES = {
    "naive_sql",
    "perfect_sql",
    "duckdb_agent",
    "hdrbench_agent",
    "llm_code_agent",
    "support_plan_agent",
    "support_plan_no_obligation",
    "contrastive_agent",
    "retrieval_llm_agent",
}
SPLIT_VIEW_OPTIONS = {
    "l0": ["full"],
    "l1": ["full"],
    "l2": ["full"],
    "l3": ["full", "oracle", "trimmed"],
}


def _canonical_mode(mode: str) -> str:
    if mode in {"contrastive_agent", "retrieval_llm_agent", "support_plan_no_obligation"}:
        return "support_plan_agent"
    return mode


def _agent_variant(mode: str) -> str:
    if mode == "support_plan_no_obligation":
        return "no_obligation"
    return "default"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item") and callable(value.item):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    return value


def _list_seed_dirs(bench_root: Path, seed_filter: set[str] | None = None) -> List[Path]:
    seed_dirs = sorted([p for p in bench_root.iterdir() if p.is_dir() and (p / "seed_report.json").exists()])
    if seed_filter:
        seed_dirs = [p for p in seed_dirs if p.name in seed_filter]
    return seed_dirs


def _register_workspace(conn: duckdb.DuckDBPyConnection, workspace: Path) -> List[str]:
    touched: List[str] = []
    for fp in workspace.iterdir():
        if not fp.is_file():
            continue
        touched.append(fp.name)
        ext = fp.suffix.lower()
        uri = str(fp).replace("\\", "/")
        if ext == ".csv":
            conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{fp.stem}\" AS SELECT * FROM read_csv_auto('{uri}')")
        elif ext == ".parquet":
            conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{fp.stem}\" AS SELECT * FROM read_parquet('{uri}')")
        elif ext == ".sqlite":
            sconn = sqlite3.connect(str(fp))
            try:
                tables = [
                    r[0]
                    for r in sconn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    ).fetchall()
                ]
            finally:
                sconn.close()
            for t in tables:
                conn.execute(f"CREATE OR REPLACE TEMP VIEW \"{t}\" AS SELECT * FROM sqlite_scan('{uri}', '{t}')")
    return touched


def _resolve_workspace(manifest_public: Dict[str, Any], split: str, view: str) -> Path:
    split_views = manifest_public.get("splits", {})
    if split in split_views and view in split_views[split]:
        return Path(split_views[split][view])
    if split == "l3" and view in manifest_public.get("views", {}):
        return Path(manifest_public["views"][view])
    raise KeyError(f"Workspace not found for split={split}, view={view}")


def _iter_selected_settings(manifest_public: Dict[str, Any], split_filter: str, view_filter: str) -> List[Tuple[str, str]]:
    split_views = manifest_public.get("splits", {})
    if not split_views:
        split_views = {"l3": manifest_public.get("views", {})}

    selected: List[Tuple[str, str]] = []
    split_names = list(split_views) if split_filter == "all" else [split_filter]
    for split in split_names:
        available_views = list(split_views.get(split, {}))
        if not available_views and split == "l3":
            available_views = list(manifest_public.get("views", {}))
        view_names = available_views if view_filter == "all" else [view_filter]
        for view in view_names:
            if view in available_views:
                selected.append((split, view))
    return selected


def _run_agent_once(
    mode: str,
    manifest_public: Dict[str, Any],
    manifest_private: Dict[str, Any],
    split: str,
    view: str,
    out_csv: Path,
    access_mode: str,
) -> Dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")
    canonical_mode = _canonical_mode(mode)

    workspace = _resolve_workspace(manifest_public, split, view)
    gold_sql = manifest_private["gold_sql"] if (access_mode == "dev" or canonical_mode == "perfect_sql") else None
    touched: List[str] = []

    if canonical_mode == "duckdb_agent":
        from evaluation.duckdb_agent import run_duckdb_agent

        meta = run_duckdb_agent(
            instruction=manifest_public.get("instruction", ""),
            workspace=workspace,
            gold_sql=gold_sql,
            output_csv=out_csv,
        )
        meta["split"] = split
        meta["view"] = view
        meta["requested_mode"] = mode
        meta["agent_impl"] = meta.get("agent_impl", canonical_mode)
        if not meta.get("success"):
            req = manifest_public["deliverable_spec"].get("required_columns", [])
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=req).to_csv(out_csv, index=False)
        return meta

    if canonical_mode == "hdrbench_agent":
        from evaluation.hdrbench_agent import run_hdrbench_agent

        meta = run_hdrbench_agent(
            instruction=manifest_public.get("instruction", ""),
            workspace=workspace,
            gold_sql=gold_sql,
            output_csv=out_csv,
        )
        meta["split"] = split
        meta["view"] = view
        meta["requested_mode"] = mode
        meta["agent_impl"] = meta.get("agent_impl", canonical_mode)
        if not meta.get("success"):
            req = manifest_public["deliverable_spec"].get("required_columns", [])
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=req).to_csv(out_csv, index=False)
        return meta

    if canonical_mode == "llm_code_agent":
        from evaluation.llm_code_agent import run_llm_code_agent

        meta = run_llm_code_agent(
            instruction=manifest_public.get("instruction", ""),
            workspace=workspace,
            deliverable_spec=manifest_public.get("deliverable_spec", {}),
            output_csv=out_csv,
        )
        meta["split"] = split
        meta["view"] = view
        meta["requested_mode"] = mode
        meta["agent_impl"] = meta.get("agent_impl", canonical_mode)
        if not meta.get("success"):
            req = manifest_public["deliverable_spec"].get("required_columns", [])
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=req).to_csv(out_csv, index=False)
        return meta

    if canonical_mode == "support_plan_agent":
        from evaluation.support_plan_agent import run_support_plan_agent

        meta = run_support_plan_agent(
            instruction=manifest_public.get("instruction", ""),
            workspace=workspace,
            deliverable_spec=manifest_public.get("deliverable_spec", {}),
            output_csv=out_csv,
            obligation_mode="off" if mode == "support_plan_no_obligation" else "full",
        )
        meta["split"] = split
        meta["view"] = view
        if not meta.get("success"):
            req = manifest_public["deliverable_spec"].get("required_columns", [])
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=req).to_csv(out_csv, index=False)
        meta["requested_mode"] = mode
        meta["agent_impl"] = meta.get("agent_impl", canonical_mode)
        if mode in {"contrastive_agent", "retrieval_llm_agent"}:
            meta["deprecated_alias"] = True
        return meta

    if canonical_mode == "naive_sql" and gold_sql is None:
        req = manifest_public["deliverable_spec"].get("required_columns", [])
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=req).to_csv(out_csv, index=False)
        return {"success": False, "files_touched": [], "error": "gold_sql unavailable in public mode", "split": split, "view": view}

    conn = duckdb.connect(database=":memory:")
    try:
        if canonical_mode == "naive_sql":
            conn.execute("INSTALL sqlite;")
            conn.execute("LOAD sqlite;")
            touched = _register_workspace(conn, workspace)
            # no mapping/inverse, directly execute original query on messy workspace
            df = conn.execute(gold_sql).fetchdf()
        else:
            if split == "l0":
                l0_manifest = _load_json(workspace / "manifest_l0.json")
                table_registry = l0_manifest["table_registry"]
                sql_script = build_duckdb_script(gold_sql=manifest_private["gold_sql"], table_registry=table_registry, workspace_dir=workspace)
            else:
                split_registry = manifest_private.get("table_registry_by_split", {}).get(split, manifest_private.get("table_registry_dirty", {}))
                split_col_map = manifest_private.get("column_mapping_by_split", {}).get(split, manifest_private.get("column_mapping_by_table", {}))
                split_value_transforms = manifest_private.get("value_transforms_by_split", {}).get(split, {})
                inverse_sql_by_table: Dict[str, Dict[str, str]] = {}
                for fq, spec in split_value_transforms.items():
                    table, col = fq.split(".", 1)
                    inverse_sql_by_table.setdefault(table, {})[col] = spec.get("inverse_sql", "{col}")
                sql_script = build_duckdb_script(
                    gold_sql=manifest_private["gold_sql"],
                    table_registry=split_registry,
                    workspace_dir=workspace,
                    column_alias_mapping=split_col_map,
                    column_inverse_sql=inverse_sql_by_table,
                )
            touched = [fp.name for fp in workspace.iterdir() if fp.is_file()]
            df = execute_duckdb_script(sql_script)

        out_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_csv, index=False)
        return {"success": True, "files_touched": touched, "error": None, "split": split, "view": view}
    except Exception as exc:  # noqa: BLE001
        req = manifest_public["deliverable_spec"].get("required_columns", [])
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=req).to_csv(out_csv, index=False)
        return {"success": False, "files_touched": touched, "error": str(exc), "split": split, "view": view}
    finally:
        conn.close()


def run_eval(
    bench_root: Path,
    mode: str,
    out_dir: Path,
    split_filter: str,
    view_filter: str,
    access_mode: str,
    variant_filter: List[str],
    seed_filter: List[str],
) -> Dict[str, Any]:
    seed_dirs = _list_seed_dirs(bench_root, seed_filter=set(seed_filter) if seed_filter else None)
    out_dir.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []

    for seed_dir in seed_dirs:
        seed_id = seed_dir.name
        for variant in VARIANTS:
            if variant_filter and variant not in variant_filter:
                continue
            variant_root = seed_dir / "variants" / variant
            pub_path = variant_root / "manifest_public.json"
            pri_path = variant_root / "manifest_private.json"
            if not pub_path.exists() or not pri_path.exists():
                continue

            pub = _load_json(pub_path)
            pri = _load_json(pri_path)
            spec = pub["deliverable_spec"]
            gold = pub["gold_path"]

            for split, view in _iter_selected_settings(pub, split_filter, view_filter):
                run_csv = out_dir / seed_id / variant / split / f"{view}.csv"
                meta = _run_agent_once(mode, pub, pri, split, view, run_csv, access_mode=access_mode)
                score = score_single(result_path=run_csv, gold_path=gold, spec=spec)
                attribution_private = pri if split != "l0" else None
                attribution = attribute_failure(
                    score=score,
                    result_csv=run_csv,
                    manifest_private=attribution_private,
                    agent_meta=meta,
                )
                rec = {
                    "seed_id": seed_id,
                    "variant": variant,
                    "split": split,
                    "view": view,
                    "pass": bool(score.get("pass")),
                    "score": float(score.get("score", 0.0)),
                    "stage": score.get("stage"),
                    "attribution": attribution,
                    "meta": meta,
                }
                records.append(rec)

    asr_by_setting: Dict[str, float] = {}
    pass_rate_by_setting: Dict[str, float] = {}
    pass_count_by_setting: Dict[str, Dict[str, int]] = {}
    attribution_by_setting: Dict[str, Dict[str, int]] = {}
    settings = sorted({f"{r['split']}.{r['view']}" for r in records})
    for setting in settings:
        split, view = setting.split(".", 1)
        by_seed: Dict[str, Dict[str, bool]] = {}
        attr_counts: Dict[str, int] = {}
        total_records = 0
        passed_records = 0
        for r in records:
            if r["split"] != split or r["view"] != view:
                continue
            total_records += 1
            passed_records += int(bool(r["pass"]))
            by_seed.setdefault(r["seed_id"], {})[r["variant"]] = bool(r["pass"])
            label = r.get("attribution", "UNKNOWN")
            attr_counts[label] = attr_counts.get(label, 0) + 1

        success = 0
        total = len(by_seed)
        for seed_id, var_pass in by_seed.items():
            if all(var_pass.get(v, False) for v in VARIANTS):
                success += 1
        asr_by_setting[setting] = (success / total) if total else 0.0
        pass_rate_by_setting[setting] = (passed_records / total_records) if total_records else 0.0
        pass_count_by_setting[setting] = {"passed": passed_records, "total": total_records}
        attribution_by_setting[setting] = attr_counts

    asr_by_split = {
        split: asr_by_setting.get(f"{split}.full", 0.0)
        for split in ("l0", "l1", "l2", "l3")
        if f"{split}.full" in asr_by_setting
    }
    pass_rate_by_split = {
        split: pass_rate_by_setting.get(f"{split}.full", 0.0)
        for split in ("l0", "l1", "l2", "l3")
        if f"{split}.full" in pass_rate_by_setting
    }
    asr_by_view = {
        view: asr_by_setting.get(f"l3.{view}", 0.0)
        for view in ("full", "oracle", "trimmed")
        if f"l3.{view}" in asr_by_setting
    }
    pass_rate_by_view = {
        view: pass_rate_by_setting.get(f"l3.{view}", 0.0)
        for view in ("full", "oracle", "trimmed")
        if f"l3.{view}" in pass_rate_by_setting
    }
    pass_count_by_view = {
        view: pass_count_by_setting.get(f"l3.{view}", {"passed": 0, "total": 0})
        for view in ("full", "oracle", "trimmed")
        if f"l3.{view}" in pass_count_by_setting
    }
    attribution_by_view = {
        view: attribution_by_setting.get(f"l3.{view}", {})
        for view in ("full", "oracle", "trimmed")
        if f"l3.{view}" in attribution_by_setting
    }

    report = {
        "mode": mode,
        "canonical_mode": _canonical_mode(mode),
        "agent_variant": _agent_variant(mode),
        "access_mode": access_mode,
        "bench_root": str(bench_root),
        "num_records": len(records),
        "asr_by_setting": asr_by_setting,
        "pass_rate_by_setting": pass_rate_by_setting,
        "pass_count_by_setting": pass_count_by_setting,
        "attribution_by_setting": attribution_by_setting,
        "asr_by_split": asr_by_split,
        "pass_rate_by_split": pass_rate_by_split,
        "asr_by_view": asr_by_view,
        "pass_rate_by_view": pass_rate_by_view,
        "pass_count_by_view": pass_count_by_view,
        "attribution_by_view": attribution_by_view,
        "records": records,
    }

    report = _json_safe(report)
    (out_dir / f"report_{mode}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evaluation on HDR-Bench build")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--mode", default="naive_sql", choices=sorted(SUPPORTED_MODES))
    parser.add_argument("--split", default="all", choices=["all", "l0", "l1", "l2", "l3"])
    parser.add_argument("--view", default="all", choices=["all", "full", "oracle", "trimmed"])
    parser.add_argument("--access_mode", default="public", choices=["public", "dev"])
    parser.add_argument("--variants", default="all", help="Comma-separated subset of variants, e.g. A or A,B")
    parser.add_argument("--seed_ids", default="all", help="Comma-separated subset of seed ids")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    variant_filter = [] if args.variants == "all" else [item.strip() for item in args.variants.split(",") if item.strip()]
    seed_filter = [] if args.seed_ids == "all" else [item.strip() for item in args.seed_ids.split(",") if item.strip()]

    rep = run_eval(
        bench_root=Path(args.bench_root),
        mode=args.mode,
        out_dir=Path(args.out),
        split_filter=args.split,
        view_filter=args.view,
        access_mode=args.access_mode,
        variant_filter=variant_filter,
        seed_filter=seed_filter,
    )
    print(
        json.dumps(
            {
                "mode": rep["mode"],
                "agent_variant": rep["agent_variant"],
                "access_mode": rep["access_mode"],
                "asr_by_split": rep["asr_by_split"],
                "asr_by_view": rep["asr_by_view"],
                "num_records": rep["num_records"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
