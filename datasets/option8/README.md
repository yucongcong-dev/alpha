# option8

## 当前状态

`option8` 是四个数据集中唯一仍保留现役 refine 策略的探索资产。现役入口统一为：

- [subindustry_refine/template.json](presets/subindustry_refine/template.json)
- [subindustry_refine/fields.txt](presets/subindustry_refine/fields.txt)

历史 phase、窗口、Decay 和 `trade_when` 实验文件已清理。
数据集 profile 已标记为 `paused`；普通 `--dataset-id option8` 会被拒绝，必须显式使用下方
preset 文件，避免重新运行已关闭的 diagnostic 模板。

## 当前最佳 Alpha

- Alpha ID：`2rNW02YN`
- 字段：`implied_volatility_mean_60`
- Sharpe：`1.58`
- Fitness：`0.78`
- Returns：`7.46%`
- Turnover：`30.33%`
- Sub-universe Sharpe：`0.91`

表达式：

```text
group_rank(
  ts_zscore(
    winsorize(ts_backfill(implied_volatility_mean_60, 5), std=4),
    60
  ),
  subindustry
)
```

该 Alpha 只是本地研究基线；运行器不提供正式提交功能。

## 已验证结论

- `subindustry` 明显优于 plain、sector 和 industry
- `ts_zscore(..., 60)` 优于 90/120 日长窗口
- Decay 10 会同时降低 Sharpe 和 Fitness
- `trade_when` 会破坏当前连续更新信号
- mean-skew 分支明显偏弱
- 50/70 等密集窗口没有足够证据支持继续微调

当前结构的主要限制仍是 Fitness 未达到提交门槛，而不是 Sharpe 或 Sub-universe Sharpe。
继续围绕单个样本做细窗口搜索，过拟合风险高于预期收益。

## 推荐命令

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id option8 \
  --template-library-file datasets/option8/presets/subindustry_refine/template.json \
  --include-fields-file datasets/option8/presets/subindustry_refine/fields.txt \
  --limit 1 \
  --max-templates-per-field 1 \
  --run-name verify-option8-subindustry
```

先使用 `--dry-run-plan` 验证候选数。程序只做 simulation/check，正式提交始终由人工决定。

## 下一步规则

- 把当前 Alpha 和 preset 作为稳定基线
- 只接受具有新经济含义的字段或结构
- 不再做密集窗口、Decay 或事件门控微调
- 如果没有新字段，优先切换到新数据集，而不是继续消耗 option8 预算
