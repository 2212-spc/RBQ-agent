from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.run_hdrbench_eval import _json_safe, _load_json, _manifest_path, _run_agent_once
from evaluation.scorer import score_single


def _parse_case(spec: str) -> Dict[str, str]:
    parts = [item.strip() for item in spec.split("|")]
    if len(parts) != 4:
        raise ValueError(f"Invalid case spec: {spec}")
    seed_id, variant, split, view = parts
    return {"seed_id": seed_id, "variant": variant, "split": split, "view": view}


def _summarize(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"modes": {}, "router_paths": {}}
    for rec in records:
        mode = rec["mode"]
        mode_sum = summary["modes"].setdefault(mode, {"passed": 0, "total": 0, "scores": []})
        mode_sum["total"] += 1
        mode_sum["passed"] += int(bool(rec["pass"]))
        mode_sum["scores"].append(float(rec["score"]))
        selected_path = rec.get("selected_path")
        if selected_path:
            route_sum = summary["router_paths"].setdefault(mode, {})
            route_sum[selected_path] = route_sum.get(selected_path, 0) + 1
    for mode_sum in summary["modes"].values():
        scores = mode_sum.pop("scores")
        mode_sum["mean_score"] = (sum(scores) / len(scores)) if scores else 0.0
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small per-case smoke comparison across agent modes.")
    parser.add_argument("--bench_root", required=True)
    parser.add_argument("--cases", required=True, help="Comma-separated seed|variant|split|view items.")
    parser.add_argument("--modes", default="ds_specialist_agent,support_plan_agent,hybrid_router_rule,hybrid_router_llm")
    parser.add_argument("--out", required=True)
    parser.add_argument("--access_mode", default="public", choices=["public", "dev"])
    args = parser.parse_args()

    bench_root = Path(args.bench_root).resolve()
    manifest_root = bench_root.parent.parent
    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    case_specs = [_parse_case(item) for item in args.cases.split(",") if item.strip()]
    modes = [item.strip() for item in args.modes.split(",") if item.strip()]

    records: List[Dict[str, Any]] = []
    for case in case_specs:
        seed_id = case["seed_id"]
        variant = case["variant"]
        split = case["split"]
        view = case["view"]
        variant_root = bench_root / seed_id / "variants" / variant
        pub = _load_json(variant_root / "manifest_public.json")
        pri = _load_json(variant_root / "manifest_private.json")
        pub["_manifest_root"] = str(manifest_root)
        pri["_manifest_root"] = str(manifest_root)
        spec = pub["deliverable_spec"]
        gold = _manifest_path(pub["gold_path"], manifest_root)

        for mode in modes:
            out_csv = out_root / mode / seed_id / variant / split / f"{view}.csv"
            meta = _run_agent_once(mode, pub, pri, split, view, out_csv, access_mode=args.access_mode)
            score = score_single(out_csv, gold, spec)
            record = {
                "mode": mode,
                "seed_id": seed_id,
                "variant": variant,
                "split": split,
                "view": view,
                "pass": bool(score.get("pass")),
                "score": float(score.get("score", 0.0)),
                "stage": score.get("stage"),
                "selected_path": meta.get("selected_path"),
                "router_type": meta.get("router_type"),
                "router_features": meta.get("router_features"),
                "meta": meta,
            }
            records.append(record)
            print(
                json.dumps(
                    {
                        "mode": mode,
                        "case": f"{seed_id}|{variant}|{split}|{view}",
                        "pass": record["pass"],
                        "score": record["score"],
                        "stage": record["stage"],
                        "selected_path": record["selected_path"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    summary = _summarize(records)
    (out_root / "smoke_records.json").write_text(
        json.dumps(_json_safe(records), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_root / "smoke_summary.json").write_text(
        json.dumps(_json_safe(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
