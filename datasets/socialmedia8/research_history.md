# socialmedia8 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。当前状态和运行入口以
[README.md](README.md) 为准。

## 公共环境

2026-08-06 的实验使用 FASTEXPR、USA TOP3000、EQUITY、Delay 1，回测区间为
2025-08-06 至 2026-08-06。Neutralization 为 SUBINDUSTRY，Decay 为 `4`，
Truncation 为 `0.08`，Pasteurization ON、Unit Handling VERIFY、NaN Handling OFF、
Max Trade OFF。

## Fast D1 social sentiment

主字段 `snt_social_value_fast_d1` 是社交媒体情绪 Z-score；辅助字段
`snt_social_volume_fast_d1` 是标准化推文数量。两个字段的 Coverage 均为 `99.98%`，
Alpha Count 分别为 `1,632` 和 `1,594`。

| 结构 | Alpha ID | Sharpe | Fitness | 其他检查 |
|---|---|---:|---:|---|
| 情绪水平的 60 日 zscore | `pwNoVAOX` | 0.17 | 0.02 | Self Correlation PENDING |
| 5 日情绪变化乘关注度排名 | `VkGq2JQA` | 0.66 | 0.14 | Sub-universe -0.24；Self Correlation PENDING |

两条结构均未形成正向基线。第二条虽然方向为正，但 Sharpe 和 Fitness 距离要求较远，且
Sub-universe 为负，不适合继续做窗口或参数微调。情绪方向关闭，原
`sentiment_attention_seed` preset 已删除。

## Fast D1 social attention

该实验独立使用 `snt_social_volume_fast_d1`，验证社交关注度水平和短期变化，不依赖情绪
字段。

| 结构 | Alpha ID | Sharpe | Fitness | 其他检查 |
|---|---|---:|---:|---|
| 关注度水平的 60 日 zscore | `KPGqnVxk` | -0.12 | -0.01 | Self Correlation PENDING |
| 关注度的 5/60 标准化变化 | `omNAnl9b` | -0.18 | -0.02 | Self Correlation PENDING |

两条结构均明显失败。即使翻转符号，Sharpe 绝对值仍不到 `0.2`，不具备继续做窗口或参数
sweep 的价值。社交关注度方向关闭。

## 当前结论

fast D1 情绪和社交关注度两个独立方向均未形成正向基线，既定停止条件已经满足。
`socialmedia8` 暂停，不运行同源且 Alpha Count 更高的普通版本。只有出现新的独立经济假设
或字段发生实质更新时才重新评估。
