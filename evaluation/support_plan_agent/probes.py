from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd
from sqlglot import exp, parse_one

from construction.seed_tools import parse_sql_metadata
from evaluation.llm_backend import create_llm_session
from evaluation.scorer import score_single
from evaluation.workspace_catalog import WorkspaceCatalog, build_workspace_catalog, tokenize

from .compiler import compile_support_plan
from .ir import build_support_plan_ir
from .observable import build_observable_sketch
from .obligations import build_obligation_sketch
from .search import _best_measure_binding, _score_filter_binding, _score_output_binding, _score_support_source, _score_time_binding
from .types import AnchorPath, Binding, ObservableSketch, ObligationSketch, SupportPlan
from .utils import infer_operator_hints, normalize_operator_direction
from .verifier import obligations_from_trace, verify_support_plan


@dataclass(slots=True)
class GoldBinding:
    table_name: str
    canonical_column: str | None
    source_id: str | None
    dirty_column: str | None
    file_name: str | None
    kind: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GoldTargets:
    output_bindings_by_label: Dict[str, List[GoldBinding]]
    filter_bindings: List[GoldBinding]
    measure_bindings: List[GoldBinding]
    evidence_bindings: List[GoldBinding]
    join_pairs: List[Dict[str, Any]]
    output_tables: List[str]
    evidence_tables: List[str]
    filter_kind_tags: List[str]
    primary_filter_kind: str
    ambiguous_count_star: bool
    has_aggregation: bool
    has_order: bool
    has_limit: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_bindings_by_label": {
                label: [binding.to_dict() for binding in bindings]
                for label, bindings in self.output_bindings_by_label.items()
            },
            "filter_bindings": [binding.to_dict() for binding in self.filter_bindings],
            "measure_bindings": [binding.to_dict() for binding in self.measure_bindings],
            "evidence_bindings": [binding.to_dict() for binding in self.evidence_bindings],
            "join_pairs": list(self.join_pairs),
            "output_tables": list(self.output_tables),
            "evidence_tables": list(self.evidence_tables),
            "filter_kind_tags": list(self.filter_kind_tags),
            "primary_filter_kind": self.primary_filter_kind,
            "ambiguous_count_star": self.ambiguous_count_star,
            "has_aggregation": self.has_aggregation,
            "has_order": self.has_order,
            "has_limit": self.has_limit,
        }


@dataclass(slots=True)
class CaseContext:
    seed_id: str
    variant: str
    split: str
    view: str
    instruction: str
    workspace: Path
    gold_path: Path
    deliverable_spec: Dict[str, Any]
    manifest_public: Dict[str, Any]
    manifest_private: Dict[str, Any]
    catalog: WorkspaceCatalog
    observable_sketch: ObservableSketch
    obligation_sketch: ObligationSketch
    sketch_mode: str
    gold_targets: GoldTargets

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed_id": self.seed_id,
            "variant": self.variant,
            "split": self.split,
            "view": self.view,
            "instruction": self.instruction,
            "workspace": str(self.workspace),
            "gold_path": str(self.gold_path),
            "deliverable_spec": dict(self.deliverable_spec),
            "sketch_mode": self.sketch_mode,
            "observable_sketch": self.observable_sketch.to_dict(),
            "obligation_sketch": self.obligation_sketch.to_dict(),
            "gold_targets": self.gold_targets.to_dict(),
        }


@dataclass(slots=True)
class ProbeConfig:
    name: str
    output_binding_top_k: int = 3
    output_plan_top_k: int = 6
    support_top_k: int = 4
    max_hops: int = 2
    oracle_output: bool = False
    oracle_filter: bool = False
    oracle_evidence_path: bool = False
    oracle_measure: bool = False
    joint_rerank: bool = False
    obligation_hard: bool = False
    typed_filter_strict: bool = False


def _resolve_workspace(manifest_public: Dict[str, Any], split: str, view: str) -> Path:
    split_views = manifest_public.get("splits", {})
    if split in split_views and view in split_views[split]:
        return Path(split_views[split][view])
    if split == "l3" and view in manifest_public.get("views", {}):
        return Path(manifest_public["views"][view])
    raise KeyError(f"Workspace not found for split={split}, view={view}")


def _load_registry_for_split(manifest_private: Dict[str, Any], workspace: Path, split: str) -> Dict[str, Dict[str, Any]]:
    if split == "l0":
        manifest_l0 = workspace / "manifest_l0.json"
        if not manifest_l0.exists():
            raise FileNotFoundError(f"Missing manifest_l0.json under {workspace}")
        return pd.read_json(manifest_l0, typ="series")["table_registry"]  # type: ignore[index]
    return manifest_private.get("table_registry_by_split", {}).get(split, {})


def _load_column_mapping_for_split(manifest_private: Dict[str, Any], split: str) -> Dict[str, Dict[str, str]]:
    if split == "l0":
        return {}
    return {
        table_name: {str(canonical): str(dirty) for canonical, dirty in mapping.items()}
        for table_name, mapping in manifest_private.get("column_mapping_by_split", {}).get(split, {}).items()
    }


def _source_id_for_entry(table_name: str, entry: Dict[str, Any]) -> str:
    storage_type = str(entry.get("storage_type", "csv")).lower()
    file_name = str(entry.get("file", ""))
    if storage_type == "sqlite":
        return f"{file_name}::{entry.get('table_name', table_name)}"
    return f"{file_name}::{Path(file_name).stem}"


def _dirty_column_name(table_name: str, canonical_column: str, column_mapping: Dict[str, Dict[str, str]]) -> str:
    return str(column_mapping.get(table_name, {}).get(canonical_column, canonical_column))


