from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from evaluation.workspace_catalog import (
    WorkspaceCatalog,
    execute_duckdb_sql,
    month_predicate_sql,
    transform_sql_expr,
    year_predicate_sql,
)

from .types import Binding, SupportPlan, SupportPlanIR
from .utils import normalize_sql_order_direction


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _binding_expr(alias: str, binding: Binding) -> str:
    return f"{alias}.{_quote(binding.column_name)}"


def _join_condition(edge: Dict[str, Any], alias_map: Dict[str, str]) -> str:
    left_alias = alias_map[edge["left_source_id"]]
    right_alias = alias_map[edge["right_source_id"]]
    left_expr = transform_sql_expr(edge.get("left_transform", "identity"), f'{left_alias}.{_quote(edge["left_column"])}')
    right_expr = transform_sql_expr(edge.get("right_transform", "identity"), f'{right_alias}.{_quote(edge["right_column"])}')
    return f"{left_expr} = {right_expr}"


def _collect_path_edges(plan: SupportPlan) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    for path in plan.output_join_paths:
        edges.extend(path.edges)
    for path in plan.filter_join_paths:
        edges.extend(path.edges)
    if plan.order_join_path is not None:
        edges.extend(plan.order_join_path.edges)
    if plan.anchor_binding is not None:
        edges.extend(plan.anchor_binding.edges)
    dedup: Dict[str, Dict[str, Any]] = {}
    for edge in edges:
        dedup[str(edge["edge_id"])] = edge
    return list(dedup.values())


def _source_sequence(plan: SupportPlan) -> List[str]:
    sequence: List[str] = []
    for binding in plan.output_bindings:
        if binding.source_id not in sequence:
            sequence.append(binding.source_id)
    if plan.support_binding is not None and plan.support_binding.source_id not in sequence:
        sequence.append(plan.support_binding.source_id)
    for edge in _collect_path_edges(plan):
        if edge["left_source_id"] not in sequence:
            sequence.append(edge["left_source_id"])
        if edge["right_source_id"] not in sequence:
            sequence.append(edge["right_source_id"])
    for binding in plan.filter_bindings:
        if binding.source_id not in sequence:
            sequence.append(binding.source_id)
    return sequence


def _ensure_join_clauses(plan: SupportPlan, catalog: WorkspaceCatalog) -> tuple[Dict[str, str], List[str], str]:
    source_ids = _source_sequence(plan)
    alias_map = {source_id: f"t{idx}" for idx, source_id in enumerate(source_ids)}
    primary_source_id = plan.output_bindings[0].source_id
    primary_view = catalog.source(primary_source_id).raw_view_name
    from_sql = f'FROM "{primary_view}" AS {alias_map[primary_source_id]}'
    seen = {primary_source_id}
    join_clauses: List[str] = []
    pending = _collect_path_edges(plan)
    while pending:
        progress = False
        rest: List[Dict[str, Any]] = []
        for edge in pending:
            left_seen = edge["left_source_id"] in seen
            right_seen = edge["right_source_id"] in seen
            if left_seen and right_seen:
                continue
            if not left_seen and not right_seen:
                rest.append(edge)
                continue
            next_source_id = edge["right_source_id"] if left_seen else edge["left_source_id"]
            next_view = catalog.source(next_source_id).raw_view_name
            join_clauses.append(f'JOIN "{next_view}" AS {alias_map[next_source_id]} ON {_join_condition(edge, alias_map)}')
            seen.add(next_source_id)
            progress = True
        if not progress:
            break
        pending = rest

    # Safety net: filter sources that are still not reachable via plan edges.
    # Try catalog.find_best_path from any already-seen source.
    for binding in plan.filter_bindings:
        if binding.source_id in seen:
            continue
        filter_source_id = binding.source_id
        best_path_edges = None
        best_score = -1.0
        for via_id in list(seen):
            path_edges = catalog.find_best_path(via_id, filter_source_id, max_hops=2)
            if not path_edges:
                path_edges = catalog.find_best_path(filter_source_id, via_id, max_hops=2)
            if path_edges:
                score = sum(e.overlap for e in path_edges)
                if score > best_score:
                    best_score = score
                    best_path_edges = path_edges
        if best_path_edges is not None:
            from dataclasses import asdict as _asdict
            for edge_obj in best_path_edges:
                edge = _asdict(edge_obj) if not isinstance(edge_obj, dict) else edge_obj
                left_id = edge["left_source_id"]
                right_id = edge["right_source_id"]
                for sid in (left_id, right_id):
                    if sid not in alias_map:
                        alias_map[sid] = f"t{len(alias_map)}"
                next_id = right_id if left_id in seen else left_id
                if next_id not in seen:
                    next_view = catalog.source(next_id).raw_view_name
                    join_clauses.append(
                        f'JOIN "{next_view}" AS {alias_map[next_id]} ON {_join_condition(edge, alias_map)}'
                    )
                    seen.add(next_id)

    return alias_map, join_clauses, from_sql


