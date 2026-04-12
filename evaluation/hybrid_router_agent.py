from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from evaluation.llm_backend import create_llm_session
from evaluation.support_plan_agent.observable import build_observable_sketch
from evaluation.workspace_catalog import build_workspace_catalog, summarize_workspace, tokenize


ROOT = Path(__file__).resolve().parents[1]
HDR_PROJECT_ROOT = ROOT.parents[1]
HDRBENCH_MVP_ROOT = HDR_PROJECT_ROOT / "hdrbench_mvp"
DS_AGENT_ADAPTER = ROOT / "path_a_ds_agent" / "hdrbench_adapter.py"
SUPPORT_PATH_ADAPTER = ROOT / "evaluation" / "path_b_support_adapter.py"
PUBLIC_SOURCE_EXTS = {".csv", ".parquet", ".sqlite"}


@dataclass(slots=True)
class RouterFeatures:
    num_files: int
    num_sources: int
    file_obfuscation_ratio: float
    column_obfuscation_ratio: float
    max_join_overlap: float
    mean_top_join_overlap: float
    transform_edge_ratio: float
    has_transform_risk: bool
    same_source_proxy: bool
    filter_count: int
    time_filter_count: int
    output_count: int
    weak_join_graph: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_files": self.num_files,
            "num_sources": self.num_sources,
            "file_obfuscation_ratio": round(self.file_obfuscation_ratio, 4),
            "column_obfuscation_ratio": round(self.column_obfuscation_ratio, 4),
            "max_join_overlap": round(self.max_join_overlap, 4),
            "mean_top_join_overlap": round(self.mean_top_join_overlap, 4),
            "transform_edge_ratio": round(self.transform_edge_ratio, 4),
            "has_transform_risk": self.has_transform_risk,
            "same_source_proxy": self.same_source_proxy,
            "filter_count": self.filter_count,
            "time_filter_count": self.time_filter_count,
            "output_count": self.output_count,
            "weak_join_graph": self.weak_join_graph,
        }


def _is_obfuscated_name(name: str) -> bool:
    lower = str(name or "").strip().lower()
    return bool(
        re.fullmatch(r"(?:col|field|extra|dump|tmp|data|export)[_\-]?\d+", lower)
        or re.fullmatch(r"[kf]\d+", lower)
        or re.fullmatch(r"col_\d+", lower)
        or re.fullmatch(r"field_\d+", lower)
    )


def _iter_public_workspace_files(workspace: Path) -> List[Path]:
    return [
        fp
        for fp in sorted(workspace.iterdir())
        if fp.is_file() and fp.suffix.lower() in PUBLIC_SOURCE_EXTS
    ]


