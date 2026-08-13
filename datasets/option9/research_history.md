# option9 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。它是只读研究档案，不代表当前 preset；
当前状态和运行入口以 [README.md](README.md) 为准。

## 公共环境

- 2026-07-30 put/call 实验：FASTEXPR、USA TOP3000、EQUITY、Delay 1，回测区间
  2025-07-30 至 2026-07-30。
- 2026-08-13 远期曲线种子：FASTEXPR、USA TOP3000、EQUITY、Delay 1，回测区间
  2025-08-13 至 2026-08-13。Neutralization 为 SUBINDUSTRY，Decay 为 `4`，
  Truncation 为 `0.08`，Pasteurization ON、Unit Handling VERIFY、NaN Handling OFF、
  Max Trade OFF。

option9 在 USA / TOP3000 / delay=1 下共 74 个字段，覆盖率约 98.17%；字段缓存位于
`cache/usa_top3000_equity_d1.json`。两个假设都只验证明确字段的小范围种子，不代表
完整字段池已经遍历。

## put/call 成交量比率（2026-07-30）

主字段 `pcr_vol_30`（覆盖率 98.10%，约 285 用户 / 443 Alpha）与对照期限
`pcr_vol_180`（覆盖率 98.10%，约 467 用户 / 680 Alpha）。

| Alpha | 结构 | Sharpe | Fitness | Sub-universe Sharpe |
| --- | --- | ---: | ---: | ---: |
| `omgZW0Ev` | 30 日 put/call 水平，取负号 | -0.57 | -0.09 | -1.07 |
| `akEGx9eO` | 30 日减 180 日期限偏离，取负号 | -0.83 | -0.16 | -1.22 |

结果方向与“高 put/call 偏空”假设相反；翻转方向后 Sharpe 仅约 0.57 / 0.83，
Fitness 绝对值 0.09 / 0.16，明显弱于 `option8` 基线，停止该方向。

## 远期价格期限结构（2026-08-13）

现役 preset `forward_curve_seed` 的两个结构，每个结构在 `forward_price_90` 与
`forward_price_270` 上各测一次，共 4 个 simulation：

| Alpha | 结构 | Sharpe | Fitness | Sub-universe Sharpe | 其他检查 |
| --- | --- | ---: | ---: | ---: | --- |
| `VkGYqZvJ` | `group_rank((forward_price_270 / close) - 1, subindustry)` | 0.28 | 0.08 | — | CONCENTRATED_WEIGHT FAIL |
| `vRNJxOrb` | `group_rank((forward_price_90 / close) - 1, subindustry)` | 0.15 | 0.03 | — | CONCENTRATED_WEIGHT FAIL |
| `N1b5qPrq` | `group_rank((forward_price_270 / forward_price_30) - 1, subindustry)` | 0.46 | 0.12 | 0.12 | CONCENTRATED_WEIGHT + LOW_SUB_UNIVERSE_SHARPE FAIL |
| `rK2rEnXJ` | `group_rank((forward_price_90 / forward_price_30) - 1, subindustry)` | 0.55 | 0.11 | -0.32 | CONCENTRATED_WEIGHT + LOW_SUB_UNIVERSE_SHARPE FAIL |

所有候选 Sharpe 远低于 1.25、Fitness 远低于 1.0，且权重集中度全部 FAIL；期限结构变体
比现货相对结构略好（Sharpe 0.46/0.55 vs 0.28/0.15），但 Sub-universe Sharpe 为
0.12 / -0.32。Self Correlation 仍为 PENDING，但其余检查已决定性失败，不影响结论。
远期价格方向关闭。

运行产物保留在 `runs/forward-curve-seed-2026-08-13/`（`summary.json`、
`analysis.json`、`results.jsonl`），结论沉淀后可按约定清理。
