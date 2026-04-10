"""Print precision/recall for l1/l2 seeds that flipped stage between baseline and reval."""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.scorer import score_single

ROOT = Path(__file__).resolve().parents[1]


def _gold_path(seed: str) -> Path:
    pub = json.loads((ROOT / "outputs/hdrbench_full150_v1" / seed / "variants/A/manifest_public.json").read_text(encoding="utf-8"))
    g = Path(pub["gold_path"])
    return g if g.is_absolute() else ROOT / g


def _score_csv(seed: str, sp: str, report_subdir: str) -> dict | None:
    pub = json.loads((ROOT / "outputs/hdrbench_full150_v1" / seed / "variants/A/manifest_public.json").read_text(encoding="utf-8"))
    p = ROOT / "outputs" / report_subdir / seed / "A" / sp / "full.csv"
    if not p.exists():
        return None
    return score_single(p, _gold_path(seed), pub["deliverable_spec"])


def main() -> None:
    l1_seeds = [
        "spider__bike_1__00139",
        "spider__decoration_competition__04495",
        "spider__climbing__01132",
        "spider__tracking_share_transactions__05871",
    ]
    print("--- l1 flips (precision/recall) ---")
    for seed in l1_seeds:
        print(f"\n{seed}")
        for tag, sub in [
            ("baseline", "full150_support_v3_l1_ABC"),
            ("reval   ", "support_plan_l012_reval/l1"),
        ]:
            s = _score_csv(seed, "l1", sub)
            if not s:
                print(f"  {tag}: (no csv)")
                continue
            print(
                f"  {tag}: P={float(s['precision']):.3f} R={float(s['recall']):.3f} "
                f"rows={s['result_rows']}/{s['gold_rows']} stage={s['stage']}"
            )

    print("\n--- l2 pass gain (precision/recall) ---")
    for seed in ["spider__entertainment_awards__04607", "spider__products_gen_characteristics__05542"]:
        print(f"\n{seed}")
        for tag, sub in [
            ("baseline", "full150_support_v3_l2_ABC"),
            ("reval   ", "support_plan_l012_reval/l2"),
        ]:
            s = _score_csv(seed, "l2", sub)
            if not s:
                print(f"  {tag}: (no csv)")
                continue
            print(
                f"  {tag}: P={float(s['precision']):.3f} R={float(s['recall']):.3f} "
                f"rows={s['result_rows']}/{s['gold_rows']} stage={s['stage']}"
            )


if __name__ == "__main__":
    main()
