# Full Bench Census Snapshot: Graph-First Baseline v1

## 1. 实验背景

- 目标：评估系统从 `family-aware binding` 重构为 `ObligationGraph`（Node / Edge / Status）之后的全局水位，验证新抽象的有效性与安全性。
- 基准环境：`outputs/hdrbench_full150_v1`
- 统计对象：`seed_passed=true` 的种子，共 `167` 个 `variant A` 任务。

## 2. 普查数据对比

| Setting | Stable Baseline | Graph Object | Delta |
|---|---:|---:|---:|
| `l0.full / A` | `14 / 167` (`8.38%`) | `18 / 167` (`10.78%`) | `+4` |
| `l1.full / A` | `10 / 167` (`5.99%`) | `12 / 167` (`7.19%`) | `+2` |

## 3. `l1.full / A` 的种子级变化

- Improved:
  - `spider__assets_maintenance__03144`
  - `spider__chinook_1__00826`

- Regressed:
  - 无

## 4. 核心定性结论

1. `Regressed = 0` 是当前最重要的数字。
   - 这说明 `ObligationGraph` 是一个安全、正交的底层抽象。
   - 在大量不需要隐式支持义务的题目上，它能够静默退化，不会引发系统性崩塌。

2. `Improved = 2` 说明新对象不是空壳。
   - 图约束确实能干预并改变部分 hard case 的生成轨迹。

3. `L0 +4` 对比 `L1 +2` 暴露了当前图系统的主要短板。
   - 现阶段图更像“逻辑声明层”，还不具备足够强的“物理拓扑传导力”来压制强噪声下的 schema-similar distractors。

4. 当前最合理的阶段判断是：
   - `Graph-first Baseline v1` 已经值得冻结。
   - 但在继续进行方法级改动之前，必须先建立 `AggregationJoin` 的 design / holdout protocol。

## 5. 纪律声明

从这个普查版本开始：

- 正式冻结 `Graph-first Baseline v1`
- 在未建立盲测 protocol 前，停止继续修改 Agent 搜索与编译逻辑
- 后续所有方法改动必须先经过 protocol 与 audit 约束