def _resolve_table(alias_or_name: str | None, alias_map: Dict[str, str]) -> str | None:
    if not alias_or_name:
        return None
    return alias_map.get(alias_or_name, alias_or_name)


def _unwrap_alias(node: exp.Expression) -> exp.Expression:
    if isinstance(node, exp.Alias):
        return node.this
    return node


def _column_refs(node: exp.Expression | None, alias_map: Dict[str, str]) -> List[Tuple[str, str]]:
    if node is None:
        return []
    refs: List[Tuple[str, str]] = []
    for col in node.find_all(exp.Column):
        table_name = _resolve_table(col.table, alias_map)
        if table_name:
            refs.append((table_name, col.name))
    return refs


def _table_names_from_refs(refs: Iterable[Tuple[str, str]]) -> List[str]:
    return sorted({table for table, _ in refs})


def _has_boolean_or_null_predicate(tree: exp.Expression) -> bool:
    return any(
        isinstance(node, (exp.Is, exp.Boolean))
        or node.key in {"is", "not"}
        for node in tree.walk()
    )


def _has_date_like_predicate(tree: exp.Expression, instruction: str) -> bool:
    lower = instruction.lower()
    if any(token in lower for token in ["date", "year", "month", "time", "earliest", "latest"]):
        return True
    for node in tree.find_all(exp.Column):
        name = node.name.lower()
        if any(token in name for token in ["date", "year", "month", "time"]):
            return True
    for node in tree.find_all(exp.Literal):
        if not node.is_string:
            continue
        value = str(node.this)
        if "-" in value or "/" in value:
            return True
    return False


def classify_filter_kind(sql: str, instruction: str) -> Dict[str, Any]:
    tree = parse_one(sql, read="sqlite")
    lower = instruction.lower()
    tags: List[str] = []
    where = tree.args.get("where")
    having = tree.args.get("having")
    order = tree.args.get("order")
    has_limit = tree.args.get("limit") is not None

    predicate_nodes: List[exp.Expression] = []
    if where is not None:
        predicate_nodes.append(where)
    if having is not None:
        predicate_nodes.append(having)

    if any(_has_boolean_or_null_predicate(node) for node in predicate_nodes):
        tags.append("null/boolean")
    if any(_has_date_like_predicate(node, instruction) for node in predicate_nodes):
        tags.append("time")
    if any(
        isinstance(node, (exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between))
        or (isinstance(node, exp.EQ) and any(isinstance(child, exp.Literal) and not child.is_string for child in node.args.values()))
        for predicate in predicate_nodes
        for node in predicate.walk()
    ):
        tags.append("numeric")
    if order is not None or has_limit or any(token in lower for token in ["least", "fewest", "most", "highest", "lowest", "top"]):
        tags.append("ordering/superlative")
    if any(isinstance(node, (exp.Like, exp.ILike)) or isinstance(node, exp.EQ) for predicate in predicate_nodes for node in predicate.walk()):
        tags.append("text")

    deduped = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    primary = deduped[0] if deduped else "none"
    return {"primary": primary, "tags": deduped or ["none"]}


def _make_gold_binding(
    table_name: str,
    canonical_column: str | None,
    registry: Dict[str, Dict[str, Any]],
    column_mapping: Dict[str, Dict[str, str]],
    kind: str,
) -> GoldBinding | None:
    table_entry = registry.get(table_name)
    if table_entry is None:
        return None
    file_name = str(table_entry.get("file", ""))
    source_id = _source_id_for_entry(table_name, table_entry)
    dirty_column = None if canonical_column is None else _dirty_column_name(table_name, canonical_column, column_mapping)
    return GoldBinding(
        table_name=table_name,
        canonical_column=canonical_column,
        source_id=source_id,
        dirty_column=dirty_column,
        file_name=file_name,
        kind=kind,
    )


def _resolve_gold_source(context: CaseContext, binding: GoldBinding):
    if binding.source_id is not None and binding.source_id in context.catalog.sources:
        return context.catalog.source(binding.source_id)
    for source in context.catalog.sources.values():
        if binding.file_name and source.file_name == binding.file_name:
            if binding.table_name and source.table_name == binding.table_name:
                return source
        if binding.table_name and source.table_name == binding.table_name:
            return source
    return None


