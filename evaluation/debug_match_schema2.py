"""Check match_season catalog and join edges."""
from pathlib import Path
from evaluation.run_hdrbench_eval import _load_json
from evaluation.support_plan_agent.probes import prepare_case_context

BENCH = Path("outputs/hdrbench_full150_v1")
sid = "spider__match_season__01072"
ctx = prepare_case_context(
    _load_json(BENCH / sid / "variants/A/manifest_public.json"),
    _load_json(BENCH / sid / "variants/A/manifest_private.json"),
    split="l0", view="full", sketch_mode="live", namespace=f"rerank_{sid}",
)

# Show all sources and their columns
print("=== SOURCES ===")
for src_id, src in ctx.catalog.sources.items():
    cols = list(src.column_profiles.keys())[:12]
    role = src.role_hint
    print(f"  {src.table_name or src_id} ({role}): {cols}")

print("\n=== ALL EDGES ===")
for edge in ctx.catalog.join_edges:
    left = edge.left_source_id.split("::")[-1]
    right = edge.right_source_id.split("::")[-1]
    print(f"  {left}.{edge.left_column} <-> {right}.{edge.right_column}  overlap={edge.overlap:.3f}")
