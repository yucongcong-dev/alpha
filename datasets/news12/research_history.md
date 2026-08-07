# news12 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。当前状态和运行入口以
[README.md](README.md) 为准。

## 公共环境

2026-08-07 的实验使用 FASTEXPR、USA TOP3000、EQUITY、Delay 1，回测区间
为 2025-08-07 至 2026-08-07。Neutralization 为 SUBINDUSTRY，Decay 为 `4`，
Truncation 为 `0.08`，Pasteurization ON、Unit Handling VERIFY、NaN Handling OFF、
Max Trade OFF。

字段缓存包含 875 个字段。种子实验只验证两个官网筛选的 VECTOR 字段，不代表
完整字段池已经遍历。

## 事件种子

两个字段均先使用 `vec_avg`聚合，再使用 5 日 backfill、10 日线性 decay 和
subindustry 分组排序。

| 字段 | 假设 | Alpha ID | Sharpe | Fitness | 其他检查 |
|---|---|---|---:|---:|---|
| `nws12_mainz_30_min` | 新闻后 30 分钟反应 | `vRN91N7a` | -0.63 | -0.16 | Sub-universe -1.15；Self Correlation PENDING |
| `nws12_mainz_newrecord` | 首发新闻新颖度 | `A1GbV0OE` | 0.87 | 0.23 | Self Correlation PENDING |

价格反应方向明显失败，不做符号或相邻窗口 sweep。新颖度方向的 Sharpe 为正，
但 Fitness 距离提交要求较远；只允许一次 4 个结构变体的 refine，不扩大字段池。