def _ensure_output_join_clauses(plan: SupportPlan, catalog: WorkspaceCatalog) -> tuple[Dict[str, str], List[str], str]:
    source_ids: List[str] = []
    for binding in plan.output_bindings:
        if binding.source_id not in source_ids:
            source_ids.append(binding.source_id)
    for path in plan.output_join_paths:
        for edge in path.edges:
            if edge["left_source_id"] not in source_ids:
                source_ids.append(edge["left_source_id"])
            if edge["right_source_id"] not in source_ids:
                source_ids.append(edge["right_source_id"])
    alias_map = {source_id: f"o{idx}" for idx, source_id in enumerate(source_ids)}
    primary_source_id = plan.output_bindings[0].source_id
    primary_view = catalog.source(primary_source_id).raw_view_name
    from_sql = f'FROM "{primary_view}" AS {alias_map[primary_source_id]}'
    seen = {primary_source_id}
    join_clauses: List[str] = []
    pending: List[Dict[str, Any]] = []
    for path in plan.output_join_paths:
        pending.extend(path.edges)
    while pending:
        progress = False
        rest: List[Dict[str, Any]] = []
        for edge in pending:
            left_seen = edge["left_source_id"] in seen
            right_seen = edge["right_source_id"] in seen
            if left_seen and right_seen:
                continue
            if not left_seen and not right_seen:
                rest.append(edge)
                continue
            next_source_id = edge["right_source_id"] if left_seen else edge["left_source_id"]
            next_view = catalog.source(next_source_id).raw_view_name
            join_clauses.append(f'JOIN "{next_view}" AS {alias_map[next_source_id]} ON {_join_condition(edge, alias_map)}')
            seen.add(next_source_id)
            progress = True
        if not progress:
            break
        pending = rest
    return alias_map, join_clauses, from_sql


def _build_filter_predicates(plan: SupportPlan, alias_map: Dict[str, str]) -> List[str]:
    predicates: List[str] = []
    for binding in plan.filter_bindings:
        alias = alias_map[binding.source_id]
        col_ref = f"{alias}.{_quote(binding.column_name)}"
        if binding.role == "filter":
            operator = str(binding.metadata.get("operator", "="))
            value = binding.metadata.get("value")
            value_text = binding.metadata.get("value_text")
            # Coerce string numbers to numeric
            if isinstance(value, str):
                try:
                    value = float(value) if "." in value else int(value)
                except (ValueError, TypeError):
                    pass
            if isinstance(value, (int, float)):
                predicates.append(f"CAST({col_ref} AS DOUBLE) {operator} {value}")
            elif value_text:
                escaped = str(value_text).replace("'", "''")
                predicates.append(f"CAST({col_ref} AS VARCHAR) ILIKE '%{escaped}%'")
        elif binding.role == "time":
            years = binding.metadata.get("years", [])
            months = binding.metadata.get("months", [])
            normalized = transform_sql_expr("date", col_ref)
            if years:
                predicates.append(year_predicate_sql(normalized, years))
            if months:
                predicates.append(month_predicate_sql(normalized, months))
    return predicates


def _predicate_for_binding(binding: Binding, alias_map: Dict[str, str]) -> str | None:
    alias = alias_map.get(binding.source_id)
    if alias is None:
        return None
    col_ref = f"{alias}.{_quote(binding.column_name)}"
    if binding.role == "filter":
        operator = str(binding.metadata.get("operator", "="))
        value = binding.metadata.get("value")
        value_text = binding.metadata.get("value_text")
        if isinstance(value, str):
            try:
                value = float(value) if "." in value else int(value)
            except (ValueError, TypeError):
                pass
        if isinstance(value, (int, float)):
            return f"CAST({col_ref} AS DOUBLE) {operator} {value}"
        if value_text:
            escaped = str(value_text).replace("'", "''")
            return f"CAST({col_ref} AS VARCHAR) ILIKE '%{escaped}%'"
        return None
    if binding.role == "time":
        years = binding.metadata.get("years", [])
        months = binding.metadata.get("months", [])
        normalized = transform_sql_expr("date", col_ref)
        predicates: List[str] = []
        if years:
            predicates.append(year_predicate_sql(normalized, years))
        if months:
            predicates.append(month_predicate_sql(normalized, months))
        return " AND ".join(predicates) if predicates else None
    return None