def _resolve_gold_column(source, binding: GoldBinding) -> str | None:
    candidate_names = [binding.dirty_column, binding.canonical_column]
    lowered = {column.lower(): column for column in source.columns}
    for candidate in candidate_names:
        if candidate is None:
            continue
        if candidate in source.columns:
            return candidate
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def extract_gold_targets(
    manifest_private: Dict[str, Any],
    deliverable_spec: Dict[str, Any],
    split: str,
    workspace: Path,
    instruction: str,
) -> GoldTargets:
    sql = str(manifest_private["gold_sql"])
    tree = parse_one(sql, read="sqlite")
    sql_meta = parse_sql_metadata(sql)
    registry = _load_registry_for_split(manifest_private, workspace, split)
    column_mapping = _load_column_mapping_for_split(manifest_private, split)
    alias_map = dict(sql_meta.get("alias_map", {}))

    required_columns = [str(column) for column in deliverable_spec.get("required_columns", [])]
    output_bindings_by_label: Dict[str, List[GoldBinding]] = {label: [] for label in required_columns}
    output_tables: List[str] = []
    measure_bindings: List[GoldBinding] = []
    ambiguous_count_star = False

    select_exprs = list(tree.expressions)
    for label, select_expr in zip(required_columns, select_exprs):
        inner = _unwrap_alias(select_expr)
        refs = _column_refs(inner, alias_map)
        if isinstance(inner, exp.Column) and refs:
            table_name, column_name = refs[0]
            binding = _make_gold_binding(table_name, column_name, registry, column_mapping, kind="output")
            if binding is not None:
                output_bindings_by_label[label].append(binding)
                output_tables.append(table_name)
            continue

        if any(isinstance(node, exp.AggFunc) for node in inner.walk()):
            agg_cols = []
            for agg_node in inner.walk():
                if isinstance(agg_node, exp.AggFunc):
                    agg_cols.extend(_column_refs(agg_node, alias_map))
            if agg_cols:
                for table_name, column_name in agg_cols:
                    binding = _make_gold_binding(table_name, column_name, registry, column_mapping, kind="measure")
                    if binding is not None:
                        measure_bindings.append(binding)
            else:
                ambiguous_count_star = True

    if not measure_bindings:
        agg_refs = []
        saw_agg = False
        for node in tree.walk():
            if isinstance(node, exp.AggFunc):
                saw_agg = True
                agg_refs.extend(_column_refs(node, alias_map))
        if agg_refs:
            for table_name, column_name in agg_refs:
                binding = _make_gold_binding(table_name, column_name, registry, column_mapping, kind="measure")
                if binding is not None:
                    measure_bindings.append(binding)
        elif saw_agg:
            ambiguous_count_star = True

    where_refs = _column_refs(tree.args.get("where"), alias_map)
    having_refs = _column_refs(tree.args.get("having"), alias_map)
    group_refs = _column_refs(tree.args.get("group"), alias_map)

    filter_bindings: List[GoldBinding] = []
    for table_name, column_name in where_refs + having_refs:
        binding = _make_gold_binding(table_name, column_name, registry, column_mapping, kind="filter")
        if binding is not None:
            filter_bindings.append(binding)

    evidence_tables = sorted(
        {
            *(_table_names_from_refs(where_refs)),
            *(_table_names_from_refs(having_refs)),
            *(_table_names_from_refs(group_refs)),
            *(binding.table_name for binding in measure_bindings),
        }
    )
    evidence_tables = [table_name for table_name in evidence_tables if table_name not in output_tables]

    if not evidence_tables and ambiguous_count_star:
        candidate_tables = [table_name for table_name in sql_meta.get("tables", []) if table_name not in output_tables]
        evidence_tables = candidate_tables

    evidence_bindings: List[GoldBinding] = []
    for table_name in evidence_tables:
        binding = _make_gold_binding(table_name, None, registry, column_mapping, kind="evidence")
        if binding is not None:
            evidence_bindings.append(binding)

    filter_kind = classify_filter_kind(sql, instruction)
    return GoldTargets(
        output_bindings_by_label=output_bindings_by_label,
        filter_bindings=filter_bindings,
        measure_bindings=measure_bindings,
        evidence_bindings=evidence_bindings,
        join_pairs=list(sql_meta.get("joins", [])),
        output_tables=sorted(set(output_tables)),
        evidence_tables=[binding.table_name for binding in evidence_bindings],
        filter_kind_tags=list(filter_kind["tags"]),
        primary_filter_kind=str(filter_kind["primary"]),
        ambiguous_count_star=ambiguous_count_star,
        has_aggregation=bool(measure_bindings or ambiguous_count_star or tree.args.get("group") is not None or tree.args.get("having") is not None),
        has_order=tree.args.get("order") is not None,
        has_limit=tree.args.get("limit") is not None,
    )


def prepare_case_context(
    manifest_public: Dict[str, Any],
    manifest_private: Dict[str, Any],
    split: str,
    view: str,
    *,
    sketch_mode: str = "fallback",
    namespace: str = "support_plan_probe",
) -> CaseContext:
    workspace = _resolve_workspace(manifest_public, split, view)
    catalog = build_workspace_catalog(workspace)

    session = create_llm_session(namespace) if sketch_mode == "live" else None
    observable_sketch = build_observable_sketch(
        instruction=manifest_public.get("instruction", ""),
        deliverable_spec=manifest_public.get("deliverable_spec", {}),
        session=session,
    )
    obligation_sketch = build_obligation_sketch(
        instruction=manifest_public.get("instruction", ""),
        observable_sketch=observable_sketch,
        session=session,
    )
    actual_mode = "live"
    if observable_sketch.raw_response.get("fallback") or obligation_sketch.raw_response.get("fallback"):
        actual_mode = "fallback"
    gold_targets = extract_gold_targets(
        manifest_private=manifest_private,
        deliverable_spec=manifest_public.get("deliverable_spec", {}),
        split=split,
        workspace=workspace,
        instruction=manifest_public.get("instruction", ""),
    )
    return CaseContext(
        seed_id=str(manifest_private.get("seed_id", manifest_public.get("seed_id", ""))),
        variant=str(manifest_public.get("variant", manifest_private.get("variant", "A"))),
        split=split,
        view=view,
        instruction=str(manifest_public.get("instruction", "")),
        workspace=workspace,
        gold_path=Path(manifest_public["gold_path"]),
        deliverable_spec=dict(manifest_public.get("deliverable_spec", {})),
        manifest_public=manifest_public,
        manifest_private=manifest_private,
        catalog=catalog,
        observable_sketch=observable_sketch,
        obligation_sketch=obligation_sketch,
        sketch_mode=actual_mode,
        gold_targets=gold_targets,
    )


