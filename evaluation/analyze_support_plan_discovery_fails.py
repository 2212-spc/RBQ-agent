from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.run_hdrbench_eval import _load_json
from evaluation.support_plan_agent.diagnostics import summarize_discovery_failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize DISCOVERY_FAIL subtypes from a support-plan report.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = _load_json(Path(args.report))
    payload = summarize_discovery_failures(report)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