def _build_exists_clause(
    plan: SupportPlan,
    catalog: WorkspaceCatalog,
    alias_map: Dict[str, str],
) -> str | None:
    """Build a WHERE EXISTS clause for existence-check semantics.

    For "customers with any account" style queries, generates:
    SELECT DISTINCT name FROM customers WHERE EXISTS (SELECT 1 FROM accounts WHERE accounts.customer_id = customers.customer_id)

    Uses catalog join_edges to find the join key between output and related sources.
    """
    if not plan.operator_plan.get("exists"):
        return None

    output_source_id = plan.output_bindings[0].source_id if plan.output_bindings else None
    if output_source_id is None:
        return None

    # Find a related source to join to via the catalog join graph
    related_source_id = None
    join_col_from_output = None
    join_col_from_related = None

    # Priority 1: filter_bindings provides the related source
    if plan.filter_bindings:
        related_source_id = plan.filter_bindings[0].source_id
        if related_source_id == output_source_id:
            related_source_id = None  # Same source
    # Priority 2: search catalog join graph for related sources
    if related_source_id is None:
        neighbors = catalog.join_neighbors(output_source_id)
        if neighbors:
            best_edge = max(neighbors, key=lambda e: e.overlap)
            other = best_edge.left_source_id if best_edge.right_source_id == output_source_id else best_edge.right_source_id
            related_source_id = other
            # Determine which column belongs to which side
            if best_edge.left_source_id == output_source_id:
                join_col_from_output = best_edge.left_column
                join_col_from_related = best_edge.right_column
            else:
                join_col_from_output = best_edge.right_column
                join_col_from_related = best_edge.left_column

    if related_source_id is None:
        return None

    output_alias = alias_map.get(output_source_id)
    related_alias = alias_map.get(related_source_id)
    if output_alias is None or related_alias is None:
        return None

    # Build the EXISTS subquery
    if join_col_from_output and join_col_from_related:
        join_cond = f"{output_alias}.{_quote(join_col_from_output)} = {related_alias}.{_quote(join_col_from_related)}"
    else:
        # Fallback: try to find edge in output_join_paths
        join_cond = None
        for path in plan.output_join_paths:
            for e in path.edges:
                edge_sources = {e["left_source_id"], e["right_source_id"]}
                if output_source_id in edge_sources and related_source_id in edge_sources:
                    if e["left_source_id"] == output_source_id:
                        join_cond = f"{alias_map.get(output_source_id, output_source_id)}.{_quote(e['left_column'])} = {alias_map.get(related_source_id, related_source_id)}.{_quote(e['right_column'])}"
                    else:
                        join_cond = f"{alias_map.get(output_source_id, output_source_id)}.{_quote(e['right_column'])} = {alias_map.get(related_source_id, related_source_id)}.{_quote(e['left_column'])}"
                    break
            if join_cond:
                break
        if join_cond is None:
            return None

    subquery_preds = [join_cond]
    # Add filter predicates if filter_bindings exist
    for binding in plan.filter_bindings:
        alias = alias_map.get(binding.source_id)
        if alias is None:
            continue
        col_ref = f"{alias}.{_quote(binding.column_name)}"
        if binding.role == "filter":
            operator = str(binding.metadata.get("operator", "="))
            value = binding.metadata.get("value")
            value_text = binding.metadata.get("value_text")
            if isinstance(value, str):
                try:
                    value = float(value) if "." in value else int(value)
                except (ValueError, TypeError):
                    pass
            if isinstance(value, (int, float)):
                subquery_preds.append(f"CAST({col_ref} AS DOUBLE) {operator} {value}")
            elif value_text:
                escaped = str(value_text).replace("'", "''")
                subquery_preds.append(f"CAST({col_ref} AS VARCHAR) ILIKE '%{escaped}%'")

    related_source = catalog.source(related_source_id)
    subquery_view = related_source.file_name or related_source_id
    subquery_alias = alias_map.get(related_source_id, related_source_id)
    subquery_sql = f"SELECT 1 FROM \"{subquery_view}\" AS {subquery_alias} WHERE " + " AND ".join(subquery_preds)
    return f"EXISTS ({subquery_sql})"


