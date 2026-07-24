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

模型字段中的 `score / rate / rank` 不应默认视为同一种数值：`score` 往往保留模型幅度，`rank` 更强调相对顺序，`rate` 需要结合字段描述确认是变化率、评级还是概率。首次使用前应分别检查分布、覆盖、更新频率和方向，避免对已经排名过的字段重复做无意义的重排序。

`STATISTICAL` 或 Consultant 专属的 Slow/Fast Factor neutralization 只适合作为显式实验设置。未确认当前账号和 Region 支持前，不进入默认模板与批量配置。

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
- 从 `2026-07-24` 起，默认 `library.json` 已被收成真正的闭合候选集：
  - 默认 broad run 不再偷偷混入自动生成的 MATRIX 邻居
  - 也不再把 feedback mutation 静默扩回默认计划
  - 因此现在看到的默认 dry-run / 实跑结果，才真正对应这份 README 里描述的窄模板库
- 当前受保护的核心模板，明显偏向 `126` 天结构和带分组语义的排序。
- 最近 `stage2_lane_validation_round2` 的结果表明，密集导数类 partner-ratio 分支系统性偏弱：
  - `high_conviction_ratio`、`group_ratio_zscore` 经常被 `LOW_SHARPE` 和 `LOW_FITNESS` 卡住
  - `group_vol_scaled_delta` 多次因 `CONCENTRATED_WEIGHT` 和较弱的子域表现失败
  - 因此，默认 broad search 不该再把这些导数 pair-ratio 分支当作第一候选
- `2026-07-20 round3_dense_derivative_focus` 又做了一轮更窄的定向验证：
  - 只保留 6 个 dense derivative 字段
  - 只围绕 `bucket_cap_ratio_zscore_120` 和 `ratio_cap_zscore_120` 这两条旧主干复核
  - 最终 `tested=34`、`submittable=0`
  - 没有产生任何新增可提交结果
- 这轮里最稳定的重复形态非常一致：
  - `bucket_cap_ratio_zscore_120` 大多停在 `Sharpe ~= 0.77 ~ 0.82`、`Fitness ~= 0.63 ~ 0.64`
  - `ratio_cap_zscore_120` 大多停在 `Sharpe ~= 0.66 ~ 0.67`、`Fitness ~= 0.50 ~ 0.51`
  - 个别 refine 邻居把 `Sharpe` 抬到约 `0.94`，但 `Fitness` 仍停在 `0.63`
- 因此当前更准确的判断是：
  - `model16` 不是没有稳定结构，而是稳定结构已经反复复现，却始终过不了质量门槛
  - 当前主问题不是“还没找到方向”，而是“已知方向没有继续抬升”
- `2026-07-24 entry_validation` 的第一条真实新结果再次确认了这个结论：
  - 字段：`analyst_revision_rank_derivative`
  - 模板：`model16_bucket_cap_ratio_zscore_120`
  - 结果：`LOW_SHARPE = 0.82`、`LOW_FITNESS = 0.64`
  - 这说明即便在“默认库已闭合、无杂模板污染”的前提下，当前主干还是停留在同一质量天花板附近

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
- 但在 `2026-07-20 round3_dense_derivative_focus` 之后，`cap-ratio` / `bucket-cap-ratio` 这条支路也应暂时停止继续加预算，除非平台状态或字段集合发生明显变化。
- `2026-07-24` 的闭合默认库实跑没有改变这个结论，因此当前不建议把 `model16` 提升为新的主预算数据集。

旧模板处理：
- 过去较弱的 fallback 模板已经从默认主库下沉，不再作为 broad-search 默认入口。
- `mean-reversion`、`information_ratio`、`normalize/quantile` 包装器，以及额外的长窗口近邻，更适合作为 refine/实验分支，而不是默认 broad-search 主力。
- 当前恢复包位于 `templates/model16/refine/broad_search_neighbors.json`

## 待确认问题

- 如果后续运行显示 value/quality/growth 风格字段之间差异足够明显，可以补一个小型 sector-relative spread 家族。
- 继续验证 `information_ratio` 是否还应留在核心默认集，还是进一步下沉到 grouped bucket 变体之后。
- 如果未来还要重启 `model16`，优先前提不该是“再试更多近邻”，而应该是：
  - 字段池出现新成员
  - 平台阈值或市场环境明显变化
  - 或者有新的结构假设，不再只是重复 `120` 天的 `ratio_cap / bucket_ratio`
