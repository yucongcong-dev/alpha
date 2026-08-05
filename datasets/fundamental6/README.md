# fundamental6

## 当前状态

`fundamental6` 的无边界 broad-search 仍然暂停。历史 `cashflow_op / cap` 双主线的性能
检查仍然通过，但当前 Self Correlation 已过高，不再作为可提交策略资产。

最近完成了 `fnd6_cicurr` 的一次小范围专项 refine；结果没有超过原始近通过候选，
该研究线已经关闭。其余历史和观察性 preset 已删除，关键结论收录在本文。

## 当前 fnd6_cicurr 专项

2026-08-04 的全量探索中，`fnd6_cicurr`（Comp Inc - Currency Trans Adj）在以下结构上
成为最佳近通过候选：

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

- Alpha ID：`QPGLow8r`
- Sharpe：`1.35`，通过
- Fitness：`0.80`，低于 `1.0` 门槛
- Turnover：`0.0328`
- Returns：`0.0442`
- Sub-universe Sharpe：`1.12`，通过
- Self Correlation：截至 2026-08-05 仍为 `PENDING`，不能视为已通过

专项 preset 位于 `presets/cicurr_refine/`，只包含 `fnd6_cicurr` 和 5 个结构变体，分别测试：

- `industry` 改为 `subindustry`
- 使用市值分桶分组
- `assets` 分母改为 `enterprise_value`
- `assets` 分母改为 `cap`
- 长期水平异常度改为 `63/126` 变化强度

2026-08-05 的真实 simulation 结果：

| 结构 | Alpha ID | Sharpe | Fitness | Turnover | 结论 |
|---|---|---:|---:|---:|---|
| assets / subindustry | `E5GA7Xpm` | 1.36 | 0.77 | 0.0291 | Sharpe 通过，Fitness 低于原始候选 |
| assets / cap bucket | `9qpQv0ax` | 1.17 | 0.61 | 0.0390 | Sharpe、Fitness 均失败 |
| enterprise value / industry | `VkGo9gOb` | 0.40 | 0.14 | 0.0604 | 明显变弱 |
| cap / industry | `2rpk0R0w` | 0.25 | 0.07 | 0.0616 | 明显变弱，Sub-universe 也失败 |
| assets 变化强度 / industry | `blQ3ko6N` | 0.66 | 0.27 | 0.0713 | 变化结构没有保留原始优势 |

5 条结果的 Self Correlation 在本轮结束时都仍为 `PENDING`。这不会改变研究决策：所有
候选已经因 Fitness 或 Sharpe 失败，且没有一条超过原始候选的 Fitness `0.80`。
`fnd6_cicurr` 的优势集中在 `assets / industry / 252-day zscore` 这一窄结构，替换分组、
分母或改成变化强度都会削弱信号。不要再通过窗口、Decay、Truncation 或 Neutralization
做密集微调；只有字段定义、数据覆盖或新的经济关系发生变化时才重新开启。

保留以下命令仅用于复现实验或刷新尚未终态的 Check Submission。先检查离线计划：

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

确认计划为 1 个字段、5 个 simulation 后，移除 `--dry-run-plan` 并增加独立
`--run-name` 运行。没有数据或假设变化时不要重复运行，也不要把该专项扩展成 100 字段
broad run。

## 历史双主线

字段：`cashflow_op`

1. 现金流相对市值的长期分组异常度

```text
group_rank(
  ts_zscore(winsorize(ts_backfill(cashflow_op, 120), std=4) / cap, 252),
  subindustry
)
```

- 模板：`hc_ratio_group_zscore_252_over_cap`
- Alpha ID：`3qe7krMQ`
- 2026-07-24 真实复跑：`submittable=true`

2. 现金流相对市值的变化强度

```text
group_rank(
  ts_delta(winsorize(ts_backfill(cashflow_op, 120), std=4) / cap, 63)
  / ts_std_dev(winsorize(ts_backfill(cashflow_op, 120), std=4) / cap, 126),
  subindustry
)
```

- 模板：`group_ratio_delta_over_std_63_126_over_cap`
- Alpha ID：`A17weAVw`
- 2026-07-24 真实复跑：`submittable=true`

两条主线曾在同一次最小 core pack 复跑中同时通过。2026-08-04 使用真实 Check
Submission 再次复跑时：

- `3qe7krMQ`：仅 Self Correlation 失败，值为 `1.0`
- `A17weAVw`：仅 Self Correlation 失败，值为 `0.8237`

两条表达式的 Sharpe/Fitness 仍通过，但已经无法提供足够独立的新信号，因此提交主线关闭。