def _rank_output_bindings(context: CaseContext, top_k: int) -> Dict[str, List[Binding]]:
    question_tokens = tokenize(context.instruction)
    ranked: Dict[str, List[Binding]] = {}
    for slot in context.observable_sketch.output_slots:
        candidates: List[Binding] = []
        for source in context.catalog.sources.values():
            for column_name in source.columns:
                score, reasons = _score_output_binding(
                    slot,
                    source,
                    column_name,
                    question_tokens,
                    observable_sketch=context.observable_sketch,
                    catalog=context.catalog,
                )
                candidates.append(
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name=column_name,
                        role=slot.role,
                        score=float(score),
                        reasons=reasons,
                        metadata={"slot_label": slot.label},
                    )
                )
        candidates.sort(key=lambda item: item.score, reverse=True)
        ranked[slot.label] = candidates[:top_k]
    return ranked


def _rank_filter_candidates(context: CaseContext, top_k: int, *, strict_types: bool = False) -> List[List[Binding]]:
    question_tokens = tokenize(context.instruction)
    outputs: List[List[Binding]] = []
    for filter_hint in context.observable_sketch.filter_hints:
        candidates: List[Binding] = []
        for source in context.catalog.sources.values():
            for column_name in source.columns:
                profile = source.column_profiles[column_name]
                raw_value = filter_hint.get("value")
                numeric_value = None
                if isinstance(raw_value, (int, float)):
                    numeric_value = float(raw_value)
                elif isinstance(raw_value, str):
                    try:
                        numeric_value = float(raw_value)
                    except Exception:
                        numeric_value = None
                if strict_types and numeric_value is not None and not (profile.numeric_ratio >= 0.5 or profile.measure_like):
                    continue
                score, reasons = _score_filter_binding(filter_hint, source, column_name, question_tokens)
                candidates.append(
                    Binding(
                        source_id=source.source_id,
                        file_name=source.file_name,
                        view_name=source.raw_view_name,
                        column_name=column_name,
                        role="filter",
                        score=float(score),
                        reasons=reasons,
                        metadata=dict(filter_hint),
                    )
                )
        candidates.sort(key=lambda item: item.score, reverse=True)
        outputs.append(candidates[:top_k])
    return outputs


def _rank_time_candidates(context: CaseContext, top_k: int, *, strict_types: bool = False) -> List[Binding]:
    if not (context.observable_sketch.time_hints.get("years") or context.observable_sketch.time_hints.get("months")):
        return []
    candidates: List[Binding] = []
    for source in context.catalog.sources.values():
        for column_name in source.columns:
            profile = source.column_profiles[column_name]
            if strict_types and not profile.time_like and not any(token in column_name.lower() for token in ["date", "year", "time", "month"]):
                continue
            score, reasons = _score_time_binding(source, column_name)
            candidates.append(
                Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name=column_name,
                    role="time",
                    score=float(score),
                    reasons=reasons,
                    metadata=dict(context.observable_sketch.time_hints),
                )
            )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:top_k]


def _rank_support_candidates(
    context: CaseContext,
    output_source_id: str,
    *,
    top_k: int,
    max_hops: int,
) -> List[Tuple[Binding, AnchorPath | None, float]]:
    question_tokens = tokenize(context.instruction)
    ranked: List[Tuple[Binding, AnchorPath | None, float]] = []
    for source in context.catalog.sources.values():
        if max_hops == 2:
            support_score, reasons, anchor_path = _score_support_source(
                source,
                output_source_id,
                context.obligation_sketch,
                context.observable_sketch,
                context.catalog,
                question_tokens,
            )
        else:
            score = 0.0
            reasons: List[str] = []
            if source.role_hint == "fact":
                score += 5.0
                reasons.append("fact_source_bonus")
            elif source.role_hint == "dimension":
                score -= 1.5
            source_tokens = set(tokenize(f"{source.file_name} {source.table_name or ''} {' '.join(source.columns)}"))
            if source_tokens:
                score += (len(set(question_tokens) & source_tokens) / len(source_tokens)) * 4.0
            if context.observable_sketch.time_hints.get("years") or context.observable_sketch.time_hints.get("months"):
                if any(profile.time_like for profile in source.column_profiles.values()):
                    score += 2.0
                    reasons.append("has_time_evidence")
            if context.observable_sketch.filter_hints:
                if any(profile.measure_like or profile.time_like for profile in source.column_profiles.values()):
                    score += 1.5
                    reasons.append("can_host_filters")
            path_edges = context.catalog.find_best_path(source.source_id, output_source_id, max_hops=max_hops)
            if source.source_id == output_source_id:
                anchor_path = AnchorPath(path_source_ids=[source.source_id], edges=[], score=1.0, notes=["same_source"])
            elif path_edges:
                anchor_score = sum(edge.overlap for edge in path_edges)
                score += anchor_score * 8.0
                reasons.append("anchor_path_found")
                anchor_path = AnchorPath(
                    path_source_ids=[source.source_id, output_source_id],
                    edges=[asdict(edge) for edge in path_edges],
                    score=float(anchor_score),
                    notes=[f"max_hops_{max_hops}"],
                )
            else:
                anchor_path = None
                score -= 4.0
            if context.obligation_sketch.probability("support_relation") >= 0.45 and source.source_id == output_source_id:
                score -= 2.0
                reasons.append("same_source_penalty")
            support_score = score
        candidate_column = source.key_columns[0] if source.key_columns else source.columns[0]
        ranked.append(
            (
                Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name=candidate_column,
                    role="support",
                    score=float(support_score),
                    reasons=reasons,
                    metadata={},
                ),
                anchor_path,
                float(support_score),
            )
        )
    ranked.sort(key=lambda item: item[2], reverse=True)
    return ranked[:top_k]


