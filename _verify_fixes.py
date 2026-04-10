"""Quick verification of the 3 diagnostic cases after bug fixes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evaluation.support_plan_agent import run_support_plan_agent
from evaluation.scorer import score_single

BENCH_ROOT = Path("outputs/hdrbench_full150_v1")

TEST_CASES = [
    "spider__chinook_1__00825",
    "spider__bike_1__00139",
    "spider__debate__01501",
]


def run_case(seed_id: str, variant: str = "A", split: str = "l0"):
    variant_root = BENCH_ROOT / seed_id / "variants" / variant
    pub_path = variant_root / "manifest_public.json"

    if not pub_path.exists():
        print(f"SKIP {seed_id}/{variant}: manifest not found")
        return

    pub = json.loads(pub_path.read_text(encoding="utf-8", errors="replace"))
    spec = pub["deliverable_spec"]
    gold_path = Path(pub["gold_path"])
    instruction = pub.get("instruction", "")

    # Resolve workspace
    split_views = pub.get("splits", {})
    if split in split_views:
        views = split_views[split]
        view = "full" if "full" in views else list(views.keys())[0]
        workspace = Path(views[view])
    else:
        print(f"SKIP {seed_id}: no split={split}")
        return

    out_csv = Path("_verify_tmp") / seed_id / "result.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"CASE: {seed_id}")
    print(f"Q: {instruction}")
    print(f"Cols: {spec.get('required_columns')}")
    print(f"Workspace: {workspace}")

    meta = run_support_plan_agent(
        instruction=instruction,
        workspace=workspace,
        deliverable_spec=spec,
        output_csv=out_csv,
    )

    print(f"\nAgent success: {meta['success']}")
    print(f"Operator plan: {meta.get('support_plan', {}).get('operator_plan')}")
    sql = meta.get('final_sql') or 'N/A'
    print(f"SQL: {sql[:300]}")

    score = score_single(result_path=out_csv, gold_path=gold_path, spec=spec)
    print(f"Score: pass={score.get('pass')}, f1={score.get('score', 0):.4f}, stage={score.get('stage')}")

    try:
        import pandas as pd
        df = pd.read_csv(out_csv)
        print(f"Result rows: {len(df)}")
        print(df.head(5).to_string(index=False))
    except Exception as e:
        print(f"Cannot read result: {e}")

    # Also show gold
    try:
        import pandas as pd
        gold = pd.read_csv(gold_path)
        print(f"\nGold rows: {len(gold)}")
        print(gold.head(5).to_string(index=False))
    except Exception:
        pass

    return score.get("pass")


if __name__ == "__main__":
    results = {}
    for seed_id in TEST_CASES:
        try:
            passed = run_case(seed_id)
            results[seed_id] = passed
        except Exception as e:
            print(f"\nERROR on {seed_id}: {e}")
            import traceback
            traceback.print_exc()
            results[seed_id] = False

    print(f"\n{'='*60}")
    print("SUMMARY:")
    for seed_id, passed in results.items():
        print(f"  {seed_id}: {'PASS' if passed else 'FAIL'}")
    print(f"  Total: {sum(1 for v in results.values() if v)}/{len(results)}")
