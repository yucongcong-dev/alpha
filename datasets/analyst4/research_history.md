# analyst4 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。它是只读研究档案，不代表当前 preset；
当前状态和运行入口以 [README.md](README.md) 为准。

## 公共环境

2026-08-06 的实验使用 FASTEXPR、USA TOP3000、EQUITY、Delay 1，回测区间
为 2025-08-06 至 2026-08-06。Neutralization 为 SUBINDUSTRY，Decay 为 `4`，
Truncation 为 `0.08`，Pasteurization ON、Unit Handling VERIFY、NaN Handling OFF、
Max Trade OFF。

字段缓存包含 1324 个字段。所有实验均围绕明确字段和两条种子结构进行，不代表完整字段池
已经遍历。

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

## Annual sales guidance range

该实验比较公司年度销售指引上界
`anl4_fs_guidances_basic_af_nd_sales_maxguidance` 与下界
`anl4_fs_guidances_basic_af_nd_sales_minguidance`。两个字段的 Coverage 和 Date Coverage
均为 `100%`，Alpha Count 分别为 `1` 和 `17`。

| 结构 | Alpha ID | Sharpe | Fitness | 其他检查 |
|---|---|---:|---:|---|
| guidance range 的 252 日 zscore | `E5GYYr8m` | 未触发 LOW_SHARPE | 0.98 | Sub-universe -0.25；Self Correlation PENDING |
| guidance range 的 63/126 变化率 | `3qp33n86` | 0.19 | 0.05 | Sub-universe -0.21；Self Correlation PENDING |

第一条 Fitness 接近阈值，但 Sub-universe 明显为负，不能作为稳健正向基线；第二条整体明显
失败。销售指引区间方向关闭，不继续做局部参数变体。

## Event-level sales estimate revision

该实验使用 VECTOR 字段 `sales_estimate_value` 与 `sales_previous_estimate_value`，比较当前
事件级销售预期与上次预期。两个字段当时的 Coverage 分别为 `99.3%` 和 `98.7%`，
Alpha Count 分别为 `59` 和 `39`。

| 结构 | Alpha ID | Sharpe | Fitness | 其他检查 |
|---|---|---:|---:|---|
| sales revision spread 的 126 日 zscore | `e73gKw16` | -0.72 | -0.22 | Sub-universe -0.70；Self Correlation PENDING |
| sales revision spread 的 20/126 变化率 | `9qpbKQno` | -0.70 | -0.17 | Self Correlation PENDING |

两条结构均明显失败。即使翻转符号，Sharpe 绝对值仍仅约 `0.7`，不具备继续做窗口或参数
sweep 的价值。销售预期修正方向关闭。

## 当前结论

EPS 与销售两类独立假设均未形成正向基线，既定停止条件已经满足。`analyst4` 暂停，不研究
recommendation 邻域，也不扩大到完整 1324 字段池。只有出现新的独立经济假设或字段发生
实质更新时才重新评估。