## 已关闭的 cashflow_dividends 研究线

2026-08-04 对 `cashflow_dividends` 做了 6 个结构变体的真实 simulation 和 Check
Submission。最佳近通过结构是市值分桶版本：

```text
group_rank(
  ts_delta(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 63)
  / ts_std_dev(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 126),
  densify(bucket(rank(cap), range='0.1, 1, 0.1'))
)
```

- Alpha ID：`YPvKdx56`
- Self Correlation 检查通过
- Fitness：`0.99`，略低于 `1.0` 上限，暂不可提交

原始 `subindustry` 版本的结果是：

```text
group_rank(
  ts_delta(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 63)
  / ts_std_dev(winsorize(ts_backfill(cashflow_dividends, 120), std=4) / cap, 126),
  subindustry
)
```

- Alpha ID：`GrGAnPx3`
- Sharpe 和 Fitness 检查通过
- Self Correlation：`0.7113`，高于 `0.7` 上限，暂不可提交

最后测试了股息字段更新后 20 日内刷新持仓的事件触发版本：

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

- Alpha ID：`XgoQ1b7x`
- Sharpe：`0.33`
- Fitness：`0.10`
- Sub-universe Sharpe：`0.05`

事件触发明显破坏了信号。市值分桶虽然解决了 Self Correlation，但 Fitness 仍差 `0.01`；
`assets`、`enterprise_value` 分母和长期 zscore 结构也都明显变弱。因此该字段研究已关闭，
不再调整窗口、Decay、Truncation、Neutralization 或触发条件，也不保留可执行 preset。
只有字段定义、平台数据状态或经济假设发生实质变化时才重新开启。

## 运行边界

`fundamental6` 不配置默认 preset，并由 dataset profile 标记为 `paused`。普通
`--dataset-id fundamental6` 会直接拒绝运行。以下两种显式研究入口可以解除暂停：

- 传入模板库、字段 include 文件或模板 include 文件，开启边界明确的专项研究；
- 同时传入 `--full-run` 和正数 `--max-total-simulations`，开启带硬预算的全量探索。

`--full-run` 只写在 YAML 中、未显式提供总预算或将预算设为 `0`，都不会解除暂停。建议先使用
相同参数运行 `--dry-run-plan`，确认字段、模板和预计 simulation 数量。不要恢复
`cashflow_submit_core`，也不要继续微调上述历史表达式。

## 已停止方向

- `cogs`、`dpq`、`lctq` 第二主线扩张
- `industry decay`、`backfill 504`、`trade_when(volume)`
- 普通短窗口和与双主线高度相似的密集邻居
- 恢复大字段池和大模板池

2026-07-29 还验证了应计/现金质量关系：

```text
(cashflow_op - income) / assets
```

- 长期异常度：Alpha `MPLZmvna`，Sharpe `-0.04`，Fitness 约 `0`
- 变化强度：Alpha `6XeJOkmG`，Sharpe `0.11`，Fitness `0.02`

该关系明显弱于现有双主线，不再继续调窗口、Decay 或 Neutralization。

## 重新开启探索的条件

只有出现新的基本面字段、独立经济关系或平台字段状态明显变化时，才重新建立专项 preset。
日常只做双主线低频复跑；没有新增信息时，不恢复 broad-search。

---

## 平台的 alphaCount / userCount 怎么看

把 `MATRIX / VECTOR / coverage / dateCoverage / alphaCount / userCount` 一起看，`fundamental6` 更适合被理解成：

- 一个“基本面主库 + 大量事件/派生向量字段”的混合数据集
- 历史时间轴完整，但单日横截面覆盖不满
- 经典基本面字段更拥挤，事件/向量字段相对没那么拥挤

这三个判断放在一起，直接导出下面这些研究结论：

- 它不是“一套模板扫全场”的数据集
  - 因为 `MATRIX` 和 `VECTOR/event` 连进入表达式的方式都不一样
- 它不适合短窗乱扫
  - 因为很多字段更新慢、覆盖不满，更依赖补值、平滑、稳定化
- 它适合先做主干，再开支路
  - `MATRIX` 更适合作为基本面主干
  - `VECTOR/event` 更适合作为专项分支
- 它不适合对高拥挤字段做最普通的写法
  - 因为高 `alphaCount` 字段很容易做出“能跑但不新”的表达式

如果只记一句话，可以先记成：

- `fundamental6` 适合慢频、稳处理、结构化
- 不适合短窗堆量
- `MATRIX` 搭主干
- `VECTOR/event` 开支路
- 拥挤字段不是不能用，而是不能普通地用
