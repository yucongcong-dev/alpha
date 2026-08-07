# news18 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。它是只读研究档案，不是当前 preset；
当前状态和重新开启条件以 [README.md](README.md) 为准。

## 2026-08-07 跨市场与 D0 筛选

官方 `/data-sets` 只读查询覆盖了 EUR / TOP2500 / D1、ASI / TOP3000 / D1、
CHN / TOP2000 / D1、USA / TOP1000 / D0、EUR / TOP1000 / D0 和
CHN / TOP2000 / D0。当前账号只有 USA / TOP1000 / D0 返回可用数据集；跨区域组合
均返回空列表，符合官网关于 EUR、Asia 仅向部分 research consultant 开放的权限说明。

USA / TOP1000 / D0 下 `news18` 的数据集覆盖率为 `0.9746`，共有 24 个字段，
数据集层 Alpha Count / User Count 为 `10 / 9`。与旧 D1 慢窗研究不同，以下字段直接描述
同日事件，且字段层使用量很低：

| 字段 | 语义 | Coverage | Alpha / User Count |
|---|---|---:|---:|
| `nws18_bee` | 盈利评价分数 | 1.0 | 0 / 0 |
| `nws18_nip` | 未来约两小时的短时市场影响估计 | 1.0 | 0 / 0 |
| `nws18_bam` | 并购新闻情绪 | 1.0 | 2 / 2 |
| `nws18_ghc_lna` | 分析师评级变化 | 1.0 | 3 / 3 |

因此曾建立临时 `d0_event_seed`，每个字段只运行一次直接事件持仓结构：

```text
trade_when(
  is_nan(vec_avg(field)) == 0,
  group_rank(vec_avg(field), subindustry),
  -1
)
```

该结构不使用 D1 研究中的 5/20 变化率、60 日 zscore、回填或窗口 sweep。真实结果为：

| 字段 | Alpha ID | Sharpe | Fitness | Turnover | 其他 |
|---|---|---:|---:|---:|---|
| `nws18_ghc_lna` | `wpazrZKQ` | 0.88 | 0.18 | 1.5340 | Concentrated Weight 0.168528 |
| `nws18_bee` | `leWzmK3x` | 0.87 | 0.15 | 1.1305 | - |
| `nws18_bam` | `1YpmMjx6` | 0.58 | 0.08 | 1.2286 | - |
| `nws18_nip` | `GrG8Rzzx` | -0.01 | -0.00 | 1.0913 | - |

D0 Check Submission 门槛显示 Sharpe `2.0`、Fitness `1.3`、Turnover 上限 `0.7`。
4 个种子已全部明确失败；`SELF_CORRELATION` 虽仍为 `PENDING`，但不是停止判断的瓶颈。
低拥挤度没有转化为可用基线，临时 preset 随后删除，不继续做 Decay、窗口或符号 sweep。

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
