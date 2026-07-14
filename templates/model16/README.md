# model16 说明

## 定位
`model16` 当前更适合被视为一个慢频的评分/复合指标数据集，而不是原始高频信号源。

因此模板库的主方向是：
- 长窗口 `rank/zscore` 平滑
- 轻度 `decay`
- 带市场/行业语义的分组排序
- 少量、受控的 bucket 分组模板

## 官方口径
- 当前本地上下文里没有找到 `model16` 的官方专属模板手册。
- 能直接复用的官方信息，主要还是 BRAIN 通用的 alpha examples 表达式风格。

## Neutralization 建议

官网对 Model Dataset 的建议不是固定使用某一级中性化，而是根据模型子类别在
`Market / Sector / Industry / Subindustry` 之间做对照实验。

对 `model16` 当前这种慢频评分/复合指标，更适合：

- 以 `Industry` 作为第一基线，检查是否只是行业风格分数
- 用 `Sector` 和 `Subindustry` 各保留一个挑战版本
- 对规模效应明显的字段，使用 `bucket(rank(cap), ...)` 创建市值组，并先 `densify()`
- 模板内已经使用 `group_neutralize` 时，把 settings 层 Neutralization 设为 `None`，避免双重中性化

Neutralization 的选择应看一组稳定结果，而不是只挑 Sharpe 最高的单点。

## 本地证据

公开脚本启发：
- 公共脚本再次说明，长窗口预处理输入和克制的 bucket 分组值得保留。

结构性判断：
- 从字段命名和实际表现看，它更像复合分数类字段，而不是日频强反应型信号。
- 因此，短窗 `delta`、激进均值回归、暴力算子扫库，都不适合作为默认主力。

运行与策略证据：
- 当前整理后的模板库，已经明显优于过去的 fallback 形态，因此一批旧模板已移出默认库。
- 当前受保护的核心模板，明显偏向 `126` 天结构和带分组语义的排序。
- 最近 `stage2_lane_validation_round2` 的结果表明，密集导数类 partner-ratio 分支系统性偏弱：
  - `high_conviction_ratio`、`group_ratio_zscore` 经常被 `LOW_SHARPE` 和 `LOW_FITNESS` 卡住
  - `group_vol_scaled_delta` 多次因 `CONCENTRATED_WEIGHT` 和较弱的子域表现失败
  - 因此，默认 broad search 不该再把这些导数 pair-ratio 分支当作第一候选

## 当前模板方向

预处理：
- 使用 `252` 天 backfill，并叠加 `winsorize(std=4)`。

当前默认库目标：
- 维持一个紧凑、可生产的候选池，围绕最强的慢频分数假设展开
- 避免大量围绕同一个 `120/126` 天主意的近邻变体，挤占真正的思路多样性

默认主干形态：
- `zscore_decay_120`
- `rank_ts_rank_120`
- 市场/行业分组排序
- `cap-ratio` / `bucket-cap-ratio` 代表模板
- 一条 `mean_spread` 分支，加一条 `groupfill` 代表

密集导数分支：
- broad search 默认优先保留 `cap-ratio` 和 `bucket-cap-ratio`
- 除非后续 refine 明确出现 near-pass 证据，否则不要让导数 `pair ratio` 家族重新主导 broad search

动态 ratio 策略：
- `fscore_*` / `fscore_bfl_*` 的 pair-ratio 探索仍然保留
- 密集导数类 partner-ratio 家族，已经明确移出默认 broad-search 策略
- `group_ratio_zscore_*` 和 `group_vol_scaled_delta` 不再是一线默认模板

## 不建议做的事

- 不要把短窗 `delta` 和激进均值回归当作该数据集的一线默认模板。
- 不要让密集导数 pair-ratio 分支重新挤占 broad search，除非后续 refine 证据明显改善。
- 不要仅仅因为“增加了数量”，就把旧的 fallback 包装器重新塞回主模板库。

## 推荐流程

Broad exploration：
- broad search 保持紧凑、假设驱动。
- 优先使用当前整理后的数据集专属模板库，而不是继续扩 shared fallback。
- 让“结构差异”胜过“近邻窗口堆叠”。

Focused refine：
- 只有在明确出现 near-pass 证据后，再用 refine pack 重新打开已下沉分支。
- 相比恢复弱势导数 pair-ratio，更优先扩 `cap-ratio` / `bucket-cap-ratio`

旧模板处理：
- 过去较弱的 fallback 模板保留在 `legacy.json`，不再放在默认主库。
- `mean-reversion`、`information_ratio`、`normalize/quantile` 包装器，以及额外的长窗口近邻，更适合作为 refine/实验分支，而不是默认 broad-search 主力。
- 当前恢复包位于 `templates/model16/refine/broad_search_neighbors.json`

## 待确认问题

- 如果后续运行显示 value/quality/growth 风格字段之间差异足够明显，可以补一个小型 sector-relative spread 家族。
- 继续验证 `information_ratio` 是否还应留在核心默认集，还是进一步下沉到 grouped bucket 变体之后。
