from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from construction.df_utils import compare_frames, read_table_from_registry
from construction.sql_rewrite import build_duckdb_script, execute_duckdb_script


def _inverse_series(series: pd.Series, spec: Dict[str, Any]) -> pd.Series:
    typ = spec.get("type")
    params = spec.get("params", {})

    if typ in {"id_prefix_zero_pad", "id_zero_pad"}:
        out = series.astype(str).str.extract(r"(\d+)", expand=False)
        out = pd.to_numeric(out, errors="coerce").astype("Int64")
        return out

    if typ == "date_reformat":
        fmt = params.get("format", "%d/%m/%Y")
        parsed = pd.to_datetime(series, format=fmt, errors="coerce")
        return parsed.dt.strftime("%Y-%m-%d")

    if typ == "string_sep":
        return series.astype(str).str.replace("-", " ", regex=False).str.replace("_", " ", regex=False)

    return series


def run_inverse_check(seed: Dict[str, Any], variant_root: Path) -> Dict[str, Any]:
    universe_a = variant_root / "universe_a"
    universe_b = variant_root / "universe_b"

    manifest_dirty = json.loads((universe_b / "manifest_dirty.json").read_text(encoding="utf-8"))
    clean_registry = manifest_dirty["table_registry_clean"]
    full_dir = Path(manifest_dirty.get("splits", {}).get("l3", {}).get("full", universe_b / "full"))
    dirty_registry = manifest_dirty.get("table_registry_by_split", {}).get("l3", manifest_dirty["table_registry_dirty"])
    col_map_by_table = manifest_dirty.get("column_mapping_by_split", {}).get("l3", manifest_dirty["column_mapping_by_table"])
    value_transforms = manifest_dirty.get("value_transforms_by_split", {}).get("l3", manifest_dirty.get("value_transforms", {}))

    per_table: Dict[str, Any] = {}
    all_pass = True

    for table, clean_entry in clean_registry.items():
        clean_df = read_table_from_registry(universe_a, clean_entry)
        dirty_df = read_table_from_registry(full_dir, dirty_registry[table])

        c2d = col_map_by_table[table]
        d2c = {d: c for c, d in c2d.items()}

        # Keep only mapped columns, drop dummy cols.
        selected = [d for d in d2c.keys() if d in dirty_df.columns]
        recovered = dirty_df[selected].rename(columns=d2c)

        # Ensure canonical column order coverage.
        for c in clean_entry["columns"]:
            if c not in recovered.columns:
                recovered[c] = None
        recovered = recovered[clean_entry["columns"]]

        # Invert L3 per canonical column.
        for fq, spec in value_transforms.items():
            t, col = fq.split(".", 1)
            if t != table or col not in recovered.columns:
                continue
            recovered[col] = _inverse_series(recovered[col], spec)

        ok = compare_frames(clean_df, recovered, float_tol=1e-6)
        per_table[table] = {
            "pass": bool(ok),
            "clean_rows": int(len(clean_df)),
            "recovered_rows": int(len(recovered)),
        }
        all_pass = all_pass and ok

    report = {
        "inverse_pass": bool(all_pass),
        "per_table": per_table,
    }
    (variant_root / "inverse_check_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def run_perfect_agent_check(seed: Dict[str, Any], variant_root: Path) -> Dict[str, Any]:
    universe_a = variant_root / "universe_a"
    universe_b = variant_root / "universe_b"

    manifest_dirty = json.loads((universe_b / "manifest_dirty.json").read_text(encoding="utf-8"))
    full_dir = Path(manifest_dirty.get("splits", {}).get("l3", {}).get("full", universe_b / "full"))
    dirty_registry = manifest_dirty.get("table_registry_by_split", {}).get("l3", manifest_dirty["table_registry_dirty"])
    col_map = manifest_dirty.get("column_mapping_by_split", {}).get("l3", manifest_dirty["column_mapping_by_table"])
    value_transforms = manifest_dirty.get("value_transforms_by_split", {}).get("l3", manifest_dirty.get("value_transforms", {}))

    inverse_sql_by_table: Dict[str, Dict[str, str]] = {}
    for fq, spec in value_transforms.items():
        t, c = fq.split(".", 1)
        inverse_sql_by_table.setdefault(t, {})[c] = spec.get("inverse_sql", "{col}")

    script = build_duckdb_script(
        gold_sql=seed["gold_sql"],
        table_registry=dirty_registry,
        workspace_dir=full_dir,
        column_alias_mapping=col_map,
        column_inverse_sql=inverse_sql_by_table,
    )

    pred_df = execute_duckdb_script(script)
    gold_df = pd.read_csv(universe_a / "gold.csv")
    ok = compare_frames(gold_df, pred_df, float_tol=1e-6)

    (variant_root / "perfect_agent.sql").write_text(script, encoding="utf-8")
    pred_df.to_csv(variant_root / "perfect_agent_result.csv", index=False)

    report = {
        "perfect_agent_pass": bool(ok),
        "perfect_sql_path": str(variant_root / "perfect_agent.sql"),
        "result_path": str(variant_root / "perfect_agent_result.csv"),
    }
    (variant_root / "perfect_agent_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