def _csv_has_content(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        df = pd.read_csv(path)
    except Exception:
        return path.stat().st_size > 0
    return len(df) > 0 or (len(df.columns) > 0 and path.stat().st_size > len(",".join(df.columns)) + 2)


def _normalize_output_csv_schema(output_csv: Path, required_columns: List[str]) -> None:
    if not output_csv.exists() or not required_columns:
        return
    try:
        df = pd.read_csv(output_csv)
    except Exception:
        return
    if all(col in df.columns for col in required_columns):
        normalized = df.loc[:, required_columns]
    elif len(df.columns) == len(required_columns):
        normalized = df.copy()
        normalized.columns = required_columns
    else:
        return
    if list(df.columns) != list(normalized.columns):
        normalized.to_csv(output_csv, index=False)


def _ensure_empty_output(output_csv: Path, required_columns: List[str]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    if not output_csv.exists():
        pd.DataFrame(columns=required_columns).to_csv(output_csv, index=False)


def _source_token_space(source) -> set[str]:
    tokens = set(tokenize(source.file_name))
    if source.table_name:
        tokens.update(tokenize(source.table_name))
    for col in source.columns:
        tokens.update(tokenize(col))
    for profile in source.column_profiles.values():
        for value in profile.sample_values[:3]:
            tokens.update(tokenize(str(value)))
    return tokens


def _best_source_for_text(catalog, text: str) -> str | None:
    target = set(tokenize(text))
    if not target:
        return None
    best_source_id: str | None = None
    best_score = -1.0
    for source in catalog.sources.values():
        source_tokens = _source_token_space(source)
        if not source_tokens:
            continue
        overlap = len(target & source_tokens)
        score = overlap / max(len(target), 1)
        if score > best_score:
            best_score = score
            best_source_id = source.source_id
    return best_source_id


def _same_source_proxy(catalog, observable_sketch) -> bool:
    output_sources = {
        _best_source_for_text(catalog, slot.label)
        for slot in observable_sketch.output_slots
    }
    output_sources.discard(None)
    filter_sources = {
        _best_source_for_text(catalog, str(item.get("attribute", "")))
        for item in observable_sketch.filter_hints
    }
    filter_sources.discard(None)
    if not filter_sources:
        return True
    if not output_sources:
        return False
    return filter_sources.issubset(output_sources)


def compute_router_features(
    instruction: str,
    workspace: Path,
    deliverable_spec: Dict[str, Any],
) -> Dict[str, Any]:
    workspace_files = _iter_public_workspace_files(workspace)
    catalog = build_workspace_catalog(workspace)
    observable_sketch = build_observable_sketch(
        instruction=instruction,
        deliverable_spec=deliverable_spec,
        session=None,
    )

    file_obfuscated = 0
    total_columns = 0
    obfuscated_columns = 0
    for source in catalog.sources.values():
        if _is_obfuscated_name(Path(source.file_name).stem) or _is_obfuscated_name(source.table_name or ""):
            file_obfuscated += 1
        for column_name in source.columns:
            total_columns += 1
            if _is_obfuscated_name(column_name):
                obfuscated_columns += 1

    all_edges = []
    seen_edges: set[str] = set()
    transform_edges = 0
    for source in catalog.sources.values():
        for edge in catalog.join_neighbors(source.source_id):
            if edge.edge_id in seen_edges:
                continue
            seen_edges.add(edge.edge_id)
            all_edges.append(edge)
            if edge.left_transform != "identity" or edge.right_transform != "identity":
                transform_edges += 1

    all_edges.sort(key=lambda edge: edge.overlap, reverse=True)
    top_edges = all_edges[: min(len(all_edges), 5)]
    mean_top_overlap = sum(edge.overlap for edge in top_edges) / max(len(top_edges), 1)
    max_overlap = top_edges[0].overlap if top_edges else 0.0
    transform_edge_ratio = transform_edges / max(len(all_edges), 1)
    has_transform_risk = transform_edges > 0

    features = RouterFeatures(
        num_files=len(workspace_files),
        num_sources=len(catalog.sources),
        file_obfuscation_ratio=file_obfuscated / max(len(catalog.sources), 1),
        column_obfuscation_ratio=obfuscated_columns / max(total_columns, 1),
        max_join_overlap=max_overlap,
        mean_top_join_overlap=mean_top_overlap,
        transform_edge_ratio=transform_edge_ratio,
        has_transform_risk=has_transform_risk,
        same_source_proxy=_same_source_proxy(catalog, observable_sketch),
        filter_count=len(observable_sketch.filter_hints),
        time_filter_count=len(observable_sketch.time_hints.get("years", [])) + len(observable_sketch.time_hints.get("months", [])),
        output_count=len(observable_sketch.output_slots),
        weak_join_graph=(not all_edges) or max_overlap < 0.45,
    )
    return {
        "features": features,
        "workspace_summary": summarize_workspace(workspace),
        "catalog": catalog,
        "observable_sketch": observable_sketch,
    }


def _decide_rule_route(features: RouterFeatures) -> Dict[str, Any]:
    simple_workspace = features.num_files <= 3 and features.num_sources <= 3
    low_obfuscation = features.file_obfuscation_ratio <= 0.34 and features.column_obfuscation_ratio <= 0.25
    strong_join_graph = features.max_join_overlap >= 0.68 or features.mean_top_join_overlap >= 0.56
    low_transform_risk = (not features.has_transform_risk) or features.transform_edge_ratio <= 0.12
    same_source_bias = features.same_source_proxy or features.filter_count == 0

    specialist_signals = [
        simple_workspace,
        low_obfuscation,
        strong_join_graph,
        low_transform_risk,
        same_source_bias,
    ]
    rbq_signals = [
        features.num_files >= 4,
        features.file_obfuscation_ratio >= 0.45,
        features.column_obfuscation_ratio >= 0.40,
        features.has_transform_risk,
        features.weak_join_graph,
        not features.same_source_proxy and features.filter_count > 0,
    ]
    specialist_votes = sum(1 for item in specialist_signals if item)
    rbq_votes = sum(1 for item in rbq_signals if item)

    if specialist_votes >= 4 and rbq_votes <= 1:
        selected = "path_a"
    elif rbq_votes >= 2:
        selected = "path_b"
    else:
        selected = "path_a" if specialist_votes >= rbq_votes else "path_b"

    return {
        "selected_path": selected,
        "router_type": "rule",
        "specialist_votes": specialist_votes,
        "rbq_votes": rbq_votes,
        "specialist_signals": {
            "simple_workspace": simple_workspace,
            "low_obfuscation": low_obfuscation,
            "strong_join_graph": strong_join_graph,
            "low_transform_risk": low_transform_risk,
            "same_source_bias": same_source_bias,
        },
        "rbq_signals": {
            "many_files": features.num_files >= 4,
            "file_name_obfuscation": features.file_obfuscation_ratio >= 0.45,
            "column_name_obfuscation": features.column_obfuscation_ratio >= 0.40,
            "transform_risk": features.has_transform_risk,
            "weak_join_graph": features.weak_join_graph,
            "cross_source_filter_risk": (not features.same_source_proxy and features.filter_count > 0),
        },
        "reason": (
            "Select specialist path for relatively clean/direct cases."
            if selected == "path_a"
            else "Select RBQ path for noisy/obfuscated/transform-heavy cases."
        ),
    }


_LLM_ROUTER_SYSTEM = """You are a router for a hybrid HDR-Bench agent.
Choose one path only:
- path_a: specialist optimized for simpler L0/L1-style cases with cleaner schemas and more direct joins.
- path_b: RBQ support-plan agent optimized for noisy L2/L3-style cases with obfuscated schema, transform-heavy joins, or latent support structure.

Return JSON only with keys:
- selected_path: "path_a" or "path_b"
- confidence: number in [0,1]
- reason: short string
- risk_flags: list of strings
"""


def _decide_llm_route(
    instruction: str,
    workspace_summary: Dict[str, Any],
    features: RouterFeatures,
    observable_sketch,
) -> Dict[str, Any]:
    session = create_llm_session("hybrid_router")
    if session is None or session.remaining_calls <= 0:
        fallback = _decide_rule_route(features)
        fallback["router_type"] = "llm_fallback_to_rule"
        return fallback

    prompt = textwrap.dedent(
        f"""
        Question:
        {instruction}

        Observable sketch:
        {json.dumps(observable_sketch.to_dict(), ensure_ascii=False, indent=2)}

        Router features:
        {json.dumps(features.to_dict(), ensure_ascii=False, indent=2)}

        Workspace summary:
        {json.dumps(workspace_summary, ensure_ascii=False, indent=2)}

        Decide which path should solve this case better.
        Prefer path_a when the case looks closer to clean/direct retrieval.
        Prefer path_b when the case looks noisy, schema-obfuscated, transform-heavy, or structurally latent.
        """
    ).strip()

    try:
        raw = session.chat_json(_LLM_ROUTER_SYSTEM, prompt, cache_namespace="hybrid_router_llm")
    except Exception as exc:
        fallback = _decide_rule_route(features)
        fallback["router_type"] = "llm_fallback_to_rule"
        fallback["llm_error"] = str(exc)
        return fallback

    selected = str(raw.get("selected_path", "")).strip().lower()
    if selected not in {"path_a", "path_b"}:
        selected = _decide_rule_route(features)["selected_path"]
    return {
        "selected_path": selected,
        "router_type": "llm",
        "confidence": float(raw.get("confidence", 0.0) or 0.0),
        "reason": str(raw.get("reason", "")),
        "risk_flags": [str(item) for item in raw.get("risk_flags", []) if str(item).strip()],
        "llm_calls_used": session.calls_used,
    }


def _stage_workspace_for_specialist(src: Path, dst: Path) -> List[str]:
    dst.mkdir(parents=True, exist_ok=True)
    copied: List[str] = []
    for fp in _iter_public_workspace_files(src):
        shutil.copy2(fp, dst / fp.name)
        copied.append(fp.name)
    return copied


def _run_ds_specialist(
    instruction: str,
    workspace: Path,
    deliverable_spec: Dict[str, Any],
    output_csv: Path,
) -> Dict[str, Any]:
    required_columns = list(deliverable_spec.get("required_columns", []))
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(HDRBENCH_MVP_ROOT),
            str(DS_AGENT_ADAPTER.parent),
            env.get("PYTHONPATH", ""),
        ]
    ).strip(os.pathsep)

    visible_files: List[str] = []
    proc: subprocess.CompletedProcess[str] | None = None
    error_text: str | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="rbq_hybrid_path_a_") as tmpdir:
            staged_workspace = Path(tmpdir) / "workspace"
            visible_files = _stage_workspace_for_specialist(workspace, staged_workspace)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(DS_AGENT_ADAPTER),
                    "--instruction",
                    instruction,
                    "--workspace",
                    str(staged_workspace),
                    "--deliverable-spec-json",
                    json.dumps(deliverable_spec, ensure_ascii=False),
                    "--output-csv",
                    str(output_csv),
                ],
                text=True,
                capture_output=True,
                env=env,
                timeout=900,
            )
    except subprocess.TimeoutExpired as exc:
        error_text = f"specialist timeout after {exc.timeout}s"
        proc = subprocess.CompletedProcess(
            args=exc.cmd,
            returncode=124,
            stdout=(exc.stdout or ""),
            stderr=(exc.stderr or ""),
        )
    except Exception as exc:  # noqa: BLE001
        error_text = str(exc)

    meta: Dict[str, Any] = {
        "success": bool(proc and proc.returncode == 0 and _csv_has_content(output_csv)),
        "files_touched": visible_files,
        "error": None if proc and proc.returncode == 0 else (error_text or ((proc.stderr or proc.stdout)[-4000:] if proc else "specialist launch failed")),
        "adapter_stdout": (proc.stdout[-4000:] if proc else ""),
        "adapter_stderr": (proc.stderr[-4000:] if proc else ""),
        "path_impl": "ds_agent_specialist",
    }
    if proc and proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout.strip().splitlines()[-1])
            if isinstance(parsed, dict):
                meta.update(parsed)
        except Exception:
            pass
    _normalize_output_csv_schema(output_csv, required_columns)
    if not _csv_has_content(output_csv):
        pd.DataFrame(columns=required_columns).to_csv(output_csv, index=False)
        meta["success"] = False
        if not meta.get("error"):
            meta["error"] = "specialist did not create a non-empty output csv"
    return meta


