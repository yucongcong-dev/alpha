# fundamental2

## 当前状态

`fundamental2` 当前暂停，不提供默认 preset，也不允许无显式研究入口的普通运行。

2026-08-06 的税务质量种子实验测试了 `current_income_tax_expense_amount` 的两条独立结构。
两条结果均明确失败 Sharpe、Fitness 和 Sub-universe Sharpe，因此关闭该字段，不扩大到
数据集的 766 个字段。完整表达式、Alpha ID 和指标见
[research_history.md](research_history.md)。

## 重新开启条件

- 提出与现有税费水平、税费构成不同的新经济假设。
- 明确指定小范围字段和独立模板，不从全字段扫描开始。
- 新入口必须建立新的 preset，并设置独立运行预算和停止规则。

重新开启前继续保留 `paused: true`，避免历史失败方向被默认运行再次执行。
