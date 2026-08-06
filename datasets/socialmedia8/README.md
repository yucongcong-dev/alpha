# socialmedia8

## 当前状态

`socialmedia8` 是当前现役 explore 数据集。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1 下
将其显示为 `Social Media Data for Equity`：数据集 Coverage `99.99%`、Date Coverage
`100%`，共 4 个 MATRIX 字段，最近更新于 2026-03。

当前入口是 [sentiment_attention_seed](presets/sentiment_attention_seed/)，只测试 fast D1
社交情绪水平，以及情绪变化与社交关注度的组合，不运行更拥挤的普通版本。

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

## 运行入口

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id socialmedia8 \
  --strategy-profile explore \
  --max-total-simulations 2 \
  --run-name socialmedia8-sentiment-attention-seed \
  --dry-run-plan
```

首次没有字段缓存时，离线计划会提示先执行一次认证运行。确认计划后移除
`--dry-run-plan`。程序只做 simulation 和 Check Submission，正式提交由人工决定。

## 停止与扩展规则

- 任一结构形成正向基线时，只围绕该结构做 4-6 个具有新经济含义的局部变体。
- 两条结构均明显失败时，暂停 `socialmedia8`，不继续测试普通版本。
- 不做相邻窗口、Decay、Truncation 或机械符号 sweep。
- 初始阶段最多 2 次 simulation，不扩大到其他社交媒体字段。
