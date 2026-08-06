# fundamental2 研究历史

本文件保存清理 `runs/` 后仍需长期保留的实验依据。它是只读研究档案，不代表当前 preset
或默认运行入口；当前状态与重新开启条件以 [README.md](README.md) 为准。

## 公共环境

2026-08-06 的税务质量实验使用 FASTEXPR、USA TOP3000、EQUITY、Delay 1，回测区间为
2025-08-06 至 2026-08-06。Neutralization 为 SUBINDUSTRY，Decay 为 `4`，Truncation
为 `0.08`，Pasteurization ON、Unit Handling VERIFY、NaN Handling OFF、Max Trade OFF。

WorldQuant BRAIN 当时将 `fundamental2` 显示为 `Report Footnotes`，包含 766 个 MATRIX
字段，数据集 Coverage 约 `44%`，Date Coverage `100%`。

## current_income_tax_expense_amount

该字段表示本期确认的当前所得税费用。实验时字段 Coverage 为 `79%`、Date Coverage 为
`100%`、Alpha Count 为 `3`。配对字段 `annual_deferred_income_tax_expense` 的 Coverage
为 `78%`、Alpha Count 为 `19`。

税费水平结构：

```text
group_rank(
  ts_zscore(
    winsorize(ts_backfill(current_income_tax_expense_amount, 120), std=4)
    / ts_backfill(assets, 504),
    252
  ),
  subindustry
)
```

Alpha `VkGwad35`：Sharpe `0.66`、Fitness `0.24`、Sub-universe Sharpe `-0.53`。

税费构成结构：

```text
group_rank(
  ts_zscore(
    (
      winsorize(ts_backfill(current_income_tax_expense_amount, 120), std=4)
      - winsorize(ts_backfill(annual_deferred_income_tax_expense, 120), std=4)
    ) / ts_backfill(assets, 504),
    252
  ),
  subindustry
)
```

Alpha `j26lAaeZ`：Sharpe `0.70`、Fitness `0.26`、Sub-universe Sharpe `0.15`。

两条结果的 Self Correlation 当时仍为 `PENDING`，但 Sharpe、Fitness 和 Sub-universe
Sharpe 已明确失败，最终相关性不会改变研究决策。税费水平和当前税费减递延税费的构成差异
均未形成正向基线，因此停止符号、窗口和邻近字段 sweep，不扩大到完整 766 字段池。

## 结论

`current_income_tax_expense_amount` 研究线关闭，临时 `tax_quality_seed` preset 已删除。
`fundamental2` 整体暂停；只有出现不同于税费水平和税费构成的新经济假设时，才建立新的小范围
preset 重新评估。