def _probe_config(probe_name: str) -> ProbeConfig:
    mapping = {
        "baseline": ProbeConfig(name="baseline"),
        "oracle_output": ProbeConfig(name="oracle_output", oracle_output=True),
        "oracle_filter": ProbeConfig(name="oracle_filter", oracle_filter=True),
        "oracle_evidence_path": ProbeConfig(name="oracle_evidence_path", oracle_evidence_path=True),
        "oracle_measure_anchor": ProbeConfig(name="oracle_measure_anchor", oracle_evidence_path=True, oracle_measure=True),
        "oracle_all": ProbeConfig(name="oracle_all", oracle_output=True, oracle_filter=True, oracle_evidence_path=True, oracle_measure=True),
        "sensitivity_topk_hops": ProbeConfig(name="sensitivity_topk_hops", output_binding_top_k=10, output_plan_top_k=10, support_top_k=6, max_hops=3),
        "joint_rerank": ProbeConfig(name="joint_rerank", output_binding_top_k=10, output_plan_top_k=10, support_top_k=6, max_hops=3, joint_rerank=True),
        "obligation_hard": ProbeConfig(name="obligation_hard", output_binding_top_k=10, output_plan_top_k=10, support_top_k=6, max_hops=3, obligation_hard=True),
        "typed_filter_strict": ProbeConfig(name="typed_filter_strict", output_binding_top_k=10, output_plan_top_k=10, support_top_k=6, max_hops=3, typed_filter_strict=True),
    }
    if probe_name not in mapping:
        raise ValueError(f"Unsupported probe: {probe_name}")
    return mapping[probe_name]


def _build_output_combos(
    context: CaseContext,
    *,
    binding_top_k: int,
    combo_top_k: int,
    max_hops: int,
    oracle_output: bool = False,
) -> List[Tuple[List[Binding], List[AnchorPath], float]]:
    question_tokens = tokenize(context.instruction)
    if oracle_output:
        ordered_bindings: List[Binding] = []
        for slot in context.observable_sketch.output_slots:
            gold_bindings = context.gold_targets.output_bindings_by_label.get(slot.label, [])
            if not gold_bindings:
                return []
            chosen = gold_bindings[0]
            source = _resolve_gold_source(context, chosen)
            if source is None:
                return []
            resolved_column = _resolve_gold_column(source, chosen)
            if resolved_column is None:
                return []
                score, reasons = _score_output_binding(
                    slot,
                    source,
                    resolved_column,
                    question_tokens,
                    observable_sketch=context.observable_sketch,
                    catalog=context.catalog,
                )
            ordered_bindings.append(
                Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name=resolved_column,
                    role=slot.role,
                    score=float(score),
                    reasons=reasons + ["oracle_output"],
                    metadata={"slot_label": slot.label},
                )
            )
        combo_score = sum(binding.score for binding in ordered_bindings)
        join_paths: List[AnchorPath] = []
        primary_source_id = ordered_bindings[0].source_id
        for binding in ordered_bindings[1:]:
            if binding.source_id == primary_source_id:
                continue
            path_edges = context.catalog.find_best_path(primary_source_id, binding.source_id, max_hops=max_hops)
            if not path_edges:
                return []
            join_paths.append(
                AnchorPath(
                    path_source_ids=[primary_source_id, binding.source_id],
                    edges=[asdict(edge) for edge in path_edges],
                    score=float(sum(edge.overlap for edge in path_edges)),
                    notes=["oracle_output_join_path"],
                )
            )
        return [(ordered_bindings, join_paths, combo_score)]

    binding_options = _rank_output_bindings(context, top_k=binding_top_k)
    slot_order = [slot.label for slot in context.observable_sketch.output_slots]
    combos: List[Tuple[List[Binding], List[AnchorPath], float]] = []
    for tuple_bindings in product(*[binding_options[label] for label in slot_order]):
        bindings = list(tuple_bindings)
        combo_score = sum(binding.score for binding in bindings)
        join_paths: List[AnchorPath] = []
        primary_source_id = bindings[0].source_id
        connected = True
        for binding in bindings[1:]:
            if binding.source_id == primary_source_id:
                continue
            path_edges = context.catalog.find_best_path(primary_source_id, binding.source_id, max_hops=max_hops)
            if not path_edges:
                connected = False
                combo_score -= 6.0
                break
            join_paths.append(
                AnchorPath(
                    path_source_ids=[primary_source_id, binding.source_id],
                    edges=[asdict(edge) for edge in path_edges],
                    score=float(sum(edge.overlap for edge in path_edges)),
                    notes=[f"output_join_path_max_hops_{max_hops}"],
                )
            )
            combo_score += sum(edge.overlap for edge in path_edges) * 6.0
        if connected:
            combos.append((bindings, join_paths, combo_score))
    combos.sort(key=lambda item: item[2], reverse=True)
    return combos[:combo_top_k]


