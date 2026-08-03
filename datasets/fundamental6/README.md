# fundamental6

## 当前状态

`fundamental6` 是维护池，不再承担 broad-search 预算。现阶段只保留已经重复验证过的
`cashflow_op / cap` 双主线，用于低频健康检查和提交前复跑。

现役策略资产：

- [cashflow_submit_core/template.json](presets/cashflow_submit_core/template.json)
- [cashflow_submit_core/fields.txt](presets/cashflow_submit_core/fields.txt)
- [cashflow_submit_core/templates.txt](presets/cashflow_submit_core/templates.txt)

其余历史、观察和单模板 preset 已删除；关键结论已经收录在本文，不再维护可执行副本。

## 已验证双主线

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

两条主线曾在同一次最小 core pack 复跑中同时通过，当前不需要再拆分成独立 preset。

## 推荐命令

普通 `--dataset-id fundamental6` 运行会自动绑定 `cashflow_submit_core` preset。下面保留
完整写法用于审计和显式复跑；只要显式传入模板或 include 文件，自动 preset 就不会介入。

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id fundamental6 \
  --template-library-file datasets/fundamental6/presets/cashflow_submit_core/template.json \
  --include-fields-file datasets/fundamental6/presets/cashflow_submit_core/fields.txt \
  --include-templates-file datasets/fundamental6/presets/cashflow_submit_core/templates.txt \
  --no-auto-update-blacklist \
  --limit 1 \
  --max-templates-per-field 2 \
  --run-name verify-cashflow-core
```

先使用 `--dry-run-plan` 确认只出现两个现役模板名。已有 feedback 可能为每个模板展开
少量 settings 变体，因此 simulation 数可以大于 2。程序只做 simulation/check，不自动提交 Alpha。

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
