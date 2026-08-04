# fundamental6

## 当前状态

`fundamental6` 已暂停，不再承担 broad-search、维护复跑或提交预算。历史
`cashflow_op / cap` 双主线的性能检查仍然通过，但当前 Self Correlation 已过高，
不再作为可提交策略资产。

其余历史、观察和单模板 preset 已删除；关键结论已经收录在本文，不再维护可执行副本。

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

`fundamental6` 不再配置默认 preset，并由 dataset profile 标记为 `paused`。普通
`--dataset-id fundamental6` 会直接拒绝运行；只有显式传入模板或 include 文件时才允许开启
新的专项研究。不要恢复 `cashflow_submit_core`，也不要继续微调上述历史表达式。

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
