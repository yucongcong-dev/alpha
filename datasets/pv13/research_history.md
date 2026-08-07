# pv13 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。它是只读研究档案，不代表当前 preset；
当前状态和运行边界以 [README.md](README.md) 为准。

## 公共环境

2026-08-07 的实验使用 FASTEXPR、USA TOP3000、EQUITY、Delay 1，回测区间
为 2025-08-07 至 2026-08-07。Neutralization 为 SUBINDUSTRY，Decay 为 `4`，
Truncation 为 `0.08`，Pasteurization ON、Unit Handling VERIFY、NaN Handling OFF、
Max Trade OFF。

字段缓存包含 165 个字段。实验只验证两个官网筛选的独立关系假设，不代表
完整字段池已经遍历。

## 客户收益传播与网络中心性

两个 MATRIX 字段均使用同一个最小水平种子：

```text
group_rank(winsorize(ts_backfill({field}, 5), std=4), subindustry)
```

| 字段 | 经济含义 | Alpha ID | Sharpe | Fitness | 其他检查 |
|---|---|---|---:|---:|---|
| `pv13_ustomergraphrank_auth_rank` | 客户网络 HITS authority | `0mpdXX8k` | 0.43 | 0.21 | Self Correlation PENDING |
| `rel_ret_cust` | 客户公司平均一日收益 | `3qpxXXoZ` | -1.05 | -0.20 | Turnover 88.19%；Sub-universe -0.54；Self Correlation PENDING |

客户网络中心性为正值，但距离 Sharpe `1.25` 和 Fitness `1.0` 的要求较远，
不属于 near-pass。客户收益传播的 Sharpe 和 Fitness 均为负，且换手率超限。
两条结果的 Sharpe 和 Fitness 已经确定失败，Self Correlation 的最终状态不会改变决策。

## 当前结论

客户收益传播和客户网络中心性两个独立假设均未形成正向基线，既定停止条件
已经满足。`pv13` 暂停，原 `relationship_seed` preset 已删除，不做符号、窗口或
运行参数 sweep，也不扩大到完整 165 字段池。只有出现新的独立经济假设或字段
发生实质更新时才重新评估。
