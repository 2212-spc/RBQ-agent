from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.motif_taxonomy import build_seed_motif_index, summarize_seed_motifs


RecordKey = Tuple[str, str, str, str]
SeedSettingKey = Tuple[str, str, str]


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _report_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mode": report.get("mode"),
        "canonical_mode": report.get("canonical_mode"),
        "agent_variant": report.get("agent_variant", "default"),
        "asr_by_split": report.get("asr_by_split", {}),
        "pass_rate_by_split": report.get("pass_rate_by_split", {}),
        "asr_by_view": report.get("asr_by_view", {}),
        "pass_rate_by_view": report.get("pass_rate_by_view", {}),
        "attribution_by_setting": report.get("attribution_by_setting", {}),
        "num_records": report.get("num_records", 0),
    }


def _representative_failures(report: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    failures = [rec for rec in report.get("records", []) if not rec.get("pass")]
    failures.sort(key=lambda item: (item.get("split", ""), item.get("view", ""), item.get("seed_id", "")))
    return [
        {
            "seed_id": rec["seed_id"],
            "variant": rec["variant"],
            "split": rec["split"],
            "view": rec["view"],
            "attribution": rec.get("attribution"),
            "error": rec.get("meta", {}).get("error"),
        }
        for rec in failures[:limit]
    ]


def _record_key(rec: Dict[str, Any]) -> RecordKey:
    return (
        str(rec["seed_id"]),
        str(rec["variant"]),
        str(rec["split"]),
        str(rec["view"]),
    )


def _setting_name_from_key(key: RecordKey) -> str:
    return f"{key[2]}.{key[3]}"


def _seed_setting_key(key: RecordKey) -> SeedSettingKey:
    return (key[0], key[2], key[3])


def _record_map(report: Dict[str, Any]) -> Dict[RecordKey, Dict[str, Any]]:
    return {_record_key(rec): rec for rec in report.get("records", [])}


def _count_record_head_to_head(
    baseline_records: Iterable[Dict[str, Any]],
    candidate_records: Iterable[Dict[str, Any]],
) -> Dict[str, int]:
    counts = Counter(
        {
            "candidate_only_pass": 0,
            "baseline_only_pass": 0,
            "both_pass": 0,
            "both_fail": 0,
        }
    )
    for baseline, candidate in zip(baseline_records, candidate_records):
        baseline_pass = bool(baseline.get("pass"))
        candidate_pass = bool(candidate.get("pass"))
        if candidate_pass and baseline_pass:
            counts["both_pass"] += 1
        elif candidate_pass and not baseline_pass:
            counts["candidate_only_pass"] += 1
        elif baseline_pass and not candidate_pass:
            counts["baseline_only_pass"] += 1
        else:
            counts["both_fail"] += 1
    return dict(counts)


def _seed_success_by_setting(
    records: Dict[RecordKey, Dict[str, Any]],
    keys: Iterable[RecordKey],
) -> Tuple[Dict[SeedSettingKey, bool], Dict[str, List[str]]]:
    by_seed_setting: Dict[SeedSettingKey, Dict[str, bool]] = defaultdict(dict)
    variants_by_setting: Dict[str, set[str]] = defaultdict(set)

    for key in keys:
        seed_id, variant, split, view = key
        by_seed_setting[(seed_id, split, view)][variant] = bool(records[key].get("pass"))
        variants_by_setting[f"{split}.{view}"].add(variant)

    success_by_seed_setting: Dict[SeedSettingKey, bool] = {}
    normalized_variants = {
        setting: sorted(variants)
        for setting, variants in variants_by_setting.items()
    }
    for seed_setting, variant_pass in by_seed_setting.items():
        setting = f"{seed_setting[1]}.{seed_setting[2]}"
        expected_variants = normalized_variants[setting]
        success_by_seed_setting[seed_setting] = all(variant_pass.get(variant, False) for variant in expected_variants)
    return success_by_seed_setting, normalized_variants


def _count_seed_asr_head_to_head(
    baseline_success: Dict[SeedSettingKey, bool],
    candidate_success: Dict[SeedSettingKey, bool],
) -> Dict[str, int]:
    counts = Counter(
        {
            "candidate_only_asr": 0,
            "baseline_only_asr": 0,
            "both_asr": 0,
            "neither_asr": 0,
        }
    )
    for key in sorted(set(baseline_success) | set(candidate_success)):
        baseline_ok = bool(baseline_success.get(key, False))
        candidate_ok = bool(candidate_success.get(key, False))
        if candidate_ok and baseline_ok:
            counts["both_asr"] += 1
        elif candidate_ok and not baseline_ok:
            counts["candidate_only_asr"] += 1
        elif baseline_ok and not candidate_ok:
            counts["baseline_only_asr"] += 1
        else:
            counts["neither_asr"] += 1
    return dict(counts)


def _shared_setting_summary(
    baseline_map: Dict[RecordKey, Dict[str, Any]],
    candidate_map: Dict[RecordKey, Dict[str, Any]],
    shared_keys: List[RecordKey],
) -> Dict[str, Dict[str, Any]]:
    keys_by_setting: Dict[str, List[RecordKey]] = defaultdict(list)
    for key in shared_keys:
        keys_by_setting[_setting_name_from_key(key)].append(key)

    summary: Dict[str, Dict[str, Any]] = {}
    for setting in sorted(keys_by_setting):
        setting_keys = sorted(keys_by_setting[setting])
        baseline_records = [baseline_map[key] for key in setting_keys]
        candidate_records = [candidate_map[key] for key in setting_keys]
        baseline_success, variants_by_setting = _seed_success_by_setting(baseline_map, setting_keys)
        candidate_success, _ = _seed_success_by_setting(candidate_map, setting_keys)

        baseline_passed = sum(int(bool(rec.get("pass"))) for rec in baseline_records)
        candidate_passed = sum(int(bool(rec.get("pass"))) for rec in candidate_records)
        baseline_asr_passed = sum(int(value) for value in baseline_success.values())
        candidate_asr_passed = sum(int(value) for value in candidate_success.values())

        summary[setting] = {
            "setting": setting,
            "record_count": len(setting_keys),
            "seed_count": len(baseline_success),
            "variants_considered": variants_by_setting[setting],
            "baseline_passed": baseline_passed,
            "candidate_passed": candidate_passed,
            "baseline_pass_rate": (baseline_passed / len(setting_keys)) if setting_keys else 0.0,
            "candidate_pass_rate": (candidate_passed / len(setting_keys)) if setting_keys else 0.0,
            "delta_pass_rate": ((candidate_passed - baseline_passed) / len(setting_keys)) if setting_keys else 0.0,
            "baseline_asr_success_seeds": baseline_asr_passed,
            "candidate_asr_success_seeds": candidate_asr_passed,
            "baseline_asr": (baseline_asr_passed / len(baseline_success)) if baseline_success else 0.0,
            "candidate_asr": (candidate_asr_passed / len(candidate_success)) if candidate_success else 0.0,
            "delta_asr": ((candidate_asr_passed - baseline_asr_passed) / len(baseline_success)) if baseline_success else 0.0,
            "record_head_to_head": _count_record_head_to_head(baseline_records, candidate_records),
            "seed_asr_head_to_head": _count_seed_asr_head_to_head(baseline_success, candidate_success),
        }
    return summary


def _motif_breakdown(
    seed_motif_index: Dict[str, Dict[str, Any]],
    baseline_map: Dict[RecordKey, Dict[str, Any]],
    candidate_map: Dict[RecordKey, Dict[str, Any]],
    shared_keys: List[RecordKey],
) -> Dict[str, Dict[str, Any]]:
    keys_by_motif: Dict[str, List[RecordKey]] = defaultdict(list)

    for key in shared_keys:
        seed_id = key[0]
        if seed_id not in seed_motif_index:
            continue
        keys_by_motif[seed_motif_index[seed_id]["base_label"]].append(key)

    motif_summary: Dict[str, Dict[str, Any]] = {}
    for motif in sorted(keys_by_motif):
        motif_keys = sorted(keys_by_motif[motif])
        baseline_records = [baseline_map[key] for key in motif_keys]
        candidate_records = [candidate_map[key] for key in motif_keys]
        baseline_success, _ = _seed_success_by_setting(baseline_map, motif_keys)
        candidate_success, _ = _seed_success_by_setting(candidate_map, motif_keys)
        seed_ids = sorted({key[0] for key in motif_keys})

        baseline_passed = sum(int(bool(rec.get("pass"))) for rec in baseline_records)
        candidate_passed = sum(int(bool(rec.get("pass"))) for rec in candidate_records)
        baseline_asr_passed = sum(int(value) for value in baseline_success.values())
        candidate_asr_passed = sum(int(value) for value in candidate_success.values())

        motif_summary[motif] = {
            "motif": motif,
            "seed_count": len(seed_ids),
            "record_count": len(motif_keys),
            "seed_setting_count": len(baseline_success),
            "has_order_seed_count": sum(int(seed_motif_index[seed_id]["has_order"]) for seed_id in seed_ids),
            "has_distinct_seed_count": sum(int(seed_motif_index[seed_id]["has_distinct"]) for seed_id in seed_ids),
            "baseline_pass_rate": (baseline_passed / len(motif_keys)) if motif_keys else 0.0,
            "candidate_pass_rate": (candidate_passed / len(motif_keys)) if motif_keys else 0.0,
            "delta_pass_rate": ((candidate_passed - baseline_passed) / len(motif_keys)) if motif_keys else 0.0,
            "baseline_asr": (baseline_asr_passed / len(baseline_success)) if baseline_success else 0.0,
            "candidate_asr": (candidate_asr_passed / len(candidate_success)) if candidate_success else 0.0,
            "delta_asr": ((candidate_asr_passed - baseline_asr_passed) / len(baseline_success)) if baseline_success else 0.0,
        }
    return motif_summary


def compare_reports(
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
    *,
    bench_root: Path | None = None,
) -> Dict[str, Any]:
    baseline_map = _record_map(baseline)
    candidate_map = _record_map(candidate)

    baseline_keys = set(baseline_map)
    candidate_keys = set(candidate_map)
    shared_keys = sorted(baseline_keys & candidate_keys)

    shared_setting_summary = _shared_setting_summary(baseline_map, candidate_map, shared_keys)
    aggregate_seed_asr = Counter(
        {
            "candidate_only_asr": 0,
            "baseline_only_asr": 0,
            "both_asr": 0,
            "neither_asr": 0,
        }
    )
    for item in shared_setting_summary.values():
        aggregate_seed_asr.update(item["seed_asr_head_to_head"])

    summary: Dict[str, Any] = {
        "baseline": _report_summary(baseline),
        "candidate": _report_summary(candidate),
        "shared_record_count": len(shared_keys),
        "baseline_only_record_count": len(baseline_keys - candidate_keys),
        "candidate_only_record_count": len(candidate_keys - baseline_keys),
        "record_head_to_head": _count_record_head_to_head(
            [baseline_map[key] for key in shared_keys],
            [candidate_map[key] for key in shared_keys],
        ),
        "seed_asr_head_to_head": dict(aggregate_seed_asr),
        "shared_setting_summary": shared_setting_summary,
        "baseline_failures": _representative_failures(baseline),
        "candidate_failures": _representative_failures(candidate),
    }

    if bench_root is not None:
        seed_motif_index = build_seed_motif_index(bench_root)
        summary["motif_taxonomy_summary"] = summarize_seed_motifs(seed_motif_index)
        summary["motif_breakdown"] = _motif_breakdown(
            seed_motif_index,
            baseline_map,
            candidate_map,
            shared_keys,
        )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline and candidate evaluation reports.")
    parser.add_argument("--baseline_report", required=True)
    parser.add_argument("--candidate_report", required=True)
    parser.add_argument("--bench_root", required=False)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    baseline = _load_json(Path(args.baseline_report))
    candidate = _load_json(Path(args.candidate_report))
    bench_root = Path(args.bench_root) if args.bench_root else None
    summary = compare_reports(baseline, candidate, bench_root=bench_root)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
