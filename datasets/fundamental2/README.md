# fundamental2

## 当前状态

`fundamental2` 是当前现役 explore 数据集。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1
下将其显示为 `Report Footnotes`：共 766 个 MATRIX 字段，数据集 Coverage 约 `44%`，
Date Coverage `100%`，字段最近更新于 2026-03。

本仓库不做全字段扫描。首轮入口固定为
[tax_quality_seed](presets/tax_quality_seed/)，只测试 1 个字段、2 条独立结构。

## 首轮字段

`current_income_tax_expense_amount` 表示本期确认的当前所得税费用。平台筛选时该字段：

- Coverage：`79%`
- Date Coverage：`100%`
- Alpha Count：`3`
- 类型：`MATRIX`

配对字段 `annual_deferred_income_tax_expense` 的 Coverage 为 `78%`、Alpha Count 为 `19`。
首轮分别验证当前税费相对资产的水平，以及当前税费减递延税费后的税务构成差异。

## 运行入口

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id fundamental2 \
  --strategy-profile explore \
  --max-total-simulations 2 \
  --run-name fundamental2-tax-quality-seed \
  --dry-run-plan
```

`tax_quality_seed` 是 dataset profile 的默认 preset。首次本地没有字段缓存时，离线计划会提示
先执行一次认证运行；正式运行前移除 `--dry-run-plan`。程序只做 simulation/check，正式提交始终由人工决定。

## 停止与扩展规则

- 两条结构都明显低于 Sharpe/Fitness 基线时，关闭该字段，不做符号和邻近窗口 sweep。
- 只有至少一条结构形成正向基线时，才增加税务、租赁或稀释字段族。
- 新字段继续要求 Coverage 不低于 `70%`、Date Coverage 不低于 `99%`、Alpha Count 不高于
  `50`。
- 不把 `fundamental6` 的现金流模板机械复制到本数据集。
