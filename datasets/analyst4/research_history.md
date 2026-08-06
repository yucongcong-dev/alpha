# analyst4 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。它是只读研究档案，不代表当前 preset；
当前状态和运行入口以 [README.md](README.md) 为准。

## 公共环境

2026-08-06 的 EPS surprise 实验使用 FASTEXPR、USA TOP3000、EQUITY、Delay 1，回测区间
为 2025-08-06 至 2026-08-06。Neutralization 为 SUBINDUSTRY，Decay 为 `4`，
Truncation 为 `0.08`，Pasteurization ON、Unit Handling VERIFY、NaN Handling OFF、
Max Trade OFF。

字段缓存包含 1324 个字段。该实验只验证一个季度 reported EPS 与匹配预期中位数的关系，
不代表完整字段池已经探索。

## Quarterly reported EPS surprise

主字段 `anl4_fs_actual_1qf_v4_nd_epsr_value` 表示季度实际 GAAP EPS；配对字段
`anl4_fs_detail_estimate_1qf_v4_nd_epsr_median` 表示季度 EPS 预期中位数。

| 结构 | Alpha ID | Sharpe | Fitness | 其他检查 |
|---|---|---:|---:|---|
| surprise/price 的 252 日 zscore | `E5G0x0W9` | -0.05 | -0.01 | Self Correlation PENDING |
| surprise/price 的 63/126 变化率 | `j26lOW39` | -0.25 | -0.06 | Self Correlation PENDING |

两条结果的 Sharpe 和 Fitness 均已明确失败，Self Correlation 的最终状态不会改变决策。
reported EPS surprise 方向关闭，原 `eps_surprise_seed` preset 已删除，不继续做符号、窗口、
Decay 或 Truncation sweep。

## Event-level EPS estimate revision

该实验使用低拥挤 VECTOR 字段 `anl4_fs_basic_splt_v4_nd_eps_estimate` 与
`anl4_fs_basic_splt_v4_nd_eps_previosestimate`，比较当前 EPS 预期和最近一次修正前预期。
两个字段当时的 Coverage 分别为 `96.8%` 和 `96.3%`，Alpha Count 分别为 `14` 和 `13`。

| 结构 | Alpha ID | Sharpe | Fitness | 其他检查 |
|---|---|---:|---:|---|
| revision spread 的 126 日 zscore | `npNY06jE` | -0.93 | -0.31 | Sub-universe -0.59；Self Correlation PENDING |
| revision spread 的 20/126 变化率 | `9qpbod72` | -0.42 | -0.07 | Self Correlation PENDING |

两条结构均明显失败，revision 方向关闭，原 `eps_revision_seed` preset 已删除。不做符号、
窗口、Decay 或 Truncation sweep；负号翻转后的绝对 Sharpe 也仍低于提交要求。

## Annual EPS estimate dispersion

该实验比较年度 EPS 预期上界与下界。两个字段当时的 Coverage 均约为 `99%`，Alpha Count
分别为 `86` 和 `45`。

| 结构 | Alpha ID | Sharpe | Fitness | 其他检查 |
|---|---|---:|---:|---|
| dispersion/price 的 252 日 zscore | `rK2EQL98` | 0.39 | 0.13 | Self Correlation PENDING |
| dispersion/price 的 63/126 变化率 | `KPGqxweN` | 0.49 | 0.19 | Self Correlation PENDING |

两条结构虽为正值，但距离 Sharpe `1.25` 和 Fitness `1.0` 的要求较远，不属于 near-pass。
EPS dispersion 方向关闭，原 `eps_dispersion_seed` preset 已删除，不做局部窗口或参数变体。

## 后续边界

已关闭的 surprise、revision 和 dispersion 都属于 EPS 研究，不能外推为整个 `analyst4`
失败。下一条独立假设是公司销售指引区间，仅允许 `sales_guidance_seed` 的两次 simulation；
若失败，再运行 `sales_revision_seed` 的两次 simulation。两个销售方向都没有形成正向基线
后暂停 `analyst4`，不研究 recommendation，也不扩大到完整 1324 字段池。
