# fundamental6 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。它是只读研究档案，不代表当前 preset、
推荐提交候选或默认运行入口；当前决策与运行边界以 [README.md](README.md) 为准。

## 公共环境

2026-08-04 至 2026-08-05 的记录均使用 FASTEXPR、USA TOP3000、EQUITY、Delay 1、
Pasteurization ON、Unit Handling VERIFY、NaN Handling OFF、Max Trade OFF。

| 实验 | 回测区间 | Neutralization | Decay | Truncation |
|---|---|---|---:|---:|
| 2026-08-04 主线、股息和 broad 结果 | 2025-08-04 至 2026-08-04 | SUBINDUSTRY | 4 | 0.08 |
| 2026-08-05 `fnd6_cicurr` refine | 2025-08-05 至 2026-08-05 | SUBINDUSTRY | 4 | 0.08 |

早期 settings 变体存在不同 Decay、Truncation 或 INDUSTRY neutralization；下文只把用于
最终判断的基准结果作为长期证据。

## fnd6_cicurr

2026-08-04 broad 结果中的最佳结构：

```text
group_rank(
  ts_zscore(
    winsorize(ts_backfill(fnd6_cicurr, 120), std=4)
    / ts_backfill(assets, 504),
    252
  ),
  industry
)
```

Alpha `QPGLow8r`：Sharpe `1.35`、Fitness `0.80`、Turnover `0.0328`、Returns `0.0442`、
Sub-universe Sharpe `1.12`。Fitness 失败；当时 Self Correlation 尚为 `PENDING`。

2026-08-05 使用 [presets/cicurr_refine/template.json](presets/cicurr_refine/template.json)
测试五个结构变体：

| 结构 | Alpha ID | Sharpe | Fitness | Turnover | 结论 |
|---|---|---:|---:|---:|---|
| assets / subindustry | `E5GA7Xpm` | 1.36 | 0.77 | 0.0291 | Fitness 低于原始候选 |
| assets / cap bucket | `9qpQv0ax` | 1.17 | 0.61 | 0.0390 | Sharpe、Fitness 均失败 |
| enterprise value / industry | `VkGo9gOb` | 0.40 | 0.14 | 0.0604 | 明显变弱 |
| cap / industry | `2rpk0R0w` | 0.25 | 0.07 | 0.0616 | Sharpe、Fitness、Sub-universe 失败 |
| assets 变化强度 / industry | `blQ3ko6N` | 0.66 | 0.27 | 0.0713 | 变化结构未保留原始优势 |

五条结果的 Self Correlation 当时均为 `PENDING`，但每条已经因 Sharpe 或 Fitness 失败。
可复现计划：

```bash
python -m alpha --dataset-id fundamental6 \
  --strategy-profile refine \
  --template-library-file datasets/fundamental6/presets/cicurr_refine/template.json \
  --include-fields-file datasets/fundamental6/presets/cicurr_refine/fields.txt \
  --include-templates-file datasets/fundamental6/presets/cicurr_refine/templates.txt \
  --max-templates-per-field 5 \
  --max-total-simulations 5 \
  --no-auto-update-blacklist \
  --dry-run-plan
```

## cashflow_op 历史主线

长期分组异常度：

```text
group_rank(
  ts_zscore(winsorize(ts_backfill(cashflow_op, 120), std=4) / cap, 252),
  subindustry
)
```

- 模板：`hc_ratio_group_zscore_252_over_cap`
- Alpha：`3qe7krMQ`
- 2026-07-24 复跑曾为 `submittable=true`
- 2026-08-04 再检查时仅 Self Correlation 失败，值为 `1.0`

变化强度：

```text
group_rank(
  ts_delta(winsorize(ts_backfill(cashflow_op, 120), std=4) / cap, 63)
  / ts_std_dev(winsorize(ts_backfill(cashflow_op, 120), std=4) / cap, 126),
  subindustry
)
```

- 模板：`group_ratio_delta_over_std_63_126_over_cap`
- Alpha：`A17weAVw`
- 2026-07-24 复跑曾为 `submittable=true`
- 2026-08-04 再检查时仅 Self Correlation 失败，值为 `0.8237`

两条表达式仍保存在 [template.json](template.json) 中作为 diagnostic probe，不再是提交主线。

## cashflow_dividends

Subindustry 变化强度：

```text
group_rank(
  ts_delta(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 63)
  / ts_std_dev(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 126),
  subindustry
)
```

Alpha `GrGAnPx3` 的 Sharpe 和 Fitness 通过，但 Self Correlation 为 `0.7113`。

市值分桶变化强度：

```text
group_rank(
  ts_delta(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 63)
  / ts_std_dev(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 126),
  densify(bucket(rank(cap), range='0.1, 1, 0.1'))
)
```

Alpha `YPvKdx56` 的 Self Correlation 通过，Fitness 为 `0.99`，未严格超过 `1.0`。

字段更新事件触发：

```text
trade_when(
  days_from_last_change(cashflow_dividends) <= 20,
  group_rank(
    ts_delta(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 63)
    / ts_std_dev(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 126),
    densify(bucket(rank(cap), range='0.1, 1, 0.1'))
  ),
  -1
)
```

Alpha `XgoQ1b7x`：Sharpe `0.33`、Fitness `0.10`、Sub-universe Sharpe `0.05`。
事件条件明显破坏信号；assets、enterprise value 分母和长期 zscore 结构也明显更弱。

## 其他已关闭证据

2026-07-29 测试应计/现金质量关系：

```text
(cashflow_op - income) / assets
```

| 结构 | Alpha ID | Sharpe | Fitness |
|---|---|---:|---:|
| 长期异常度 | `MPLZmvna` | -0.04 | 约 0 |
| 变化强度 | `6XeJOkmG` | 0.11 | 0.02 |

该关系明显弱于历史现金流主线，不再调窗口、Decay 或 Neutralization。
