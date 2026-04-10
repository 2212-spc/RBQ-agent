"""Debug observable sketch + per-slot ranking for rerank-category seeds."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from evaluation.run_hdrbench_eval import _load_json
from evaluation.support_plan_agent.probes import prepare_case_context
from evaluation.support_plan_agent.search import _best_output_bindings, search_support_plans
from evaluation.workspace_catalog import tokenize

BENCH = Path("outputs/hdrbench_full150_v1")

SEEDS = [
    "spider__climbing__01130",
    "spider__match_season__01072",
    "spider__tracking_share_transactions__05871",
]


def debug_one(seed_id: str) -> Dict[str, Any]:
    seed_dir = BENCH / seed_id
    pub = _load_json(seed_dir / "variants" / "A" / "manifest_public.json")
    pri = _load_json(seed_dir / "variants" / "A" / "manifest_private.json")
    ctx = prepare_case_context(
        pub, pri, split="l0", view="full", sketch_mode="live",
        namespace=f"debug_{seed_id}",
    )
    qtok = tokenize(ctx.instruction)
    ranked = _best_output_bindings(ctx.observable_sketch, ctx.catalog, qtok, top_k=6)

    slot_info = []
    for slot in ctx.observable_sketch.output_slots:
        candidates = [
            {"src": b.source_id.split("::")[-1], "col": b.column_name, "score": round(b.score, 3)}
            for b in ranked.get(slot.label, [])
        ]
        slot_info.append({"label": slot.label, "role": slot.role, "top6": candidates})

    # gold targets
    gold_pairs = {}
    for label, bindings in ctx.gold_targets.output_bindings_by_label.items():
        gold_pairs[label] = [(b.table_name, b.canonical_column) for b in bindings]

    # best plan outputs
    summary = search_support_plans(
        ctx.instruction, ctx.observable_sketch, ctx.obligation_sketch, ctx.catalog,
    )
    best = summary["best_plan"]
    best_out = [(b.source_id.split("::")[-1], b.column_name) for b in best.output_bindings]

    # source question overlap
    source_overlaps = {}
    from evaluation.support_plan_agent.search import _question_overlap
    for sid, src in ctx.catalog.sources.items():
        source_overlaps[src.table_name or sid] = round(_question_overlap(qtok, src), 4)
    top_sources = sorted(source_overlaps.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "seed_id": seed_id,
        "instruction": ctx.instruction,
        "required_columns": ctx.deliverable_spec.get("required_columns", []),
        "output_slots": [
            {"label": s.label, "role": s.role}
            for s in ctx.observable_sketch.output_slots
        ],
        "operator_plan": ctx.observable_sketch.order_hint,
        "per_slot_top6": slot_info,
        "gold_pairs_by_label": gold_pairs,
        "best_plan_outputs": best_out,
        "top_source_q_overlaps": dict(top_sources),
    }


if __name__ == "__main__":
    for sid in SEEDS:
        r = debug_one(sid)
        print(f"\n{'='*60}")
        print(f"SEED: {sid}")
        print(f"INSTRUCTION: {r['instruction']}")
        print(f"REQUIRED_COLS: {r['required_columns']}")
        print(f"OUTPUT_SLOTS: {[(s['label'], s['role']) for s in r['output_slots']]}")
        print(f"BEST_PLAN: {r['best_plan_outputs']}")
        print(f"GOLD_PAIRS: {r['gold_pairs_by_label']}")
        print(f"TOP_Q_OVERLAPS: {r['top_source_q_overlaps']}")
        for slot in r["per_slot_top6"]:
            print(f"  slot[{slot['label']}] role={slot['role']}")
            for c in slot["top6"]:
                print(f"    {c['src']}.{c['col']}  score={c['score']}")
