# L0 诊断：llm 通过、support 失败（variant A）

## 数据切片

- 条件：`split=l0`，`llm_code_agent` 通过且 `support_plan_agent` 失败。
- 全量池中约 **17** 个 seed（与 `max_cases=20` 对齐时即全取）。
- 诊断脚本：`evaluation/diagnose_support_recall_l0.py`（per-slot `top_k` 与生产 `search._best_output_bindings` 默认一致）。

## 分类结果（约）

| 类别 | 含义 | 数量（约） |
|------|------|------------|
| **recall** | 至少一个输出槽的 gold `(source_id, column)` 不在 per-slot top-k 候选池 | **0** |
| **rerank** | gold 全在池内，但 `search_support_plans` 的 `best_plan` 的 output 与 gold 不一致 | **7** |
| **compiler** | top1 的 output 已与 gold 对齐，但 compile/execute/`score_single` 仍失败 | **8** |
| **gold_parse_skip** | 无法从 gold 解析出可绑定的输出槽（如 soccer_2） | **2** |

## 结论

1. **召回（per-slot top-4）不是当前切片的主瓶颈**：gold 从未出现在「完全不在池里」的情况。
2. **主瓶颈在「重排 + 编译/执行链路」**：约一半在 **选错表/列组合**（rerank），**另一半在 SQL 正确性/执行/评分**（compiler 桶内仍包含错误 JOIN、CTE 映射、IR 约束等，需结合 `compiler_failure_kind` 细分）。
3. **后续优先级（建议）**
   - **rerank**：多槽联合打分、表/实体选择（如 climbing 选 mountain vs climber）。
   - **compiler**：SQL 与路径（`ORDER BY ASCENDING`→DuckDB 已在 `compiler`/`utils` 修复）、**JOIN 键/路径**、support CTE 双列同源、IR 义务未满足等。
   - **gold_parse_skip**：补 `extract_gold_targets` 或手工标注，避免样本丢失。
4. **消融**：若仍担心召回，可单独跑 `output_top_k=8/12` 或检查 `_output_plan_candidates` 是否因「无连通路径」丢掉 combo（与 per-slot 池不同）。

## 代码变更记录（与本次推进）

- `normalize_sql_order_direction` / `normalize_operator_direction`（`evaluation/support_plan_agent/utils.py`）：`ascending`/`descending` → DuckDB 合法 `ASC`/`DESC`；`search`/`probes` 合并 `order_hint` 时写入规范 `asc`/`desc`。
- 诊断 JSON 增加 `compiler_failure_kind` 与 `compiler_failure_kind_counts`（便于区分语法错误、IR 阻塞、执行后结果错等）。