def _default_filter_bindings(
    context: CaseContext,
    candidate_source_ids: List[str],
    *,
    strict_types: bool = False,
) -> List[Binding]:
    question_tokens = tokenize(context.instruction)
    sources = [context.catalog.sources[source_id] for source_id in candidate_source_ids if source_id in context.catalog.sources]
    bindings: List[Binding] = []
    for filter_hint in context.observable_sketch.filter_hints:
        best: Binding | None = None
        for source in sources:
            for column_name in source.columns:
                profile = source.column_profiles[column_name]
                raw_value = filter_hint.get("value")
                numeric_value = None
                if isinstance(raw_value, (int, float)):
                    numeric_value = float(raw_value)
                elif isinstance(raw_value, str):
                    try:
                        numeric_value = float(raw_value)
                    except Exception:
                        numeric_value = None
                if strict_types and numeric_value is not None and not (profile.numeric_ratio >= 0.5 or profile.measure_like):
                    continue
                score, reasons = _score_filter_binding(filter_hint, source, column_name, question_tokens)
                candidate = Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name=column_name,
                    role="filter",
                    score=float(score),
                    reasons=reasons,
                    metadata=dict(filter_hint),
                )
                if best is None or candidate.score > best.score:
                    best = candidate
        if best is not None:
            bindings.append(best)
    if context.observable_sketch.time_hints.get("years") or context.observable_sketch.time_hints.get("months"):
        best_time: Binding | None = None
        for source in sources:
            for column_name in source.columns:
                profile = source.column_profiles[column_name]
                if strict_types and not profile.time_like and not any(token in column_name.lower() for token in ["date", "year", "time", "month"]):
                    continue
                score, reasons = _score_time_binding(source, column_name)
                candidate = Binding(
                    source_id=source.source_id,
                    file_name=source.file_name,
                    view_name=source.raw_view_name,
                    column_name=column_name,
                    role="time",
                    score=float(score),
                    reasons=reasons,
                    metadata=dict(context.observable_sketch.time_hints),
                )
                if best_time is None or candidate.score > best_time.score:
                    best_time = candidate
        if best_time is not None:
            bindings.append(best_time)
    return bindings


def _oracle_filter_bindings(context: CaseContext) -> List[Binding]:
    bindings: List[Binding] = []
    for binding in context.gold_targets.filter_bindings:
        source = _resolve_gold_source(context, binding)
        if source is None:
            continue
        resolved_column = _resolve_gold_column(source, binding)
        if resolved_column is None:
            continue
        bindings.append(
            Binding(
                source_id=source.source_id,
                file_name=source.file_name,
                view_name=source.raw_view_name,
                column_name=resolved_column,
                role="filter",
                score=100.0,
                reasons=["oracle_filter"],
                metadata={},
            )
        )
    return bindings


def _oracle_measure_binding(context: CaseContext, support_source_id: str | None) -> Binding | None:
    if support_source_id is None:
        return None
    for binding in context.gold_targets.measure_bindings:
        source = _resolve_gold_source(context, binding)
        if source is None or source.source_id != support_source_id:
            continue
        resolved_column = _resolve_gold_column(source, binding)
        if resolved_column is not None:
            return Binding(
                source_id=source.source_id,
                file_name=source.file_name,
                view_name=source.raw_view_name,
                column_name=resolved_column,
                role="measure",
                score=100.0,
                reasons=["oracle_measure"],
                metadata={"aggregation": infer_operator_hints(context.instruction).get("aggregation")},
            )
    return None


def _global_consistency_bonus(plan: SupportPlan, context: CaseContext) -> float:
    bonus = 0.0
    if plan.output_bindings:
        bonus += 1.5
    if context.obligation_sketch.probability("support_relation") >= 0.45:
        if plan.support_binding is not None and plan.anchor_binding is not None:
            bonus += 3.0 + (plan.anchor_binding.score * 4.0)
        else:
            bonus -= 5.0
    if context.observable_sketch.filter_hints or context.observable_sketch.time_hints.get("years") or context.observable_sketch.time_hints.get("months"):
        bonus += 1.5 if plan.filter_bindings else -2.0
    if context.obligation_sketch.probability("aggregation_support") >= 0.45:
        bonus += 1.5 if (plan.measure_binding is not None or plan.operator_plan.get("aggregation") == "count") else -2.0
    bonus -= len(plan.unmet_obligations) * 2.5
    return bonus


