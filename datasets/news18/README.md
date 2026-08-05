# news18

## 当前状态

`news18` 由 dataset profile 标记为 `paused`，当前没有现役 preset 或可提交候选。
2026-08-04 在 USA TOP3000、EQUITY、Delay 1 下获取到 121 个字段：71 个 MATRIX、
50 个 VECTOR。已测试的单字段情绪、新颖度和事件聚合结构均未形成正向基线。
完整字段元数据、表达式和逐 Alpha 结果见 [research_history.md](research_history.md)。

## 关键证据

| 字段 | 类型 | Alpha ID | 最佳 Sharpe | 最佳 Fitness | 决策 |
|---|---|---|---:|---:|---|
| `mean_composite_sentiment_score` | MATRIX | `A1GZVjjW` | -0.17 | -0.01 | 短窗变化率为负且 Turnover `0.7518` |
| `mean_corporate_action_sentiment` | MATRIX | `E5GW6wMm` / `qMNrL6Nv` | -0.45 | -0.08 | 慢频与事件结构都为负 |
| `mean_event_novelty_score` | MATRIX | `qMNrVZEZ` | -0.47 | -0.07 | 新颖度没有稳定收益方向 |
| `mean_event_sentiment_score` | MATRIX | `9qp1kml9` / `2rpzexAw` | -0.38 | -0.08 | 两种结构及 Sub-universe 均为负 |
| `mean_earnings_evaluation_sentiment` | MATRIX | `58p0dvw1` / `LLGaYkxv` | -0.27 | -0.04 | 专项情绪替换没有改善 |
| `nws18_bee_fast_d1` | VECTOR | `78zbPqg8` / `WjAQrK2Z` | 0.06 | 0.00 | 事件持仓仅改善到零附近 |
| `nws18_qmb_fast_d1` | VECTOR | `KPGdoqG1` / `kqPrw1VP` | -0.08 | 约 0 | 两条结构低于停止线 |

除首个自动基线外，上述重点字段的 coverage 与 dateCoverage 均为 `1.0`。结果说明当前瓶颈
不是缺失覆盖，而是单字段假设与模板没有产生有效收益方向。

## 研究与运行边界

- MATRIX 与 VECTOR 必须分区研究；VECTOR 模板使用 `{field}`，生成器负责展开单层
  `vec_avg(field)`，不要手动重复聚合。
- 不再用 `5/20` 短窗变化率作为默认种子，也不通过反转符号、邻近窗口或 settings 变体
  延长明显为负的研究线。
- 一个字段的两条独立结构都明显为负时停止；新的研究应来自多字段关系或新的经济假设。

普通 `--dataset-id news18` 会拒绝运行。重新探索必须显式传入研究文件，或使用带正数预算的
`--full-run`；执行前先加 `--dry-run-plan` 检查字段、模板和 simulation 数量。

## 已停止方向

- 日均综合情绪、公司行动情绪、事件情绪和盈利评价情绪的单字段 zscore / event-hold 路径。
- `mean_event_novelty_score` 的符号反转和窗口搜索。
- `nws18_bee_fast_d1`、`nws18_qmb_fast_d1` 的单字段 VECTOR 聚合邻域。
- 用相同两套模板继续枚举相似 sentiment 字段。

## 重新开启条件

只有出现新的经济假设、平台字段定义变化、明确的多字段关系，或需要补齐尚未覆盖的独立字段族
时才重新开启。重新运行时建立边界明确的 preset；不要直接恢复无预算的单字段枚举。
