from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict

from sqlglot import exp, parse_one

from construction.seed_tools import parse_sql_metadata


def classify_sql_motif(sql: str) -> Dict[str, Any]:
    sql_meta = parse_sql_metadata(sql)
    tree = parse_one(sql, read="sqlite")

    join_count = len(sql_meta.get("joins", []))
    has_aggregation = any(isinstance(node, exp.AggFunc) for node in tree.walk())
    has_group = tree.args.get("group") is not None
    has_having = tree.args.get("having") is not None
    has_where = tree.args.get("where") is not None
    has_order = tree.args.get("order") is not None or tree.args.get("limit") is not None
    has_distinct = tree.args.get("distinct") is not None

    if join_count >= 1 and (has_aggregation or has_group or has_having):
        base_label = "AggregationJoin"
    elif join_count >= 1 and has_where:
        base_label = "FilterJoin"
    elif join_count >= 1:
        base_label = "SimpleJoin"
    else:
        base_label = "Other"

    modifiers = []
    if has_order:
        modifiers.append("Order")
    if has_distinct:
        modifiers.append("Distinct")

    return {
        "base_label": base_label,
        "has_order": has_order,
        "has_distinct": has_distinct,
        "modifier_labels": modifiers,
        "display_label": base_label + ("+" + "+".join(modifiers) if modifiers else ""),
        "join_count": join_count,
        "has_aggregation": bool(has_aggregation or has_group or has_having),
        "has_where": has_where,
    }


def build_seed_motif_index(bench_root: str | Path) -> Dict[str, Dict[str, Any]]:
    root = Path(bench_root)
    seed_index: Dict[str, Dict[str, Any]] = {}

    for seed_dir in sorted(path for path in root.iterdir() if path.is_dir() and (path / "seed_report.json").exists()):
        variant_motifs: Dict[str, Dict[str, Any]] = {}
        for variant in ("A", "B", "C"):
            manifest_private = seed_dir / "variants" / variant / "manifest_private.json"
            if not manifest_private.exists():
                continue
            payload = json.loads(manifest_private.read_text(encoding="utf-8"))
            motif = classify_sql_motif(str(payload["gold_sql"]))
            variant_motifs[variant] = motif

        if not variant_motifs:
            continue

        signatures = {
            (
                motif["base_label"],
                motif["has_order"],
                motif["has_distinct"],
            )
            for motif in variant_motifs.values()
        }
        if len(signatures) != 1:
            raise ValueError(f"Inconsistent motif across variants for seed {seed_dir.name}: {variant_motifs}")

        selected_variant = sorted(variant_motifs)[0]
        seed_index[seed_dir.name] = {
            "seed_id": seed_dir.name,
            "variant_checked": selected_variant,
            **variant_motifs[selected_variant],
        }

    return seed_index


def summarize_seed_motifs(seed_index: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    base_counter = Counter()
    modifier_counter = Counter()

    for motif in seed_index.values():
        base_counter[motif["base_label"]] += 1
        if motif["has_order"]:
            modifier_counter["has_order"] += 1
        if motif["has_distinct"]:
            modifier_counter["has_distinct"] += 1

    return {
        "base_counts": dict(sorted(base_counter.items())),
        "modifier_counts": dict(sorted(modifier_counter.items())),
    }
