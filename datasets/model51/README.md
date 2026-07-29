# model51

## 当前状态

`model51` 已暂停新增研究预算。默认 [template.json](template.json) 仅作为数据集基线，
当前没有现役专项 preset。

该数据集主要描述系统性和非系统性风险。历史结果已经表明，继续围绕相同字段做窗口、
Decay、bucket 或分组邻居，无法稳定提高 Fitness。

## 关键历史证据

`unsystematic_risk_last_60_days` 曾是最接近门槛的字段：

- `model51_ts_zscore_120`：Fitness 约 `0.85`
- `model51_bucket_cap_zscore_120`：Fitness 约 `0.83`
- `model51_ts_rank_120`：Fitness 约 `0.78`

后续 refine 没有突破该天花板。

`systematic_risk_last_30_days` 的专项验证同样较弱：

- bucket-cap ratio：Sharpe 约 `0.79`，Fitness 约 `0.37`
- cap ratio：Sharpe 约 `0.60–0.72`，Fitness 约 `0.35–0.37`
- 最好的相邻 bucket 结构也只有 Sharpe 约 `0.84`、Fitness 约 `0.37`

## 字段关系约束

同窗口的：

- `systematic_risk_last_*` 是对 SPY 回归的 R²
- `unsystematic_risk_last_*` 是 `1 - R²`

因此二者的同窗口 spread、ratio 或 rank 只是同一信息的单调变换，不应当作新的
relation 方向。

2026-07-29 测试了真正跨周期的 30 日–360 日 systematic risk 缺口：

- 当前缺口：Alpha `bldn38mp`，Sharpe `-0.53`，Fitness `-0.26`
- 缺口的 `ts_zscore(..., 120)`：Alpha `1YzP5NJk`，Sharpe `-0.20`，Fitness `-0.05`

两条结果均为负，临时 preset 已删除。

## 已停止方向

- beta/correlation SPY 分支
- unsystematic 60 日窗口微调
- systematic 30 日 ratio/bucket 微调
- 同窗口 systematic/unsystematic 配对
- 只依赖同一风险字段的短长窗口 sweep

## 重新开启探索的条件

只有获得独立的市场 regime 条件、第二风险向量，或数据集新增不同语义字段时才重开。
届时优先验证正交增量信息，不恢复旧 preset。
