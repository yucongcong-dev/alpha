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

## 后续边界

surprise 失败不能外推为整个 `analyst4` 失败。下一条独立假设是低拥挤 VECTOR 字段的 EPS
预期修正，即当前预期相对最近一次修正前预期的变化。该方向只允许当前
`eps_revision_seed` 的两次 simulation；若仍全部明显失败，再运行两次独立 dispersion
种子。两条独立方向都没有形成正向基线后，暂停 `analyst4`。
