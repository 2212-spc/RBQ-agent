from __future__ import annotations

import json
import random
import shutil
import sqlite3
import string
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from construction.df_utils import read_table_from_registry


def _rand_file_name(rng: random.Random, ext: str) -> str:
    token = "".join(rng.choices(string.ascii_lowercase + string.digits, k=4))
    prefix = rng.choice(["dump", "export", "data", "tmp"])
    return f"{prefix}_{token}{ext}"


def _rand_nonkey_col(rng: random.Random) -> str:
    if rng.random() < 0.5:
        return f"col_{rng.randint(0, 999)}"
    return f"field_{rng.randint(0, 999)}"


def _is_int_like(s: pd.Series) -> bool:
    ss = s.dropna()
    if ss.empty:
        return False
    try:
        pd.to_numeric(ss, errors="raise").astype("Int64")
        return True
    except Exception:  # noqa: BLE001
        return False


def _is_date_like(s: pd.Series) -> bool:
    ss = s.dropna().astype(str)
    if ss.empty:
        return False
    parsed = pd.to_datetime(ss, errors="coerce", utc=False)
    ratio = parsed.notna().mean() if len(parsed) else 0
    return ratio >= 0.8


def _apply_l3_transform(
    series: pd.Series,
    rng: random.Random,
) -> tuple[pd.Series, Dict[str, Any]]:
    if _is_int_like(series):
        base = pd.to_numeric(series, errors="coerce").astype("Int64")
        if rng.random() < 0.5:
            prefix = rng.choice(["ID-", "EMP", "K", "X-"])
            width = rng.choice([4, 5, 6])
            out = base.map(lambda x: None if pd.isna(x) else f"{prefix}{str(int(x)).zfill(width)}")
            spec = {
                "type": "id_prefix_zero_pad",
                "params": {"prefix": prefix, "width": width},
                "inverse_sql": "CAST(regexp_extract({col}, '[0-9]+') AS BIGINT)",
            }
            return out, spec
        width = rng.choice([4, 5, 6])
        out = base.map(lambda x: None if pd.isna(x) else str(int(x)).zfill(width))
        spec = {
            "type": "id_zero_pad",
            "params": {"width": width},
            "inverse_sql": "CAST(regexp_extract({col}, '[0-9]+') AS BIGINT)",
        }
        return out, spec

    if _is_date_like(series):
        parsed = pd.to_datetime(series, errors="coerce", utc=False)
        fmt = rng.choice(["%d/%m/%Y", "%m-%d-%Y", "%d %b %Y"])
        out = parsed.dt.strftime(fmt).where(parsed.notna(), None)
        spec = {
            "type": "date_reformat",
            "params": {"format": fmt},
            "inverse_sql": f"strftime(strptime({{col}}, '{fmt}'), '%Y-%m-%d')",
        }
        return out, spec

    # string-like (reversible): only separator mutation, keep lexical case unchanged.
    sep = rng.choice(["_", "-"])

    def _tx(v: Any) -> Any:
        if pd.isna(v):
            return None
        txt = str(v).strip().replace(" ", sep)
        return txt

    out = series.map(_tx)
    inverse_expr = "replace(replace({col}, '-', ' '), '_', ' ')"
    spec = {
        "type": "string_sep",
        "params": {"sep": sep},
        "inverse_sql": inverse_expr,
    }
    return out, spec


def _load_universe_a(universe_a_dir: Path, table_registry: Dict[str, Dict[str, Any]]) -> Dict[str, pd.DataFrame]:
    return {t: read_table_from_registry(universe_a_dir, entry) for t, entry in table_registry.items()}


def _write_dirty_tables(
    out_full: Path,
    table_registry: Dict[str, Dict[str, Any]],
    tables_dirty: Dict[str, pd.DataFrame],
    file_mapping: Dict[str, str],
) -> None:
    out_full.mkdir(parents=True, exist_ok=True)

    # sqlite files may contain multiple tables; group writes by dirty file.
    sqlite_groups: Dict[str, List[Tuple[str, pd.DataFrame, Dict[str, Any]]]] = defaultdict(list)

    for table, entry in table_registry.items():
        storage = entry["storage_type"]
        dirty_file = file_mapping[entry["file"]]
        df = tables_dirty[table]

        if storage == "sqlite":
            sqlite_groups[dirty_file].append((table, df, entry))
            continue
        fp = out_full / dirty_file
        if storage == "csv":
            df.to_csv(fp, index=False)
        elif storage == "parquet":
            df.to_parquet(fp, index=False)
        else:
            raise ValueError(f"Unsupported storage type {storage}")

    for dirty_file, items in sqlite_groups.items():
        fp = out_full / dirty_file
        if fp.exists():
            fp.unlink()
        conn = sqlite3.connect(str(fp))
        try:
            for table, df, _entry in items:
                df.to_sql(table, conn, index=False, if_exists="replace")
        finally:
            conn.close()


