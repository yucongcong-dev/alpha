# fundamental6 说明

## 定位
`fundamental6` 当前应被视为一个慢频基本面数据集。

当前模板库故意偏向以下方向：
- 长窗口稳定化（`60/120/252/504`）
- 多种预处理变体（`backfill+winsorize`、`longfill`、`rawfill`）
- 用 ratio/pair 模板降低 self-correlation
- 用 `densify` 支持 bucket 分组
- 给向量字段使用字段自身变化触发

## 官方口径
- WorldQuant BRAIN 的 alpha examples 明确支持 neutralization、grouped ranking、以及结构化表达式。

官方字段元信息层面：
- 字段筛选和排序会使用 `coverage`、`dateCoverage`、`alphaCount`、`userCount`
- 事件前缀字段通常需要更严格的阈值处理

## 官方数据画像

基于 `2026-07-10` 对 `api.worldquantbrain.com/data-fields` 的官方接口查询：
- 字段总数：`886`
- 字段类型：
  - `MATRIX = 574`
  - `VECTOR = 312`
- 类别分布：
  - `Fundamental = 886`
- 元信息形态：
  - 全部字段 `coverage = 0.5`
  - 全部字段 `dateCoverage = 1.0`
  - 全部字段 `name = null`，实际可用标识就是字段 `id`

数据结构上的明显分层：
- 一层是传统慢频基本面/会计字段，类型为 `MATRIX`
  - 例如：`assets`、`cash_st`、`cashflow_op`、`cogs`、`debt`、`debt_lt`
- 另一层是大量前缀化的事件/派生字段
  - `fnd6_newqeventv110_* = 217`
  - `fnd6_eventv110_* = 35`
  - `fnd6_cptnewqeventv110_* = 19`

拥挤度画像：
- 全体字段中位数：
  - `alphaCount ~= 487`
  - `userCount ~= 246`
- `MATRIX` 字段明显更拥挤：
  - 中位数 `alphaCount ~= 737.5`
  - 中位数 `userCount ~= 346`
- `VECTOR` 字段明显更不拥挤：
  - 中位数 `alphaCount ~= 70`
  - 中位数 `userCount ~= 49.5`

最拥挤的经典字段示例：
- `assets`: `alphaCount=168132`, `userCount=52788`
- `enterprise_value`: `alphaCount=45876`, `userCount=11908`
- `debt`: `alphaCount=31574`, `userCount=12052`
- `capex`: `alphaCount=30914`, `userCount=13471`
- `cashflow_op`: `alphaCount=22809`, `userCount=9407`

相对不拥挤的字段，多数集中在事件/向量支路，而不是经典会计核心字段。

## 对模板设计的直接启示

- `fundamental6` 不是一个“小而纯”的会计数据集，它本质上是“基本面主库 + 大量事件/向量支路”的混合数据集。
- broad-search 默认主干应先围绕拥挤的 `MATRIX` 核心设计，因为大众表达式最容易在那里发生碰撞。
- `VECTOR` 和带 event 前缀的字段应继续独立成分支，因为它们的拥挤度画像和表达式形态，都和普通标量基本面不同。
- 由于官方元信息里统一是 `coverage=0.5`，所以 `backfill/stabilization` 不是偶发修补，而是基础动作。
- 由于官方元信息里统一是 `dateCoverage=1.0`，当前主要问题并不是历史跨度不够，而是更新慢、有效变化稀疏。
- 对高 `alphaCount` 的核心字段，优先考虑 relation-based、grouped、specialty refine 分支，而不是继续堆单字段窗口邻居。

## 本地证据

公开脚本启发：
- 本地 public script 明显强调 `winsorize(ts_backfill(...), std=4)`
- 也使用了 `bucket(...)` 分组和 `trade_when(...)` 触发
- xiegengcai factory 使用 `vec_avg` + `vec_sum` 双通道、`densify()` bucket 分组，以及字段自身变化触发的事件逻辑

本地运行证据：
- 短窗 `delta/group_delta/vol_scaled_delta` 家族在该数据集上持续偏弱
- 更接近阈值的字段与模板家族，多出现在 `cash_st`、`debt`、`debt_lt`、`cogs`、`cashflow_op` 及其相关 ratio 周围
- 事件/向量字段在单独的 `event_conditioned` 支路里表现更合理；混进通用模板池时，表现明显变差
- 模板内 `group_neutralize` 与 settings 层 `neutralization=SUBINDUSTRY` 叠加，会形成双重中性化，压缩信号
- 短窗模板（`20/5`）在季度更新字段上几乎没有有效信号
- v3 模板的 53 条结果全部 `submittable=0`，主因是 self-correlation

## v4 模板调整

1. 去掉模板内中性化：所有模板移除 `group_neutralize`，只依赖 settings 里的 `neutralization=SUBINDUSTRY`
2. 删除短窗模板：去掉 `ts_rank_20`、`ts_zscore_20`、`decay_5`、`stddev_20`、`ir_20`，因为季度字段在 20 天窗口基本无意义
3. 增加预处理变体：
   - `{field_longfill}` = `winsorize(ts_backfill(field, 252), std=3)`
   - `{field_rawfill}` = `ts_backfill(field, 120)`
