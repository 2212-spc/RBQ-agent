content = open('evaluation/support_plan_agent/compiler.py', encoding='utf-8', errors='replace').read()
old = """        f'SELECT {", ".join(select_parts)} '
        f"{output_from_sql} "
        f'{" ".join(output_join_clauses)} '
        "JOIN support_cte AS s ON "
        f"{output_anchor_expr.replace(output_alias + '.', output_alias_map[primary_output.source_id] + '.')} = s.output_anchor_key"
    )
    if plan.operator_plan.get("direction"):
        sql += f" ORDER BY s.support_value {normalize_sql_order_direction(plan.operator_plan['direction'])}"
        if plan.operator_plan.get("limit"):
            sql += f" LIMIT {int(plan.operator_plan['limit'])}"
    return sql"""
new = """        f'SELECT {", ".join(select_parts)} '
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
    return sql"""
if old in content:
    content = content.replace(old, new, 1)
    open('evaluation/support_plan_agent/compiler.py', 'w', encoding='utf-8').write(content)
    print("SUCCESS")
else:
    print("NOT FOUND")
    # Debug: print first 200 chars of old
    for i, c in enumerate(old[:200]):
        print(f"  {i}: {repr(c)}")