def _build_distractor_schema_similar(
    rng: random.Random,
    ref_df: pd.DataFrame,
    ref_key_cols: List[str],
) -> pd.DataFrame:
    out = ref_df.copy()
    if out.empty:
        return out

    for c in ref_key_cols:
        if c not in out.columns:
            continue
        if _is_int_like(out[c]):
            vals = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)
            out[c] = vals + rng.randint(10000, 20000)
        else:
            out[c] = out[c].astype(str).map(lambda x: f"ZZ_{x}")
    return out.sample(frac=1.0, random_state=rng.randint(1, 10_000_000)).reset_index(drop=True)


def _build_distractor_topic_confusing(rng: random.Random, rows: int = 300) -> pd.DataFrame:
    np_rng = np.random.default_rng(rng.randint(1, 10_000_000))
    return pd.DataFrame(
        {
            "id": np_rng.integers(1, 100000, size=rows),
            "name": [f"name_{i}" for i in range(rows)],
            "date": pd.date_range("2024-01-01", periods=rows, freq="D").astype(str),
            "value": np_rng.normal(loc=50, scale=10, size=rows).round(3),
        }
    )


def _copy_selected_files(src_dir: Path, dst_dir: Path, file_names: List[str]) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for file_name in file_names:
        src = src_dir / file_name
        if src.exists():
            shutil.copy2(src, dst_dir / file_name)


