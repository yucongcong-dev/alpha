# news18

## 当前状态

`news18` 是 RavenPack News Data 的显式入口探索池。2026-08-04 在 USA TOP3000、
EQUITY、Delay 1 下获取到 121 个字段，其中 71 个 MATRIX、50 个 VECTOR。

dataset profile 标记为 `paused`，普通 `--dataset-id news18` 会拒绝运行。每轮必须显式提供
字段和模板文件，并保持 1 个字段、2 条结构的预算边界。当前没有现役 preset。

## 字段选择原则

- 优先 MATRIX，先验证清晰的经济方向，再单独研究 VECTOR 聚合方式。
- coverage 和 dateCoverage 优先接近 `1.0`。
- 优先低 alphaCount、低 userCount 的专项情绪、事件新颖度和新闻影响字段。
- 不使用 5/20 短窗变化率作为默认种子；首个自动基线出现高换手且表现为负。
- 一个字段的两条独立结构都明显为负时立即停止，不调整 Decay、Truncation 或邻近窗口。

## 已停止字段

### mean_composite_sentiment_score

字段发现阶段的自动基线：

```text
group_rank(
  ts_delta(ts_backfill(mean_composite_sentiment_score, 504), 5)
  / ts_std_dev(ts_backfill(mean_composite_sentiment_score, 504), 20),
  subindustry
)
```

- Alpha ID：`A1GZVjjW`
- Sharpe：`-0.17`
- Fitness：`-0.01`
- Turnover：`0.7518`

该结构同时存在负表现和高换手，不继续研究综合情绪短窗变化率。

### mean_corporate_action_sentiment

元数据：MATRIX，coverage `1.0`，dateCoverage `1.0`，alphaCount `50`，userCount `38`。

60 日情绪异常度：

```text
group_rank(
  ts_zscore(ts_backfill(mean_corporate_action_sentiment, 20), 60),
  subindustry
)
```

- Alpha ID：`E5GW6wMm`
- Sharpe：`-0.55`
- Fitness：`-0.08`

公司行动新闻更新时刷新持仓：

```text
trade_when(
  days_from_last_change(mean_corporate_action_sentiment) <= 5,
  group_rank(ts_backfill(mean_corporate_action_sentiment, 5), subindustry),
  -1
)
```

- Alpha ID：`qMNrL6Nv`
- Sharpe：`-0.45`
- Fitness：`-0.08`

两条独立结构都明显为负，该字段已停止，不保留可执行 preset。

## 下一字段

`mean_event_novelty_score`：MATRIX，coverage `1.0`，dateCoverage `1.0`，alphaCount `64`，
userCount `55`。下一轮应分别验证慢频新颖度异常和事件条件持仓，不与情绪字段组合，
避免在基线阶段引入多字段解释成本。
