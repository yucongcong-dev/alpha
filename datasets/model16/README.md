# model16

## 当前状态

`model16` 已暂停新增研究预算。默认 [template.json](template.json) 保留为数据集基线，
当前没有现役专项 preset。

字段表现更接近密集、缓慢变化的模型导数。多个字段在相同日期和模板下反复触及同一
质量上限，继续调窗口或包装算子容易产生重复信号。

## 本地证据

最近的 dense derivative 定向验证：

- `tested=34`
- `submittable=0`
- bucket-cap ratio 的 Sharpe 多在 `0.77–0.82`
- bucket-cap ratio 的 Fitness 多在 `0.63–0.64`
- cap ratio 的 Sharpe 多在 `0.66–0.67`
- cap ratio 的 Fitness 多在 `0.50–0.51`
- 个别邻居把 Sharpe 抬到约 `0.94`，Fitness 仍停在约 `0.63`
- Decay 变体进一步变差

四个主要 dense derivative 字段重复出现相同天花板，说明问题不是缺少更多相邻窗口，
而是字段信息本身缺乏新的横截面增量。

## 已停止方向

- cap-ratio 与 bucket-cap-ratio 的继续微调
- 60/120/504 等相邻时间窗口 sweep
- mean-reversion、Decay、IR 等相同字段包装
- 重新扩大 dense derivative 字段池

## 重新开启探索的条件

只有数据集新增字段、出现跨风格 relation，或能够引入独立风险/基本面向量时才重开。
没有新信息时，不重新创建历史 focused preset。