def _run_support_path(
    instruction: str,
    workspace: Path,
    deliverable_spec: Dict[str, Any],
    output_csv: Path,
    obligation_mode: str = "full",
) -> Dict[str, Any]:
    required_columns = list(deliverable_spec.get("required_columns", []))
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(ROOT),
            env.get("PYTHONPATH", ""),
        ]
    ).strip(os.pathsep)

    proc: subprocess.CompletedProcess[str] | None = None
    error_text: str | None = None
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(SUPPORT_PATH_ADAPTER),
                "--instruction",
                instruction,
                "--workspace",
                str(workspace),
                "--deliverable-spec-json",
                json.dumps(deliverable_spec, ensure_ascii=False),
                "--output-csv",
                str(output_csv),
                "--obligation-mode",
                obligation_mode,
            ],
            text=True,
            capture_output=True,
            env=env,
            timeout=1200,
        )
    except subprocess.TimeoutExpired as exc:
        error_text = f"support path timeout after {exc.timeout}s"
        proc = subprocess.CompletedProcess(
            args=exc.cmd,
            returncode=124,
            stdout=(exc.stdout or ""),
            stderr=(exc.stderr or ""),
        )
    except Exception as exc:  # noqa: BLE001
        error_text = str(exc)

    meta: Dict[str, Any] = {
        "success": bool(proc and proc.returncode == 0 and _csv_has_content(output_csv)),
        "files_touched": [],
        "error": None if proc and proc.returncode == 0 else (error_text or ((proc.stderr or proc.stdout)[-4000:] if proc else "support path launch failed")),
        "adapter_stdout": (proc.stdout[-4000:] if proc else ""),
        "adapter_stderr": (proc.stderr[-4000:] if proc else ""),
        "path_impl": "support_plan_subprocess",
    }
    if proc and proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout.strip().splitlines()[-1])
            if isinstance(parsed, dict):
                meta.update(parsed)
        except Exception:
            pass
    _normalize_output_csv_schema(output_csv, required_columns)
    if not _csv_has_content(output_csv):
        pd.DataFrame(columns=required_columns).to_csv(output_csv, index=False)
        meta["success"] = False
        if not meta.get("error"):
            meta["error"] = "support path did not create a non-empty output csv"
    return meta


