# news18 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。它是只读研究档案，不是当前 preset；
当前状态和重新开启条件以 [README.md](README.md) 为准。

## 公共环境

除自动字段发现基线外，2026-08-04 的专项实验统一使用：

| 设置 | 值 |
|---|---|
| Region / Universe / Instrument / Delay | USA / TOP3000 / EQUITY / 1 |
| 回测区间 | 2025-08-04 至 2026-08-04 |
| Neutralization / Decay / Truncation | SUBINDUSTRY / 4 / 0.08 |
| Pasteurization / Unit Handling / NaN Handling | ON / VERIFY / OFF |
| Max Trade | OFF |

字段缓存当时包含 121 个字段，其中 71 个 MATRIX、50 个 VECTOR。

## 字段元数据

| 字段 | 类型 | Coverage | Date coverage | Alpha count | User count |
|---|---|---:|---:|---:|---:|
| `mean_corporate_action_sentiment` | MATRIX | 1.0 | 1.0 | 50 | 38 |
| `mean_event_novelty_score` | MATRIX | 1.0 | 1.0 | 64 | 55 |
| `mean_event_sentiment_score` | MATRIX | 1.0 | 1.0 | 59 | 46 |
| `mean_earnings_evaluation_sentiment` | MATRIX | 1.0 | 1.0 | 83 | 68 |
| `nws18_bee_fast_d1` | VECTOR | 1.0 | 1.0 | 16 | 13 |
| `nws18_qmb_fast_d1` | VECTOR | 1.0 | 1.0 | 12 | 8 |

这些字段覆盖完整，但表现仍弱，说明瓶颈不是缺失值，而是单字段假设没有形成稳定收益方向。

## 表达式结构

自动字段发现使用过一个短窗变化率基线：

```text
group_rank(
  ts_delta(ts_backfill(mean_composite_sentiment_score, 504), 5)
  / ts_std_dev(ts_backfill(mean_composite_sentiment_score, 504), 20),
  subindustry
)
```

后续 MATRIX 字段使用两条独立结构，其中 `{field}` 替换为具体字段：

```text
group_rank(ts_zscore(ts_backfill({field}, 20), 60), subindustry)
```

```text
trade_when(
  days_from_last_change({field}) <= 5,
  group_rank(ts_backfill({field}, 5), subindustry),
  -1
)
```

VECTOR 字段先做单层 `vec_avg()`，再使用对应结构：

```text
group_rank(ts_zscore(ts_backfill(vec_avg({field}), 20), 60), subindustry)
```

```text
trade_when(
  days_from_last_change(vec_avg({field})) <= 5,
  group_rank(ts_backfill(vec_avg({field}), 5), subindustry),
  -1
)
```

## 结果

| 字段 | 结构 | Alpha ID | Sharpe | Fitness | 其他关键结果 |
|---|---|---|---:|---:|---|
| `mean_composite_sentiment_score` | 5/20 短窗变化率 | `A1GZVjjW` | -0.17 | -0.01 | Turnover 0.7518 |
| `mean_corporate_action_sentiment` | MATRIX zscore | `E5GW6wMm` | -0.55 | -0.08 | - |
| `mean_corporate_action_sentiment` | MATRIX event hold | `qMNrL6Nv` | -0.45 | -0.08 | - |
| `mean_event_novelty_score` | MATRIX zscore | `qMNrVZEZ` | -0.47 | -0.07 | Sub-universe -0.74 |
| `mean_event_sentiment_score` | MATRIX zscore | `9qp1kml9` | -0.80 | -0.16 | Sub-universe -0.61 |
| `mean_event_sentiment_score` | MATRIX event hold | `2rpzexAw` | -0.38 | -0.08 | Sub-universe -0.52 |
| `mean_earnings_evaluation_sentiment` | MATRIX zscore | `58p0dvw1` | -0.92 | -0.19 | Sub-universe -0.50 |
| `mean_earnings_evaluation_sentiment` | MATRIX event hold | `LLGaYkxv` | -0.27 | -0.04 | - |
| `nws18_bee_fast_d1` | VECTOR zscore | `78zbPqg8` | -0.38 | -0.05 | - |
| `nws18_bee_fast_d1` | VECTOR event hold | `WjAQrK2Z` | 0.06 | 0.00 | 仅改善到零附近 |
| `nws18_qmb_fast_d1` | VECTOR zscore | `KPGdoqG1` | -0.51 | -0.07 | Turnover 0.7005；Sub-universe -0.63 |
| `nws18_qmb_fast_d1` | VECTOR event hold | `kqPrw1VP` | -0.08 | 约 0 | Sub-universe -0.44 |

所有候选均不可提交。MATRIX 日均情绪、新颖度和 VECTOR 单字段聚合路径因此关闭；
后续只有新的多字段关系或经济假设才值得建立新的 preset。
