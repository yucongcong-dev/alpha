# option9

## 当前状态

`option9` 已完成 put/call 最小验证，当前以 `forward_curve_seed` 重新进入受限探索。它提供期权 put/call 成交量与持仓量比率、远期价格和盈亏平衡价格，USA / TOP3000 / delay=1 的覆盖率约为 98.17%。

本轮只验证了低拥挤的 put/call 成交量比率：

- 主字段：`pcr_vol_30`，覆盖率 98.10%，约 285 个用户、443 个 Alpha
- 对照期限：`pcr_vol_180`，覆盖率 98.10%，约 467 个用户、680 个 Alpha

## 研究假设

真实回测区间为 2025-07-30 至 2026-07-30：

| Alpha | 结构 | Sharpe | Fitness | Sub-universe Sharpe |
| --- | --- | ---: | ---: | ---: |
| `omgZW0Ev` | 30 日 put/call 水平，取负号 | -0.57 | -0.09 | -1.07 |
| `akEGx9eO` | 30 日减 180 日期限偏离，取负号 | -0.83 | -0.16 | -1.22 |

结果方向与“高 put/call 偏空”的初始假设相反，说明该区间更接近期权防御需求的反向指标。但即使直接翻转方向，Sharpe 也仅约 0.57 / 0.83，Fitness 绝对值仅 0.09 / 0.16，仍明显弱于现有 `option8` 基线，不值得追加方向复跑或窗口精修。

## 下一步规则

- 现役 preset 仅保留 `presets/forward_curve_seed/`，只运行 `forward_price_90` 和
  `forward_price_270`。
- 不围绕 `pcr_vol_30` 做符号、窗口或 Decay 微调。
- 当前先比较远期价格相对现货价格，以及相对 `forward_price_30` 的期限结构；在得到首轮
  结果前不扩字段、不扩模板。
