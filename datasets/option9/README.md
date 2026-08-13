# option9

## 当前状态

`option9` 当前暂停。put/call 成交量比率和远期价格期限结构两个独立假设均未形成正向基线，
因此没有默认运行入口，也不遍历完整字段池。它提供期权 put/call 成交量与持仓量比率、
远期价格和盈亏平衡价格，USA / TOP3000 / delay=1 的覆盖率约为 98.17%。

首轮远期曲线种子（2026-08-13，`runs/forward-curve-seed-2026-08-13/`）在
`forward_price_90/270` 上的 4 个候选全部失败：Sharpe / Fitness / 权重集中度均不达标，
期限结构变体还伴随 Sub-universe Sharpe 过低。完整证据见
[research_history.md](research_history.md)。

## 已关闭方向

### put/call 成交量比率（2026-07-30）

真实回测区间为 2025-07-30 至 2026-07-30：

| Alpha | 结构 | Sharpe | Fitness | Sub-universe Sharpe |
| --- | --- | ---: | ---: | ---: |
| `omgZW0Ev` | 30 日 put/call 水平，取负号 | -0.57 | -0.09 | -1.07 |
| `akEGx9eO` | 30 日减 180 日期限偏离，取负号 | -0.83 | -0.16 | -1.22 |

结果方向与“高 put/call 偏空”的初始假设相反，说明该区间更接近期权防御需求的反向指标。
但即使直接翻转方向，Sharpe 也仅约 0.57 / 0.83，Fitness 绝对值仅 0.09 / 0.16，
仍明显弱于现有 `option8` 基线，不值得追加方向复跑或窗口精修。

### 远期价格期限结构（2026-08-13）

真实回测区间为 2025-08-13 至 2026-08-13；settings 为 FASTEXPR / USA / TOP3000 /
Delay 1 / SUBINDUSTRY / Decay 4 / Truncation 0.08。

| Alpha | 结构 | Sharpe | Fitness | Sub-universe Sharpe | 其他检查 |
| --- | --- | ---: | ---: | ---: | --- |
| `VkGYqZvJ` | `forward_price_270 / close - 1` 分组排序 | 0.28 | 0.08 | — | 权重集中 FAIL |
| `vRNJxOrb` | `forward_price_90 / close - 1` 分组排序 | 0.15 | 0.03 | — | 权重集中 FAIL |
| `N1b5qPrq` | `forward_price_270 / forward_price_30 - 1` 分组排序 | 0.46 | 0.12 | 0.12 | 权重集中 + Sub-universe FAIL |
| `rK2rEnXJ` | `forward_price_90 / forward_price_30 - 1` 分组排序 | 0.55 | 0.11 | -0.32 | 权重集中 + Sub-universe FAIL |

4 个候选 Sharpe 均远低于 1.25、Fitness 远低于 1.0，且全部命中 CONCENTRATED_WEIGHT；
期限结构变体比现货相对结构略好（Sharpe 0.46/0.55 vs 0.28/0.15），但仍距离门槛很远，
且 Sub-universe Sharpe 为 0.12 / -0.32。Self Correlation 仍为 PENDING，但其余检查已
决定性失败，不影响结论。远期价格方向关闭，不追加符号、窗口、Decay 或模板变体。

## 下一步规则

- 暂停 `option9`，不提供默认 preset；普通 `--dataset-id option9` 会被拒绝。
- 不围绕 `pcr_vol_30` 或 `forward_price_*` 做符号、窗口、Decay 或模板微调。
- 只有出现新的独立经济假设或平台字段发生实质更新时，才重新建立小范围 preset。
