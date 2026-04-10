from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_eval_root(eval_root: Path) -> Dict[str, Any]:
    reports = sorted(eval_root.glob("eval_*"))
    summary: Dict[str, Any] = {"eval_root": str(eval_root), "modes": {}}
    for report_dir in reports:
        report_files = list(report_dir.glob("report_*.json"))
        if not report_files:
            continue
        report = _load_json(report_files[0])
        mode = report["mode"]
        asr_by_setting = report.get("asr_by_setting", {})
        l3_oracle = asr_by_setting.get("l3.oracle")
        l3_full = asr_by_setting.get("l3.full")
        if mode not in summary["modes"]:
            summary["modes"][mode] = {
                "access_mode": report.get("access_mode", "unknown"),
                "asr_by_setting": {},
                "pass_rate_by_setting": {},
                "pass_count_by_setting": {},
                "attribution_by_setting": {},
                "asr_by_split": {},
                "pass_rate_by_split": {},
                "asr_by_view": {},
                "pass_rate_by_view": {},
                "pass_count_by_view": {},
                "attribution_by_view": {},
            }
        mode_summary = summary["modes"][mode]
        mode_summary["access_mode"] = report.get("access_mode", mode_summary.get("access_mode", "unknown"))
        mode_summary["asr_by_setting"].update(asr_by_setting)
        mode_summary["pass_rate_by_setting"].update(report.get("pass_rate_by_setting", {}))
        mode_summary["pass_count_by_setting"].update(report.get("pass_count_by_setting", {}))
        mode_summary["attribution_by_setting"].update(report.get("attribution_by_setting", {}))
        mode_summary["asr_by_split"].update(report.get("asr_by_split", {}))
        mode_summary["pass_rate_by_split"].update(report.get("pass_rate_by_split", {}))
        mode_summary["asr_by_view"].update(report.get("asr_by_view", {}))
        mode_summary["pass_rate_by_view"].update(report.get("pass_rate_by_view", {}))
        mode_summary["pass_count_by_view"].update(report.get("pass_count_by_view", {}))
        mode_summary["attribution_by_view"].update(report.get("attribution_by_view", {}))
        mode_summary["delta_asr_l3_oracle_minus_full"] = (
            (mode_summary["asr_by_setting"].get("l3.oracle") - mode_summary["asr_by_setting"].get("l3.full"))
            if isinstance(mode_summary["asr_by_setting"].get("l3.oracle"), (int, float))
            and isinstance(mode_summary["asr_by_setting"].get("l3.full"), (int, float))
            else None
        )
        mode_summary["delta_pass_rate_l3_oracle_minus_full"] = (
            (mode_summary["pass_rate_by_setting"].get("l3.oracle") - mode_summary["pass_rate_by_setting"].get("l3.full"))
            if isinstance(mode_summary["pass_rate_by_setting"].get("l3.oracle"), (int, float))
            and isinstance(mode_summary["pass_rate_by_setting"].get("l3.full"), (int, float))
            else None
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize all eval reports under a benchmark root")
    parser.add_argument("--eval_root", required=True, help="Benchmark output root containing eval_* dirs")
    parser.add_argument("--out", required=True, help="Output summary json path")
    args = parser.parse_args()

    summary = summarize_eval_root(Path(args.eval_root))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