def _compact_primary_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {
        "success": bool(meta.get("success")),
        "agent_impl": meta.get("agent_impl"),
        "path_impl": meta.get("path_impl"),
        "error": meta.get("error"),
        "files_touched": list(meta.get("files_touched", []) or []),
    }
    if meta.get("planner_output"):
        compact["planner_output"] = meta.get("planner_output")
    if meta.get("execution_summary"):
        compact["execution_summary"] = meta.get("execution_summary")
    if meta.get("search_summary"):
        compact["search_summary"] = meta.get("search_summary")
    for key in ("wall_clock_time", "llm_calls_used", "llm_calls_budget"):
        if key in meta:
            compact[key] = meta.get(key)
    return compact


def run_ds_specialist_agent(
    instruction: str,
    workspace: Path,
    deliverable_spec: Dict[str, Any],
    output_csv: Path,
) -> Dict[str, Any]:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    meta = _run_ds_specialist(
        instruction=instruction,
        workspace=workspace,
        deliverable_spec=deliverable_spec,
        output_csv=output_csv,
    )
    required_columns = list(deliverable_spec.get("required_columns", []))
    _normalize_output_csv_schema(output_csv, required_columns)
    _ensure_empty_output(output_csv, required_columns)
    meta.setdefault("agent_impl", "ds_specialist_agent")
    return meta


