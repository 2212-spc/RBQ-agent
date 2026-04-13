from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt

from evaluation.hybrid_router_agent import (
    _decide_llm_route,
    _decide_rule_route,
    compute_router_features,
)
from evaluation.run_hdrbench_eval import _iter_selected_settings, _load_json, _resolve_workspace


def _pick_seed_dirs(bench_root: Path, num_seeds: int, seed: int) -> List[Path]:
    seed_dirs = sorted(
        [
            p
            for p in bench_root.iterdir()
            if p.is_dir() and (p / "variants" / "A" / "manifest_public.json").exists()
        ],
        key=lambda p: p.name,
    )
    rng = random.Random(seed)
    if num_seeds >= len(seed_dirs):
        return seed_dirs
    return sorted(rng.sample(seed_dirs, num_seeds), key=lambda p: p.name)


def _salient_reason(features: Dict[str, Any], selected_path: str) -> str:
    if selected_path == "path_a":
        return (
            f"{features['num_files']} files, "
            f"obf={features['file_obfuscation_ratio']:.2f}/{features['column_obfuscation_ratio']:.2f}, "
            f"join={features['max_join_overlap']:.2f}, "
            f"same_src={features['same_source_proxy']}"
        )
    return (
        f"{features['num_files']} files, "
        f"transform={features['has_transform_risk']}, "
        f"obf={features['file_obfuscation_ratio']:.2f}/{features['column_obfuscation_ratio']:.2f}, "
        f"weak_join={features['weak_join_graph']}"
    )


def _build_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_router_split: Dict[str, Dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for row in records:
        by_router_split[row["router"]][row["split"]][row["selected_path"]] += 1

    summary: Dict[str, Any] = {"by_router_split": {}, "examples": {}}
    for router in ["rule", "llm"]:
        router_summary: Dict[str, Any] = {}
        for split in ["l0", "l1", "l2", "l3"]:
            counts = by_router_split[router][split]
            total = sum(counts.values())
            router_summary[split] = {
                "path_a": counts.get("path_a", 0),
                "path_b": counts.get("path_b", 0),
                "total": total,
                "path_a_ratio": (counts.get("path_a", 0) / total) if total else 0.0,
                "path_b_ratio": (counts.get("path_b", 0) / total) if total else 0.0,
            }
        summary["by_router_split"][router] = router_summary

        examples: Dict[str, List[Dict[str, Any]]] = {"path_a": [], "path_b": []}
        for target_path in ["path_a", "path_b"]:
            matched = [r for r in records if r["router"] == router and r["selected_path"] == target_path]
            matched.sort(key=lambda r: (r["split"], r["seed_id"]))
            for row in matched[:3]:
                examples[target_path].append(
                    {
                        "seed_id": row["seed_id"],
                        "split": row["split"],
                        "reason": row["salient_reason"],
                    }
                )
        summary["examples"][router] = examples
    return summary


def _write_records_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "seed_id",
        "variant",
        "split",
        "router",
        "selected_path",
        "reason",
        "num_files",
        "file_obfuscation_ratio",
        "column_obfuscation_ratio",
        "max_join_overlap",
        "mean_top_join_overlap",
        "transform_edge_ratio",
        "has_transform_risk",
        "same_source_proxy",
        "filter_count",
        "time_filter_count",
        "output_count",
        "weak_join_graph",
        "salient_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({key: row.get(key) for key in fields})


def _plot_summary(summary: Dict[str, Any], figure_pdf: Path, figure_png: Path | None = None) -> None:
    plt.rcParams.update(
        {
            "font.size": 12,
            "axes.titlesize": 15,
            "axes.labelsize": 13,
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
            "legend.fontsize": 11,
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 3.9), constrained_layout=True)
    colors = {"path_a": "#5BA3D0", "path_b": "#E58F3A"}
    titles = {"rule": "(a) Rule Router", "llm": "(b) LLM Meta-Router"}
    labels = ["L0", "L1", "L2", "L3"]
    splits = ["l0", "l1", "l2", "l3"]

    for ax, router in zip(axes, ["rule", "llm"]):
        path_a = [summary["by_router_split"][router][split]["path_a_ratio"] * 100 for split in splits]
        path_b = [summary["by_router_split"][router][split]["path_b_ratio"] * 100 for split in splits]
        ax.bar(labels, path_a, color=colors["path_a"], label="Path A", width=0.62)
        ax.bar(labels, path_b, bottom=path_a, color=colors["path_b"], label="Path B", width=0.62)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Routing share (%)")
        ax.set_title(titles[router], pad=12)
        ax.grid(axis="y", linestyle="--", alpha=0.25)
        ax.set_axisbelow(True)
        for idx, (a, b) in enumerate(zip(path_a, path_b)):
            if a > 0:
                ax.text(idx, a / 2, f"{a:.0f}", ha="center", va="center", fontsize=10, color="white", weight="bold")
            if b > 0:
                ax.text(idx, a + b / 2, f"{b:.0f}", ha="center", va="center", fontsize=10, color="white", weight="bold")
        if router == "llm":
            ax.legend(loc="upper right", frameon=False)

    figure_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_pdf, bbox_inches="tight")
    if figure_png is not None:
        fig.savefig(figure_png, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a route-only probe for hybrid routing behavior.")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--num_seeds", type=int, default=25)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--variant", default="A")
    parser.add_argument("--figure_pdf", default="")
    parser.add_argument("--figure_png", default="")
    args = parser.parse_args()

    bench_root = Path(args.bench_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_root = bench_root.parent.parent
    records: List[Dict[str, Any]] = []
    for seed_dir in _pick_seed_dirs(bench_root, args.num_seeds, args.seed):
        seed_id = seed_dir.name
        variant_root = seed_dir / "variants" / args.variant
        pub = _load_json(variant_root / "manifest_public.json")
        pub["_manifest_root"] = str(manifest_root)
        instruction = pub.get("instruction", "")
        deliverable_spec = pub.get("deliverable_spec", {})

        for split, view in _iter_selected_settings(pub, split_filter="all", view_filter="full"):
            if view != "full":
                continue
            workspace = _resolve_workspace(pub, split, view)
            feature_pack = compute_router_features(instruction, workspace, deliverable_spec)
            features = feature_pack["features"]
            feature_dict = features.to_dict()
            observable_sketch = feature_pack["observable_sketch"]
            workspace_summary = feature_pack["workspace_summary"]

            for router, route in [
                ("rule", _decide_rule_route(features)),
                ("llm", _decide_llm_route(instruction, workspace_summary, features, observable_sketch)),
            ]:
                row = {
                    "seed_id": seed_id,
                    "variant": args.variant,
                    "split": split,
                    "router": router,
                    "selected_path": route["selected_path"],
                    "reason": route.get("reason", ""),
                    **feature_dict,
                }
                row["salient_reason"] = _salient_reason(feature_dict, route["selected_path"])
                records.append(row)

    records_path = out_dir / "router_probe_cases.csv"
    summary_path = out_dir / "router_probe_summary.json"
    _write_records_csv(records_path, records)
    summary = _build_summary(records)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.figure_pdf:
        _plot_summary(
            summary,
            figure_pdf=Path(args.figure_pdf).resolve(),
            figure_png=Path(args.figure_png).resolve() if args.figure_png else None,
        )

    print(
        json.dumps(
            {
                "num_case_views": len(records) // 2,
                "num_router_decisions": len(records),
                "records_csv": str(records_path),
                "summary_json": str(summary_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
