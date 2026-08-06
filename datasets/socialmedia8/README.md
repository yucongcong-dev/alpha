# socialmedia8

## 当前状态

`socialmedia8` 当前已暂停。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1 下
将其显示为 `Social Media Data for Equity`：数据集 Coverage `99.99%`、Date Coverage
`100%`，共 4 个 MATRIX 字段，最近更新于 2026-03。

fast D1 社交情绪和独立社交关注度均未形成正向基线，结果见
[research_history.md](research_history.md)。既定停止条件已经满足，因此当前没有默认运行入口，
也不运行更拥挤的普通版本。

## 官网筛选依据

字段元数据于 2026-08-06 从 WorldQuant BRAIN 官方接口读取。

| 字段 | 含义 | Coverage | Date Coverage | Alpha Count | User Count |
|---|---|---:|---:|---:|---:|
| `snt_social_value_fast_d1` | 社交媒体情绪 Z-score | 99.98% | 100% | 1,632 | 1,056 |
| `snt_social_volume_fast_d1` | 标准化推文数量 | 99.98% | 100% | 1,594 | 1,121 |
| `snt_social_value` | 社交媒体情绪 Z-score | 100% | 100% | 6,733 | 3,396 |
| `snt_social_volume` | 标准化推文数量 | 100% | 100% | 6,564 | 3,142 |

fast D1 字段与普通字段表达同一底层信号，但 Alpha Count 低约 75%，因此只使用 fast D1
版本作为初始入口。

## 当前边界

- 暂停 `socialmedia8`，不再运行已完成的 sentiment 或 volume preset。
- 不测试同源且更拥挤的普通版本。
- 不做相邻窗口、Decay、Truncation 或机械符号 sweep。
- 只有出现新的独立经济假设或字段发生实质更新时才重新评估。
