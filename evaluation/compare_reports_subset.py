"""Compare pass rates on same seed subset between two support_plan_agent reports."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _subset_report(report_path: Path, split: str, variant: str, seed_set: set[str]) -> list[dict]:
    r = json.loads(report_path.read_text(encoding="utf-8"))
    return [
        x
        for x in r["records"]
        if x.get("split") == split and x.get("variant") == variant and str(x.get("seed_id")) in seed_set
    ]


def summarize(recs: list[dict]) -> dict:
    n = len(recs)
    passed = sum(1 for x in recs if x.get("pass"))
    stages = Counter((x.get("stage") or "OK") for x in recs)
    return {"n": n, "pass": passed, "rate": round(passed / max(n, 1), 4), "stages": dict(stages)}


def main() -> None:
    seeds_path = ROOT / "outputs/_tmp_eval56_l0a_seeds.txt"
    seed_set = set(seeds_path.read_text(encoding="utf-8").strip().split(","))
    old_path = ROOT / "outputs/full150_support_v3_l0_ABC/report_support_plan_agent.json"
    new_path = ROOT / "outputs/support_plan_agent_l0A_n56_20260329/report_support_plan_agent.json"

    old_recs = _subset_report(old_path, "l0", "A", seed_set)
    new_recs = _subset_report(new_path, "l0", "A", seed_set)

    old_ids = {str(x["seed_id"]) for x in old_recs}
    new_ids = {str(x["seed_id"]) for x in new_recs}
    print("seed_set size:", len(seed_set))
    print("old report match:", len(old_recs), "missing old:", len(seed_set - old_ids))
    print("new report match:", len(new_recs), "missing new:", len(seed_set - new_ids))

    so, sn = summarize(old_recs), summarize(new_recs)
    print("\n--- baseline (full150_support_v3_l0_ABC) ---")
    print(json.dumps(so, ensure_ascii=False, indent=2))
    print("\n--- current code ---")
    print(json.dumps(sn, ensure_ascii=False, indent=2))

    by_id_old = {str(x["seed_id"]): x for x in old_recs}
    by_id_new = {str(x["seed_id"]): x for x in new_recs}
    fix: list[str] = []
    reg: list[str] = []
    for sid in sorted(seed_set):
        o, n = by_id_old.get(sid), by_id_new.get(sid)
        if not o or not n:
            continue
        po, pn = bool(o.get("pass")), bool(n.get("pass"))
        if po and not pn:
            reg.append(sid)
        elif not po and pn:
            fix.append(sid)

    print(f"\nflips: +{len(fix)} fixed, -{len(reg)} regressed")
    print("  fixed sample:", fix[:10])
    print("  regressed sample:", reg[:10])


if __name__ == "__main__":
    main()