def build_universe_b_for_variant(
    seed: Dict[str, Any],
    variant_id: str,
    variant_root: Path,
    random_seed: int,
    nonkey_rename_prob: float = 0.7,
    l3_apply_prob: float = 0.6,
    distractor_min: int = 3,
    distractor_max: int = 5,
    trimmed_ratio: float = 0.5,
) -> Dict[str, Any]:
    """Generate split-aware Universe B workspaces.

    L1: file rename + distractors only
    L2: L1 + column rename + dummy columns
    L3: L2 + join-key value transforms, plus full/oracle/trimmed views
    """
    rng = random.Random(random_seed)

    universe_a = variant_root / "universe_a"
    universe_b = variant_root / "universe_b"
    explosion_log = json.loads((universe_a / "explosion_log.json").read_text(encoding="utf-8"))
    table_registry = explosion_log["table_registry"]

    tables_clean = _load_universe_a(universe_a, table_registry)

    l1_dir = universe_b / "l1"
    l2_dir = universe_b / "l2"
    l3_dir = universe_b / "l3"
    full_dir = l3_dir / "full"
    oracle_dir = l3_dir / "oracle"
    trimmed_dir = l3_dir / "trimmed"

    # L1 file rename map.
    file_mapping: Dict[str, str] = {}
    used_files: set[str] = set()
    for entry in table_registry.values():
        src = entry["file"]
        if src in file_mapping:
            continue
        ext = Path(src).suffix
        candidate = _rand_file_name(rng, ext)
        while candidate in used_files:
            candidate = _rand_file_name(rng, ext)
        file_mapping[src] = candidate
        used_files.add(candidate)

    key_cols_by_table = {
        t: set(cols)
        for t, cols in seed.get("key_columns_by_table", {}).items()
    }
    join_cols_by_table = {
        t: set(cols)
        for t, cols in seed.get("join_key_columns", {}).items()
    }

    friction_trace: List[Dict[str, Any]] = []
    for src, dst in file_mapping.items():
        friction_trace.append({"level": "L1", "type": "file_rename", "original": src, "transformed": dst})

    identity_column_mapping_by_table: Dict[str, Dict[str, str]] = {
        table: {col: col for col in entry["columns"]}
        for table, entry in table_registry.items()
    }
    identity_column_mapping_flat: Dict[str, str] = {
        f"{table}.{col}": col
        for table, entry in table_registry.items()
        for col in entry["columns"]
    }

    key_counter = 0
    column_mapping_flat: Dict[str, str] = {}
    column_mapping_by_table: Dict[str, Dict[str, str]] = {}
    value_transforms: Dict[str, Dict[str, Any]] = {}
    tables_l1: Dict[str, pd.DataFrame] = {}
    tables_l2: Dict[str, pd.DataFrame] = {}
    tables_l3: Dict[str, pd.DataFrame] = {}
    table_registry_l1: Dict[str, Dict[str, Any]] = {}
    table_registry_l2: Dict[str, Dict[str, Any]] = {}
    table_registry_l3: Dict[str, Dict[str, Any]] = {}
    friction_trace_l1: List[Dict[str, Any]] = [dict(item) for item in friction_trace]
    friction_trace_l2: List[Dict[str, Any]] = [dict(item) for item in friction_trace]
    friction_trace_l3: List[Dict[str, Any]] = [dict(item) for item in friction_trace]

    for table, entry in table_registry.items():
        df_clean = tables_clean[table].copy()
        tables_l1[table] = df_clean.copy()
        col_map: Dict[str, str] = {}

        key_cols = key_cols_by_table.get(table, set())
        join_cols = join_cols_by_table.get(table, set())

        for col in list(df_clean.columns):
            if col in key_cols:
                new_col = f"k{key_counter}"
                key_counter += 1
            else:
                if rng.random() < nonkey_rename_prob:
                    new_col = _rand_nonkey_col(rng)
                else:
                    new_col = col
            col_map[col] = new_col
            if new_col != col:
                event = {
                    "level": "L2",
                    "type": "col_rename",
                    "table": table,
                    "original": col,
                    "transformed": new_col,
                    "is_key": col in key_cols,
                }
                friction_trace_l2.append(event)
                friction_trace_l3.append(dict(event))
            column_mapping_flat[f"{table}.{col}"] = new_col

        df_l2 = df_clean.rename(columns=col_map)

        n_dummy = rng.randint(1, 3)
        for _ in range(n_dummy):
            dcol = f"extra_{rng.randint(100, 999)}"
            while dcol in df_l2.columns:
                dcol = f"extra_{rng.randint(100, 999)}"
            df_l2[dcol] = np.random.default_rng(rng.randint(1, 10_000_000)).integers(0, 1000, size=len(df_l2))
            event = {
                "level": "L2",
                "type": "col_add_dummy",
                "table": table,
                "transformed": dcol,
                "is_key": False,
            }
            friction_trace_l2.append(event)
            friction_trace_l3.append(dict(event))

        shuffled_cols = list(df_l2.columns)
        rng.shuffle(shuffled_cols)
        df_l2 = df_l2[shuffled_cols]
        tables_l2[table] = df_l2

        df_l3 = df_l2.copy()

        transformed_join_cols = []
        for original_col in join_cols:
            dirty_col = col_map.get(original_col, original_col)
            if dirty_col not in df_l3.columns:
                continue
            if rng.random() <= l3_apply_prob:
                tx_series, tx_spec = _apply_l3_transform(df_l3[dirty_col], rng)
                df_l3[dirty_col] = tx_series
                value_transforms[f"{table}.{original_col}"] = {
                    "dirty_column": dirty_col,
                    **tx_spec,
                }
                transformed_join_cols.append(original_col)
                friction_trace_l3.append(
                    {
                        "level": "L3",
                        "type": tx_spec["type"],
                        "table": table,
                        "column": original_col,
                        "dirty_column": dirty_col,
                        "params": tx_spec["params"],
                    }
                )

        if join_cols and not transformed_join_cols:
            first_col = sorted(join_cols)[0]
            dirty_col = col_map[first_col]
            tx_series, tx_spec = _apply_l3_transform(df_l3[dirty_col], rng)
            df_l3[dirty_col] = tx_series
            value_transforms[f"{table}.{first_col}"] = {
                "dirty_column": dirty_col,
                **tx_spec,
            }
            friction_trace_l3.append(
                {
                    "level": "L3",
                    "type": tx_spec["type"],
                    "table": table,
                    "column": first_col,
                    "dirty_column": dirty_col,
                    "params": tx_spec["params"],
                    "forced": True,
                }
            )
        tables_l3[table] = df_l3
        column_mapping_by_table[table] = col_map

        table_registry_l1[table] = {
            "storage_type": entry["storage_type"],
            "file": file_mapping[entry["file"]],
            "table_name": entry["table_name"],
            "canonical_columns": list(entry["columns"]),
            "dirty_columns": list(entry["columns"]),
            "row_count": int(len(df_clean)),
        }
        table_registry_l2[table] = {
            **table_registry_l1[table],
            "dirty_columns": list(df_l2.columns),
            "row_count": int(len(df_l2)),
        }
        table_registry_l3[table] = {
            **table_registry_l2[table],
            "row_count": int(len(df_l3)),
        }

    _write_dirty_tables(l1_dir, table_registry, tables_l1, file_mapping)

    nd = rng.randint(distractor_min, distractor_max)
    distractors: List[Dict[str, Any]] = []
    gold_files = set(file_mapping.values())

    table_names = list(table_registry.keys())
    for i in range(nd):
        is_schema_similar = i % 2 == 0
        storage = rng.choice(["csv", "parquet"])
        ext = ".csv" if storage == "csv" else ".parquet"
        dname = _rand_file_name(rng, ext)
        while dname in gold_files:
            dname = _rand_file_name(rng, ext)

        if is_schema_similar:
            ref_table = rng.choice(table_names)
            ref_df = tables_clean[ref_table]
            ref_keys = list(key_cols_by_table.get(ref_table, set()))
            ddf = _build_distractor_schema_similar(rng, ref_df, ref_keys)
            dtype = "schema_similar"
        else:
            ddf = _build_distractor_topic_confusing(rng, rows=rng.randint(150, 500))
            dtype = "topic_confusing"

        fp = l1_dir / dname
        if storage == "csv":
            ddf.to_csv(fp, index=False)
        else:
            ddf.to_parquet(fp, index=False)

        distractors.append(
            {
                "file": dname,
                "storage_type": storage,
                "type": dtype,
                "rows": int(len(ddf)),
            }
        )
        event = {
            "level": "L1",
            "type": "distractor_add",
            "file": dname,
            "distractor_type": dtype,
        }
        friction_trace_l1.append(event)
        friction_trace_l2.append(dict(event))
        friction_trace_l3.append(dict(event))

    _write_dirty_tables(l2_dir, table_registry, tables_l2, file_mapping)
    _copy_selected_files(l1_dir, l2_dir, [d["file"] for d in distractors])

    _write_dirty_tables(full_dir, table_registry, tables_l3, file_mapping)
    _copy_selected_files(l1_dir, full_dir, [d["file"] for d in distractors])

    oracle_dir.mkdir(parents=True, exist_ok=True)
    for fp in full_dir.iterdir():
        if fp.is_file() and fp.name in gold_files:
            shutil.copy2(fp, oracle_dir / fp.name)

    trimmed_dir.mkdir(parents=True, exist_ok=True)
    keep_d = max(1, int(len(distractors) * trimmed_ratio)) if distractors else 0
    keep_names = set(gold_files)
    keep_names.update(d["file"] for d in distractors[:keep_d])
    for fp in full_dir.iterdir():
        if fp.is_file() and fp.name in keep_names:
            shutil.copy2(fp, trimmed_dir / fp.name)

    manifest = {
        "seed_id": seed["seed_id"],
        "variant": variant_id,
        "views": {
            "full": str(full_dir),
            "oracle": str(oracle_dir),
            "trimmed": str(trimmed_dir),
        },
        "splits": {
            "l1": {"full": str(l1_dir)},
            "l2": {"full": str(l2_dir)},
            "l3": {
                "full": str(full_dir),
                "oracle": str(oracle_dir),
                "trimmed": str(trimmed_dir),
            },
        },
        "table_registry_clean": table_registry,
        "table_registry_dirty": table_registry_l3,
        "table_registry_by_split": {
            "l1": table_registry_l1,
            "l2": table_registry_l2,
            "l3": table_registry_l3,
        },
        "file_mapping": file_mapping,
        "column_mapping": column_mapping_flat,
        "column_mapping_by_table": column_mapping_by_table,
        "column_mapping_by_split": {
            "l1": identity_column_mapping_by_table,
            "l2": column_mapping_by_table,
            "l3": column_mapping_by_table,
        },
        "column_mapping_flat_by_split": {
            "l1": identity_column_mapping_flat,
            "l2": column_mapping_flat,
            "l3": column_mapping_flat,
        },
        "value_transforms": value_transforms,
        "value_transforms_by_split": {
            "l1": {},
            "l2": {},
            "l3": value_transforms,
        },
        "friction_trace": friction_trace_l3,
        "friction_trace_by_split": {
            "l1": friction_trace_l1,
            "l2": friction_trace_l2,
            "l3": friction_trace_l3,
        },
        "distractors": distractors,
        "gold_files_dirty": sorted(gold_files),
    }

    (universe_b / "manifest_dirty.json").parent.mkdir(parents=True, exist_ok=True)
    (universe_b / "manifest_dirty.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return manifest
