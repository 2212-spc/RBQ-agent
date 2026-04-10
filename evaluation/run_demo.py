from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.attribution import attribute_failure
from evaluation.scorer import score_single


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _list_sqlite_tables(db_path: Path) -> List[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def run_direct_sql_baseline(case_dir: Path, view: str) -> Dict[str, Any]:
    pub = _load_json(case_dir / "manifest_public.json")
    priv = _load_json(case_dir / "manifest_private.json")

    workspace = Path(pub["views"][view])
    out_dir = case_dir / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    result_csv = out_dir / f"direct_sql_{view}.csv"
    meta_path = out_dir / f"direct_sql_{view}.meta.json"

    touched_files: List[str] = []
    start = time.time()

    conn = duckdb.connect(database=":memory:")
    success = False
    error = None

    try:
        for fp in workspace.iterdir():
            if not fp.is_file():
                continue
            touched_files.append(fp.name)
            ext = fp.suffix.lower()
            fp_uri = str(fp).replace("\\", "/")
            if ext == ".csv":
                view_name = fp.stem
                conn.execute(
                    f"CREATE OR REPLACE TEMP VIEW \"{view_name}\" AS SELECT * FROM read_csv_auto('{fp_uri}')"
                )
            elif ext == ".parquet":
                view_name = fp.stem
                conn.execute(
                    f"CREATE OR REPLACE TEMP VIEW \"{view_name}\" AS SELECT * FROM read_parquet('{fp_uri}')"
                )
            elif ext == ".sqlite":
                for t in _list_sqlite_tables(fp):
                    conn.execute(
                        f"CREATE OR REPLACE TEMP VIEW \"{t}\" AS SELECT * FROM sqlite_scan('{fp_uri}', '{t}')"
                    )

        df = conn.execute(priv["gold_sql"]).fetchdf()
        df.to_csv(result_csv, index=False)
        success = True
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        # Ensure scorer sees a parseable artifact when possible.
        required_cols = pub["deliverable_spec"].get("required_columns", [])
        if required_cols:
            pd.DataFrame(columns=required_cols).to_csv(result_csv, index=False)
    finally:
        conn.close()

    elapsed = time.time() - start
    meta = {
        "success": success,
        "files_touched": touched_files,
        "time_seconds": round(elapsed, 4),
        "error": error,
        "result_csv": str(result_csv),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    score = score_single(result_path=result_csv, gold_path=pub["gold_path"], spec=pub["deliverable_spec"])
    label = attribute_failure(score, result_csv=result_csv, manifest_private=priv, agent_meta=meta)

    return {
        "view": view,
        "score": score,
        "attribution": label,
        "meta": meta,
        "result_csv": str(result_csv),
    }


def collect_cases(cases_root: Path) -> List[Path]:
    return sorted([p for p in cases_root.iterdir() if p.is_dir() and (p / "manifest_public.json").exists()])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MVP demo baselines on built cases")
    parser.add_argument("--cases", required=True, help="Path to outputs/cases")
    parser.add_argument("--view", default="full", choices=["full", "oracle", "trimmed", "all"])
    args = parser.parse_args()

    cases_root = Path(args.cases)
    case_dirs = collect_cases(cases_root)
    if not case_dirs:
        raise SystemExit(f"No cases found under {cases_root}")

    report_lines: List[str] = ["# HDR-Bench MVP Demo Report", ""]
    report_lines.append(f"- Cases: {len(case_dirs)}")
    report_lines.append(f"- View: {args.view}")
    report_lines.append("")

    views = ["full", "oracle", "trimmed"] if args.view == "all" else [args.view]

    aggregate: Dict[str, int] = {"PASS": 0, "DISCOVERY_FAIL": 0, "SCHEMA_FAIL": 0, "INSTANCE_FAIL": 0, "QUERY_FAIL": 0, "DELIVERY_FAIL": 0}
    total = 0

    for case_dir in case_dirs:
        report_lines.append(f"## Case {case_dir.name}")
        perfect_report_path = case_dir / "perfect_agent_report.json"
        if perfect_report_path.exists():
            perfect_report = _load_json(perfect_report_path)
            report_lines.append(f"- Perfect-Agent: {'PASS' if perfect_report.get('perfect_agent_pass') else 'FAIL'}")
        for v in views:
            run = run_direct_sql_baseline(case_dir, v)
            total += 1
            label = run["attribution"]
            aggregate[label] = aggregate.get(label, 0) + 1

            report_lines.append(f"- View `{v}`: pass={run['score']['pass']}, score={run['score']['score']:.4f}, attribution={label}")
        report_lines.append("")

    report_lines.append("## Attribution Breakdown")
    for k, v in aggregate.items():
        if v > 0:
            report_lines.append(f"- {k}: {v}/{total}")

    out_report = cases_root.parent / "mvp_report.md"
    out_report.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Report saved: {out_report}")


if __name__ == "__main__":
    main()