def run_hybrid_router_agent(
    instruction: str,
    workspace: Path,
    deliverable_spec: Dict[str, Any],
    output_csv: Path,
    router_type: str = "rule",
) -> Dict[str, Any]:
    if router_type not in {"rule", "llm"}:
        raise ValueError(f"Unsupported router_type: {router_type}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    feature_pack = compute_router_features(instruction, workspace, deliverable_spec)
    features: RouterFeatures = feature_pack["features"]
    workspace_summary = feature_pack["workspace_summary"]
    observable_sketch = feature_pack["observable_sketch"]

    if router_type == "rule":
        route = _decide_rule_route(features)
    else:
        route = _decide_llm_route(instruction, workspace_summary, features, observable_sketch)

    selected_path = route["selected_path"]
    required_columns = list(deliverable_spec.get("required_columns", []))
    if selected_path == "path_a":
        primary_meta = _run_ds_specialist(instruction, workspace, deliverable_spec, output_csv)
    else:
        primary_meta = _run_support_path(
            instruction=instruction,
            workspace=workspace,
            deliverable_spec=deliverable_spec,
            output_csv=output_csv,
            obligation_mode="full",
        )
    _normalize_output_csv_schema(output_csv, required_columns)
    _ensure_empty_output(output_csv, required_columns)

    return {
        "success": bool(primary_meta.get("success")) and _csv_has_content(output_csv),
        "files_touched": primary_meta.get("files_touched", []),
        "error": primary_meta.get("error"),
        "selected_path": selected_path,
        "router_type": router_type,
        "router_decision": route,
        "router_features": features.to_dict(),
        "planner_output": primary_meta.get("planner_output", {}),
        "execution_summary": primary_meta.get("execution_summary", {}),
        "primary_path_meta": _compact_primary_meta(primary_meta),
        "agent_impl": f"hybrid_router_{router_type}",
    }
