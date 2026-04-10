import sys
content = open('evaluation/support_plan_agent/compiler.py', encoding='utf-8', errors='ignore').read()

old = (
    "f\"{output_anchor_expr.replace(output_alias + '.', output_alias_map[primary_output.source_id] + '.')} = s.output_anchor_key\"\n"
    "    )\n"
    "    if plan.operator_plan.get('direction'):\n"
    "        sql += f\" ORDER BY s.support_value {normalize_sql_order_direction(plan.operator_plan['direction'])}\"\n"
    "        if plan.operator_plan.get('limit'):\n"
    "            sql += f\" LIMIT {int(plan.operator_plan['limit'])}\"\n"
    "    return sql"
)

new = (
    "f\"{output_anchor_expr.replace(output_alias + '.', output_alias_map[primary_output.source_id] + '.')} = s.output_anchor_key\"\n"
    "    )\n"
    "    exists_clause = _build_exists_clause(plan, catalog, output_alias_map)\n"
    "    if exists_clause:\n"
    "        sql += f' WHERE {exists_clause}'\n"
    "    elif plan.operator_plan.get('direction'):\n"
    "        sql += f\" ORDER BY s.support_value {normalize_sql_order_direction(plan.operator_plan['direction'])}\"\n"
    "        if plan.operator_plan.get('limit'):\n"
    "            sql += f\" LIMIT {int(plan.operator_plan['limit'])}\"\n"
    "    return sql"
)

if old in content:
    content = content.replace(old, new, 1)
    open('evaluation/support_plan_agent/compiler.py', 'w', encoding='utf-8').write(content)
    print('SUCCESS')
else:
    print('NOT FOUND')
    idx = content.find("output_anchor_expr.replace")
    if idx >= 0:
        print(repr(content[idx-50:idx+300]))
    sys.exit(1)