def _build_intersection_clauses(plan: SupportPlan, alias_map: Dict[str, str]) -> tuple[List[str], List[str]] | None:
    groups: Dict[tuple[str, str], List[Binding]] = {}
    for binding in plan.filter_bindings:
        if binding.role != "filter":
            continue
        value_text = str(binding.metadata.get("value_text", "")).strip() or str(binding.metadata.get("value", "")).strip()
        if not value_text:
            continue
        key = (binding.source_id, binding.column_name)
        groups.setdefault(key, []).append(binding)
    if not any(len(bindings) >= 2 for bindings in groups.values()):
        return None

    where_parts: List[str] = []
    having_parts: List[str] = []
    for _, bindings in groups.items():
        if len(bindings) < 2:
            continue
        predicates: List[str] = []
        case_parts: List[str] = []
        for idx, binding in enumerate(bindings):
            predicate = _predicate_for_binding(binding, alias_map)
            if not predicate:
                continue
            predicates.append(predicate)
            case_parts.append(f"WHEN {predicate} THEN 'v{idx}'")
        if len(predicates) < 2:
            continue
        where_parts.append("(" + " OR ".join(predicates) + ")")
        having_parts.append(f"COUNT(DISTINCT CASE {' '.join(case_parts)} END) >= {len(predicates)}")
    if not having_parts:
        return None
    return where_parts, having_parts


def _build_direct_sql(plan: SupportPlan, catalog: WorkspaceCatalog, required_columns: List[str]) -> str:
    alias_map, join_clauses, from_sql = _ensure_join_clauses(plan, catalog)
    where_predicates = _build_filter_predicates(plan, alias_map)
    intersection_clauses = _build_intersection_clauses(plan, alias_map) if plan.operator_plan.get("intersection") else None
    select_parts: List[str] = []
    group_exprs: List[str] = []
    aggregation = plan.operator_plan.get("aggregation")
    if aggregation and aggregation != "count" and plan.measure_binding is not None:
        agg_expr = f"{aggregation.upper()}({_binding_expr(alias_map[plan.measure_binding.source_id], plan.measure_binding)})"
    elif aggregation == "count":
        agg_expr = "COUNT(*)"
    else:
        agg_expr = ""

    # For direct-aggregation plans (no support binding), if aggregation is non-count but
    # no explicit measure_binding was found, fall back to the first measure-role output
    # binding as the aggregation target (e.g. "avg(amount_of_transaction)" slot pattern).
    _agg_from_output: Binding | None = None
    if aggregation and aggregation != "count" and not agg_expr:
        for _b in plan.output_bindings:
            if _b.role == "measure":
                agg_expr = f"{aggregation.upper()}({_binding_expr(alias_map[_b.source_id], _b)})"
                _agg_from_output = _b
                break

    # Track whether we've already emitted COUNT(*) so we don't duplicate it across
    # multiple measure-role bindings in a multi-output plan.
    _count_emitted = False

    for binding, required_column in zip(plan.output_bindings, required_columns):
        if aggregation and binding.role == "measure" and agg_expr:
            if aggregation == "count":
                if not _count_emitted:
                    select_parts.append(f"{agg_expr} AS {_quote(required_column)}")
                    _count_emitted = True
                    continue
                # Second+ measure slot for count: fall through to direct reference
            elif binding is _agg_from_output or plan.measure_binding is not None:
                # Emit the aggregation expression for this slot
                select_parts.append(f"{agg_expr} AS {_quote(required_column)}")
                continue
        expr = _binding_expr(alias_map[binding.source_id], binding)
        select_parts.append(f"{expr} AS {_quote(required_column)}")
        if aggregation and binding.role not in {"measure"}:
            group_exprs.append(expr)
        elif aggregation and binding.role == "measure" and not agg_expr:
            group_exprs.append(expr)
    select_keyword = "SELECT DISTINCT" if plan.operator_plan.get("exists") and not aggregation else "SELECT"
    sql = f"{select_keyword} {', '.join(select_parts)} {from_sql}"
    if join_clauses:
        sql += " " + " ".join(join_clauses)
    effective_where = list(where_predicates)
    # Add EXISTS clause for existence-check semantics
    exists_clause = _build_exists_clause(plan, catalog, alias_map)
    if exists_clause:
        effective_where.append(exists_clause)
    having_predicates: List[str] = []
    if intersection_clauses is not None:
        intersection_where, intersection_having = intersection_clauses
        effective_where.extend(intersection_where)
        having_predicates.extend(intersection_having)
    if effective_where:
        sql += " WHERE " + " AND ".join(effective_where)
    if aggregation and group_exprs and agg_expr:
        sql += " GROUP BY " + ", ".join(group_exprs)
    elif having_predicates:
        sql += " GROUP BY " + ", ".join(group_exprs or [expr.split(" AS ")[0] for expr in select_parts])
    if having_predicates:
        sql += " HAVING " + " AND ".join(having_predicates)
    if plan.operator_plan.get("direction") and agg_expr:
        sql += f" ORDER BY {agg_expr} {normalize_sql_order_direction(plan.operator_plan['direction'])}"
        if plan.operator_plan.get("limit"):
            sql += f" LIMIT {int(plan.operator_plan['limit'])}"
    elif plan.operator_plan.get("direction") and not agg_expr:
        # Non-aggregation ORDER BY: find the best column to sort on
        order_col = None
        target = plan.operator_plan.get("target", "")
        if plan.order_binding is not None and plan.order_binding.source_id in alias_map:
            order_col = _binding_expr(alias_map[plan.order_binding.source_id], plan.order_binding)
        # Try to match target hint to an output binding
        if order_col is None:
            for binding, required_column in zip(plan.output_bindings, required_columns):
                if target and target.lower() in binding.column_name.lower():
                    order_col = _binding_expr(alias_map[binding.source_id], binding)
                    break
        # Fallback: use the first measure-role binding
        if order_col is None:
            for binding, required_column in zip(plan.output_bindings, required_columns):
                if binding.role == "measure":
                    order_col = _binding_expr(alias_map[binding.source_id], binding)
                    break
        # Last resort: use the measure_binding if available
        if order_col is None and plan.measure_binding is not None and plan.measure_binding.source_id in alias_map:
            order_col = _binding_expr(alias_map[plan.measure_binding.source_id], plan.measure_binding)
        # Search all joined sources for a column matching the target hint
        if order_col is None and target:
            target_lower = target.lower().replace("_", "")
            for source_id, alias in alias_map.items():
                source = catalog.source(source_id)
                for col in source.columns:
                    col_lower = col.lower().replace("_", "")
                    if target_lower in col_lower or col_lower in target_lower:
                        order_col = f"{alias}.{_quote(col)}"
                        break
                if order_col is not None:
                    break
        if order_col is not None:
            sql += f" ORDER BY {order_col} {normalize_sql_order_direction(plan.operator_plan['direction'])}"
            if plan.operator_plan.get("limit"):
                sql += f" LIMIT {int(plan.operator_plan['limit'])}"
    return sql