def _build_plan_candidates(context: CaseContext, config: ProbeConfig) -> List[SupportPlan]:
    output_combos = _build_output_combos(
        context,
        binding_top_k=config.output_binding_top_k,
        combo_top_k=config.output_plan_top_k,
        max_hops=config.max_hops,
        oracle_output=config.oracle_output,
    )
    if not output_combos:
        return []

    operator_plan = infer_operator_hints(context.instruction)
    if context.observable_sketch.order_hint:
        if context.observable_sketch.order_hint.get("direction") and not operator_plan.get("direction"):
            od = normalize_operator_direction(context.observable_sketch.order_hint["direction"])
            if od:
                operator_plan["direction"] = od
        if context.observable_sketch.order_hint.get("limit") and not operator_plan.get("limit"):
            operator_plan["limit"] = context.observable_sketch.order_hint["limit"]
        if context.observable_sketch.order_hint.get("target"):
            operator_plan.setdefault("target", context.observable_sketch.order_hint["target"])

    support_required = context.obligation_sketch.probability("support_relation") >= 0.45
    plans: List[SupportPlan] = []

    for output_bindings, output_join_paths, output_score in output_combos:
        primary_output_source_id = output_bindings[0].source_id
        support_candidates: List[Tuple[Binding | None, AnchorPath | None, float]]
        if config.oracle_evidence_path and context.gold_targets.evidence_bindings:
            support_candidates = []
            for gold_binding in context.gold_targets.evidence_bindings:
                source = _resolve_gold_source(context, gold_binding)
                if source is None:
                    continue
                candidate_column = source.key_columns[0] if source.key_columns else source.columns[0]
                path_edges = context.catalog.find_best_path(source.source_id, primary_output_source_id, max_hops=config.max_hops)
                if source.source_id == primary_output_source_id:
                    anchor_path = AnchorPath(path_source_ids=[source.source_id], edges=[], score=1.0, notes=["oracle_same_source"])
                elif path_edges:
                    anchor_path = AnchorPath(
                        path_source_ids=[source.source_id, primary_output_source_id],
                        edges=[asdict(edge) for edge in path_edges],
                        score=float(sum(edge.overlap for edge in path_edges)),
                        notes=["oracle_evidence_path"],
                    )
                else:
                    anchor_path = None
                support_candidates.append(
                    (
                        Binding(
                            source_id=source.source_id,
                            file_name=source.file_name,
                            view_name=source.raw_view_name,
                            column_name=candidate_column,
                            role="support",
                            score=100.0 if anchor_path is not None else -100.0,
                            reasons=["oracle_evidence_path"],
                            metadata={},
                        ),
                        anchor_path,
                        100.0 if anchor_path is not None else -100.0,
                    )
                )
            if not support_candidates and support_required:
                continue
        elif support_required:
            support_candidates = _rank_support_candidates(
                context,
                primary_output_source_id,
                top_k=config.support_top_k,
                max_hops=config.max_hops,
            )
        else:
            support_candidates = [(None, None, 0.0)]

        for support_binding, anchor_binding, support_score in support_candidates:
            candidate_source_ids = [binding.source_id for binding in output_bindings]
            if support_binding is not None:
                candidate_source_ids.append(support_binding.source_id)
            if anchor_binding is not None:
                candidate_source_ids.extend(anchor_binding.path_source_ids)

            filter_bindings = (
                _oracle_filter_bindings(context)
                if config.oracle_filter
                else _default_filter_bindings(context, candidate_source_ids, strict_types=config.typed_filter_strict)
            )
            measure_binding = None
            if support_binding is not None:
                measure_binding = _oracle_measure_binding(context, support_binding.source_id) if config.oracle_measure else None
                if measure_binding is None:
                    measure_binding = _best_measure_binding(context.observable_sketch, context.catalog.source(support_binding.source_id))

            plan = SupportPlan(
                output_bindings=output_bindings,
                output_join_paths=output_join_paths,
                support_binding=support_binding,
                anchor_binding=anchor_binding,
                evidence_bindings=[],
                measure_binding=measure_binding,
                filter_bindings=filter_bindings,
                operator_plan=dict(operator_plan),
                confidence=output_score + support_score + sum(binding.score for binding in filter_bindings) * 0.3,
                source_trace=sorted({binding.source_id for binding in output_bindings} | ({support_binding.source_id} if support_binding is not None else set())),
                notes=[config.name],
            )
            trace = verify_support_plan(plan, context.observable_sketch, context.obligation_sketch, context.catalog)
            satisfied, unmet = obligations_from_trace(trace, context.obligation_sketch)
            plan.satisfied_obligations = satisfied
            plan.unmet_obligations = unmet
            plan.confidence += sum(item["score"] for item in trace if item["passed"]) * 2.0
            if config.joint_rerank:
                plan.confidence += _global_consistency_bonus(plan, context)
            if config.obligation_hard and unmet:
                continue
            plans.append(plan)

    plans.sort(key=lambda item: item.confidence, reverse=True)
    return plans


