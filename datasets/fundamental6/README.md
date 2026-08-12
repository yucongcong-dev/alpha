# fundamental6

## 当前状态

`fundamental6` 由 dataset profile 标记为 `paused`，没有当前可提交候选，也不配置默认
preset。普通 `--dataset-id fundamental6` 会拒绝运行；这不是永久禁止探索，而是要求每次
研究都显式给出专项范围，或使用带正数总预算的 `--run-mode full`。

当前结论：历史 `cashflow_op` 主线性能仍过线，但 Self Correlation 过高；
`fnd6_cicurr`、`cashflow_dividends` 和 `fnd6_newqv1300_tstkq` 的近通过候选都没有形成新的
提交入口。当前没有待运行专项，不恢复全库探索。
完整表达式、settings 和历史变体结果见 [research_history.md](research_history.md)。

## 关键证据

| 研究线 | Alpha ID | Sharpe | Fitness | 关键检查 | 决策 |
|---|---|---:|---:|---|---|
| `fnd6_cicurr` assets/industry zscore | `QPGLow8r` | 1.35 | 0.80 | Self Correlation 仍为 `PENDING` | Fitness 不足，专项关闭 |
| `fnd6_cicurr` assets/subindustry | `E5GA7Xpm` | 1.36 | 0.77 | Fitness 失败 | 5 个结构变体均未超过原始候选 |
| `cashflow_op` 长期异常度 | `3qe7krMQ` | 通过 | 通过 | Self Correlation `1.0` | 提交主线关闭 |
| `cashflow_op` 变化强度 | `A17weAVw` | 通过 | 通过 | Self Correlation `0.8237` | 提交主线关闭 |
| `cashflow_dividends` 市值分桶 | `YPvKdx56` | 通过 | 0.99 | Self Correlation 通过 | 差 Fitness `0.01`，停止微调 |
| `cashflow_dividends` subindustry | `GrGAnPx3` | 通过 | 通过 | Self Correlation `0.7113` | 相关性失败 |
| `cashflow_dividends` 事件触发 | `XgoQ1b7x` | 0.33 | 0.10 | Sub-universe Sharpe `0.05` | 事件化破坏信号 |
| `fnd6_newqv1300_tstkq` 市值分桶变化强度 | `xANMqKqp` | 通过 | 通过 | Self Correlation `0.7028` | 6 个去相关变体均未通过 |
| `fnd6_newqv1300_tstkq` Backfill 90 | `mL52j0LK` | 通过 | 通过 | Self Correlation `0.7021` | 改善仅 `0.0007`，专项关闭 |

`fnd6_cicurr` 的 2026-08-05 refine 还测试了市值分桶、`enterprise_value` / `cap`
分母和 `63/126` 变化强度；所有结果都因 Sharpe 或 Fitness 失败。历史应计关系
`(cashflow_op - income) / assets` 的两种结构 Sharpe 仅为 `-0.04` 和 `0.11`。

## 研究与运行边界

`fundamental6` 同时包含慢频 MATRIX 主干和 VECTOR/event 分支，不能用一套模板机械扫全场。
经典基本面字段通常更拥挤，优先使用稳定预处理和结构差异；VECTOR 字段应使用独立聚合模板。

现有 `presets/cicurr_refine/` 与 `presets/cashflow_decorrelate/` 只用于复现实验，
不代表现役提交策略。`fnd6_newqv1300_tstkq` 的临时去相关 preset 已在六个变体完成后删除；
逐 Alpha 结果保存在 [research_history.md](research_history.md) 中。

全量探索前先离线确认 Seed 覆盖和预算：

```bash
python -m alpha --dataset-id fundamental6 \
  --run-mode full \
  --max-total-simulations 100 \
  --dry-run-plan
```

确认计划后移除 `--dry-run-plan` 并设置独立 `--run-name`。预算低于剩余 Seed 字段数时，
本次只完成部分字段覆盖，不会提前进入 refine。`--max-total-simulations 0` 不能解除暂停。

## 已停止方向

- 对 `cashflow_op`、`fnd6_cicurr` 和 `cashflow_dividends` 继续调整邻近窗口、Decay、
  Truncation 或 Neutralization。
- `cogs`、`dpq`、`lctq` 第二主线，以及 `industry decay`、`backfill 504`、
  `trade_when(volume)`。
- `fnd6_newqv1300_tstkq` 的分桶、邻近窗口、分组、分母、Backfill 和 Winsorize 微调。
- 用普通短窗口批量扫描高拥挤 MATRIX 字段，或用 MATRIX 模板直接处理 VECTOR 字段。
- 在没有新证据时恢复旧 submit core 或重复运行已完成候选。

## 重新开启条件

出现新的基本面字段、独立经济关系、字段定义或平台状态变化时，可以建立新的专项 preset。
若目标是补齐初始字段覆盖，也可以显式执行带硬预算的 full-run；先完成 Seed，再根据反馈决定
是否 refine，不把“允许全量探索”误解成“取消所有 API 和 simulation 预算保护”。