def _build_support_sql(plan: SupportPlan, catalog: WorkspaceCatalog, required_columns: List[str]) -> str:
    if plan.support_binding is None:
        return _build_direct_sql(plan, catalog, required_columns)
    primary_output = plan.output_bindings[0]
    alias_map, join_clauses, from_sql = _ensure_join_clauses(plan, catalog)
    output_alias = alias_map[primary_output.source_id]
    has_aggregation = bool(plan.operator_plan.get("aggregation"))
    has_exists = bool(plan.operator_plan.get("exists"))
    aggregation = plan.operator_plan.get("aggregation") or ("count" if not has_exists else None)
    if has_exists and not plan.operator_plan.get("aggregation"):
        # EXISTS without aggregation: just DISTINCT the output anchor, no COUNT(*)
        measure_expr = None
    elif aggregation == "count" or plan.measure_binding is None:
        measure_expr = "COUNT(*)"
    else:
        measure_expr = f"{aggregation.upper()}({_binding_expr(alias_map[plan.measure_binding.source_id], plan.measure_binding)})"

    output_anchor_expr = _binding_expr(output_alias, primary_output)
    if plan.anchor_binding is not None and plan.anchor_binding.edges:
        for edge in reversed(plan.anchor_binding.edges):
            if edge["left_source_id"] == primary_output.source_id:
                output_anchor_expr = transform_sql_expr(
                    edge.get("left_transform", "identity"),
                    f'{output_alias}.{_quote(edge["left_column"])}',
                )
                break
            if edge["right_source_id"] == primary_output.source_id:
                output_anchor_expr = transform_sql_expr(
                    edge.get("right_transform", "identity"),
                    f'{output_alias}.{_quote(edge["right_column"])}',
                )
                break
    where_predicates = _build_filter_predicates(plan, alias_map)
    if measure_expr:
        support_sql = f"SELECT {output_anchor_expr} AS output_anchor_key, {measure_expr} AS support_value {from_sql}"
        if join_clauses:
            support_sql += " " + " ".join(join_clauses)
        if where_predicates:
            support_sql += " WHERE " + " AND ".join(where_predicates)
        support_sql += f" GROUP BY {output_anchor_expr}"
    else:
        # EXISTS without aggregation: just DISTINCT the output keys
        support_sql = f"SELECT DISTINCT {output_anchor_expr} AS output_anchor_key {from_sql}"
        if join_clauses:
            support_sql += " " + " ".join(join_clauses)
        if where_predicates:
            support_sql += " WHERE " + " AND ".join(where_predicates)

    output_view = catalog.source(primary_output.source_id).raw_view_name
    output_alias_map, output_join_clauses, output_from_sql = _ensure_output_join_clauses(plan, catalog)
    select_parts = []
    for binding, required_column in zip(plan.output_bindings, required_columns):
        if binding.role == "measure":
            select_parts.append(f's.support_value AS {_quote(required_column)}')
        else:
            select_parts.append(f'{output_alias_map[binding.source_id]}.{_quote(binding.column_name)} AS {_quote(required_column)}')
    sql = (
        "WITH support_cte AS ("
        f"{support_sql}"
        ") "
        f'SELECT {", ".join(select_parts)} '
        f"{output_from_sql} "
        f'{" ".join(output_join_clauses)} '
        "JOIN support_cte AS s ON "
        f"{output_anchor_expr.replace(output_alias + '.', output_alias_map[primary_output.source_id] + '.')} = s.output_anchor_key"
    )
    exists_clause = _build_exists_clause(plan, catalog, output_alias_map)
    if exists_clause:
        sql += f" WHERE {exists_clause}"
    elif plan.operator_plan.get("direction"):
        sql += f" ORDER BY s.support_value {normalize_sql_order_direction(plan.operator_plan['direction'])}"
        if plan.operator_plan.get("limit"):
            sql += f" LIMIT {int(plan.operator_plan['limit'])}"
    return sql