def audit_case_recall(
    context: CaseContext,
    *,
    output_ks: Sequence[int] = (1, 3, 6),
    filter_ks: Sequence[int] = (1, 3),
    evidence_ks: Sequence[int] = (1, 4),
    max_hops_values: Sequence[int] = (2, 3),
) -> Dict[str, Any]:
    output_rankings = _rank_output_bindings(context, top_k=max(output_ks))
    filter_rankings = _rank_filter_candidates(context, top_k=max(filter_ks))
    time_rankings = _rank_time_candidates(context, top_k=max(filter_ks))

    output_slot_hits = {k: 0 for k in output_ks}
    output_slot_total = 0
    output_case_hits = {k: 1 for k in output_ks}
    for label, gold_bindings in context.gold_targets.output_bindings_by_label.items():
        if not gold_bindings:
            continue
        output_slot_total += 1
        candidates = output_rankings.get(label, [])
        for k in output_ks:
            hit = any(
                candidate.source_id == gold_binding.source_id and candidate.column_name == gold_binding.dirty_column
                for candidate in candidates[:k]
                for gold_binding in gold_bindings
                if gold_binding.source_id is not None and gold_binding.dirty_column is not None
            )
            output_slot_hits[k] += int(hit)
            output_case_hits[k] *= int(hit)

    filter_hits = {k: 0 for k in filter_ks}
    filter_total = 0
    matching_candidates = [candidate for group in filter_rankings for candidate in group]
    matching_candidates.extend(time_rankings)
    for gold_binding in context.gold_targets.filter_bindings:
        if gold_binding.source_id is None or gold_binding.dirty_column is None:
            continue
        filter_total += 1
        for k in filter_ks:
            hit = any(
                candidate.source_id == gold_binding.source_id and candidate.column_name == gold_binding.dirty_column
                for candidate in matching_candidates[:k]
            )
            filter_hits[k] += int(hit)

    evidence_hits = {k: 0 for k in evidence_ks}
    evidence_total = 0
    evidence_path_hits = {hops: 0 for hops in max_hops_values}
    evidence_path_total = 0
    output_gold_bindings = [bindings[0] for bindings in context.gold_targets.output_bindings_by_label.values() if bindings]
    primary_output_source_id = output_gold_bindings[0].source_id if output_gold_bindings else None
    if primary_output_source_id is not None:
        ranked_support = _rank_support_candidates(context, primary_output_source_id, top_k=max(evidence_ks), max_hops=2)
        for gold_binding in context.gold_targets.evidence_bindings:
            if gold_binding.source_id is None:
                continue
            evidence_total += 1
            evidence_path_total += 1
            for k in evidence_ks:
                hit = any(candidate.source_id == gold_binding.source_id for candidate, _, _ in ranked_support[:k] if candidate is not None)
                evidence_hits[k] += int(hit)
            for hops in max_hops_values:
                path_edges = context.catalog.find_best_path(gold_binding.source_id, primary_output_source_id, max_hops=hops)
                evidence_path_hits[hops] += int(gold_binding.source_id == primary_output_source_id or bool(path_edges))

    join_path_hits = {hops: 0 for hops in max_hops_values}
    join_path_total = len(context.gold_targets.join_pairs)
    registry = _load_registry_for_split(context.manifest_private, context.workspace, context.split)
    for pair in context.gold_targets.join_pairs:
        left_source = _make_gold_binding(str(pair["left_table"]), None, registry, {}, kind="join")
        right_source = _make_gold_binding(str(pair["right_table"]), None, registry, {}, kind="join")
        if left_source is None or right_source is None or left_source.source_id is None or right_source.source_id is None:
            continue
        for hops in max_hops_values:
            if left_source.source_id == right_source.source_id:
                join_path_hits[hops] += 1
                continue
            path_edges = context.catalog.find_best_path(left_source.source_id, right_source.source_id, max_hops=hops)
            join_path_hits[hops] += int(bool(path_edges))

    row = {
        "seed_id": context.seed_id,
        "variant": context.variant,
        "split": context.split,
        "view": context.view,
        "sketch_mode": context.sketch_mode,
        "motif": "AggregationJoin" if context.gold_targets.has_aggregation else ("FilterJoin" if context.gold_targets.filter_bindings else "SimpleJoin"),
        "filter_kind": context.gold_targets.primary_filter_kind,
        "filter_kind_tags": list(context.gold_targets.filter_kind_tags),
        "output_slot_total": output_slot_total,
        "filter_total": filter_total,
        "evidence_total": evidence_total,
        "join_path_total": join_path_total,
        "ambiguous_count_star": context.gold_targets.ambiguous_count_star,
    }
    for k in output_ks:
        row[f"output_column_recall_at_{k}"] = (output_slot_hits[k] / output_slot_total) if output_slot_total else 0.0
        row[f"output_case_recall_at_{k}"] = float(output_case_hits[k]) if output_slot_total else 0.0
    for k in filter_ks:
        row[f"filter_column_recall_at_{k}"] = (filter_hits[k] / filter_total) if filter_total else 0.0
    for k in evidence_ks:
        row[f"evidence_table_recall_at_{k}"] = (evidence_hits[k] / evidence_total) if evidence_total else 0.0
    for hops in max_hops_values:
        row[f"gold_join_path_reachable_at_{hops}"] = (join_path_hits[hops] / join_path_total) if join_path_total else 0.0
        row[f"evidence_path_reachable_at_{hops}"] = (evidence_path_hits[hops] / evidence_path_total) if evidence_path_total else 0.0
    return row


def run_probe(
    context: CaseContext,
    probe_name: str,
    *,
    output_csv: Path | None = None,
) -> Dict[str, Any]:
    config = _probe_config(probe_name)
    plans = _build_plan_candidates(context, config)
    if plans:
        best_plan = plans[0]
        plan_ir = build_support_plan_ir(best_plan, context.observable_sketch, context.obligation_sketch, context.catalog)
        compile_meta = compile_support_plan(best_plan, plan_ir, context.catalog, context.deliverable_spec, output_csv)
    else:
        best_plan = SupportPlan(output_bindings=[], confidence=0.0, unmet_obligations=["support_relation"])
        plan_ir = build_support_plan_ir(best_plan, context.observable_sketch, context.obligation_sketch, context.catalog)
        compile_meta = {
            "compiled": False,
            "executed": False,
            "required_columns_ok": False,
            "row_count": 0,
            "reason": "no_plan_candidates",
            "final_sql": None,
            "execution_summary": {"success": False, "row_count": 0, "columns": []},
        }
    if output_csv is not None and not output_csv.exists():
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=context.deliverable_spec.get("required_columns", [])).to_csv(output_csv, index=False)

    score = score_single(
        result_path=output_csv,
        gold_path=context.gold_path,
        spec=context.deliverable_spec,
    ) if output_csv is not None else {
        "pass": False,
        "score": 0.0,
        "stage": "DELIVERY_FAIL",
        "result_rows": 0,
        "gold_rows": 0,
    }
    result_rows = int(score.get("result_rows", compile_meta.get("row_count", 0)) or 0)
    return {
        "probe": probe_name,
        "config": asdict(config),
        "seed_id": context.seed_id,
        "variant": context.variant,
        "split": context.split,
        "view": context.view,
        "sketch_mode": context.sketch_mode,
        "pass": bool(score.get("pass")),
        "score": float(score.get("score", 0.0)),
        "stage": score.get("stage"),
        "result_rows": result_rows,
        "empty_fail": (not bool(score.get("pass"))) and result_rows == 0,
        "nonempty_fail": (not bool(score.get("pass"))) and result_rows > 0,
        "best_plan": best_plan.to_dict(),
        "support_ir": plan_ir.to_dict(),
        "compile_meta": compile_meta,
        "candidates_considered": len(plans),
        "final_sql": compile_meta.get("final_sql"),
    }