4. 增加 ratio/pair 模板：补充 `ratio_cap`、`ratio_assets`、`bucket_ratio` 家族，以降低和现有 alpha 的同质化
5. bucket 分组统一加 `densify()`：避免稀疏组问题
6. 事件字段改用自身变化触发：
   - `ts_delta({field}) != 0`
   - `days_from_last_change({field}) <= 5`
   用来替代泛化的 volume/returns 触发
7. 增加 `vec_sum` 变体：和 `vec_avg` 一起形成双通道
8. 增加 hump 参数扫描：`0.2/0.3/0.4/0.5`
9. 增加长窗口变体：`ts_rank_504`、`ts_zscore_126`、`decay_120`

## 默认模板库边界

当前默认库应理解为：给 broad exploration 用的、窄化后的生产主队列。

核心原则：
- `default` 里只保留 5 个慢频核心种子
- vector / event-conditioned 家族是专项分支，不是通用 broad-search 默认种子
- 对 `VECTOR / GROUP / SET`，broad 中只保留最小代表主干；把 `zscore` 邻居和 `252` 天邻居下沉到 refine
- cross-field ratio/pair 探索集中在 account/matrix 专用支路，不要把 scalar `default` 撑得过宽
- 额外长窗口邻居、`rawfill/longfill` 近邻、旧式横截面包装器，如果没有反复证明有效，就都作为 refine 候选
- 单独的 decay 邻居、liquidity-bucket 变体，也都更适合作为 refine 候选，而不是 broad-search 默认
- 当前这些被下沉分支的恢复包在 `templates/fundamental6/refine/default_neighbors.json`

Refine pack 约定：
- `default_neighbors.json` 现在应被理解为新默认主干外侧的一圈扩展带，而不是旧 scalar 剩余物的堆放地
- 它主要负责扩以下内容：
  - 保留下来的慢频模板的更快/更慢邻居
  - 更长窗口的 `ratio_cap` / `bucket_ratio` 变体
  - 围绕 `cap` 和流动性分层的 grouped bucket 变体
  - 过于具体、不适合放进 broad 默认队列的次级 event-self-change 路径

## 不建议做的事

- 不要把短窗模板当作季度更新字段的一线默认模板。
- 不要把 event/vector 专用家族重新混回通用 scalar broad-search 池。
- 不要重新引入模板内 `group_neutralize`，再和 settings 层 `neutralization=SUBINDUSTRY` 叠加。

## 哪些方向更适合 fundamental6

- 慢频单字段稳定器，例如 `ts_rank_120`、`ts_zscore_252`、以及 `zscore + decay` 复合主干
- 排序前做较重的预处理，尤其是 `ts_backfill + winsorize`
- relation-based 模板，例如 `ratio_cap`、`ratio_assets`、`bucket_ratio` 等跨字段比较
- 带 `densify(...)` 的 bucket/group 结构，尤其是围绕 `cap` 和流动性分层
- 用字段自身变化触发的 VECTOR/event 模板，而不是泛化市场活跃度触发
- 默认 broad-search 先窄，再接 refine pack，而不是第一轮就压入大量近似模板

## 哪些方向通常表现较差

- 在慢更新基本面字段上使用 `5/20` 这类短窗 rank、zscore、decay 家族
- 一大批只在邻近窗口上微调的单字段模板
- 把 scalar、vector、event-conditioned 结构混进同一个通用 broad-search 池
- 双重中性化：模板内 `group_neutralize` + settings 层 `neutralization=SUBINDUSTRY`
- 在主要失败模式已经明确后，仍然用 broad search 单纯放大数量
- 把 `vec_avg / vec_sum` 邻居和更长窗口邻居，当作第一轮默认模板，而不是第二轮 refine 分支

## 推荐流程

Broad exploration：
- 默认主干保持窄，并且显式适配慢频数据
- vector/event-conditioned 支路保持专项化，不和通用 broad-search 默认种子混用
- 让 field-relation 模板逐步替代单字段变换的堆叠

Focused refine：
- refine pack 作为慢频默认主干外围的扩展带使用
- 只有在主 scalar 主干被验证后，再扩 ratio/bucket/event-self-change 邻居

## 第一轮研究流程

1. 从窄化后的 `default` 主干开始，而不是从 refine pack 开始
2. 第一轮 broad search 只跑一个小批次，回答三个问题：
   - 是否出现 `near_pass`
   - 是否仍由 `self-correlation` 主导失败
   - 哪些字段家族反复接近阈值
3. 优先阅读这些已知更有希望的字段家族：
   - `cash_st`
   - `debt`
   - `debt_lt`
   - `cogs`
   - `cashflow_op`
   - 相关 ratio 字段
4. 如果结果反复显示 near-threshold，就切换到 `refine/default_neighbors.json`，而不是继续拓宽 `default`
5. 如果结果仍然是高度同质化失败，就增加 field-relation 结构，而不是增加更多 scalar 邻居
6. 只有在主 scalar 主干基本看清后，再打开专项支路：
   - vector/event-conditioned 分支
   - grouped bucket 分支
   - 长窗口 relation 邻居

第一轮的实际目标：
- 判断窄化后的 broad 主干，是否已经产生更有区分度的失败，而不是旧的 self-correlation 重复模式
- 找出 1 到 3 个值得单独 refine 的字段家族

## 待确认问题

- 继续推动从单字段变换，转向 field-relation 模板。
- 继续评估剩余的通用 `ts_rank/ts_zscore/stddev` 默认模板，是否还能进一步收窄。
- 持续把“官网直接支持的结论”和“本地运行推导出来的结论”分开记录。