def compile_support_plan(
    plan: SupportPlan,
    plan_ir: SupportPlanIR,
    catalog: WorkspaceCatalog,
    deliverable_spec: Dict[str, Any],
    output_csv,
) -> Dict[str, Any]:
    required_columns = list(deliverable_spec.get("required_columns", []))
    if not plan_ir.compile_ready:
        return {
            "compiled": False,
            "executed": False,
            "required_columns_ok": False,
            "row_count": 0,
            "reason": plan_ir.compile_reason or "ir_not_ready",
            "final_sql": None,
        }
    # Use support CTE only when there's actual aggregation; otherwise direct SQL handles joins fine.
    # _build_support_sql projects one support_value per output slot with role=="measure". If the
    # planner incorrectly tags 2+ outputs as measure (common on mixed dimension+metric questions),
    # both columns become identical support_value and gold fails — fall back to direct SQL.
    has_aggregation = bool(plan.operator_plan.get("aggregation"))
    has_exists = bool(plan.operator_plan.get("exists"))
    measure_output_slots = sum(1 for b in plan.output_bindings if b.role == "measure")
    use_support_sql = (
        plan.support_binding is not None
        and (has_aggregation or has_exists)
        and measure_output_slots <= 1
    )
    sql = _build_support_sql(plan, catalog, required_columns) if use_support_sql else _build_direct_sql(plan, catalog, required_columns)
    exec_meta = execute_duckdb_sql(catalog, sql_query=sql, output_csv=output_csv)
    if not exec_meta["success"]:
        if not output_csv.exists():
            output_csv.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=required_columns).to_csv(output_csv, index=False)
        return {
            "compiled": False,
            "executed": False,
            "required_columns_ok": False,
            "row_count": 0,
            "reason": exec_meta.get("error", "execution_failed"),
            "final_sql": sql,
            "execution_summary": exec_meta,
        }
    columns = exec_meta.get("columns", [])
    required_columns_ok = set(required_columns).issubset(columns)
    row_count = int(exec_meta.get("row_count", 0))
    return {
        "compiled": True,
        "executed": True,
        "required_columns_ok": required_columns_ok,
        "row_count": row_count,
        "reason": None if required_columns_ok else "required_columns_missing",
        "final_sql": sql,
        "execution_summary": exec_meta,
    }
