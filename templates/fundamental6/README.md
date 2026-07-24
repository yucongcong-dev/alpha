# fundamental6 说明

## 执行摘要

如果只看一页，当前 `fundamental6` 可以直接理解成下面这张状态卡：

- 正式主干：
  - `cashflow_op`
  - 主表达式分成两条已验证主线：
    - `group_rank(ts_zscore(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 252), subindustry/industry)`
    - `group_rank(ts_delta(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 63) / ts_std_dev(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 126), subindustry)`
- 已验证通过：
  - `cashflow_op / cap / grouped zscore_252`
  - `cashflow_op / cap / group delta-over-std 63/126`
- 近通过但未过线：
  - `ts_decay_linear(group_rank(ts_zscore(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 252), subindustry), 20)`
  - 常见卡点：`LOW_SHARPE ~= 1.20~1.21`、`LOW_FITNESS ~= 0.78~0.79`
- 事件型备选：
  - `cogs`
  - 最强也只到大约 `Sharpe ~= 0.89`、`Fitness ~= 0.79`
- 向量观察线：
  - `fnd6_cptnewqeventv110_lctq`
  - 当前只保留 `vec_avg_decay_120`
- 已降级字段：
  - `fnd6_cptnewqeventv110_dpq`

当前阶段结论：

- `fundamental6` 已经不是“继续找方向”的阶段，而是“接受单主线现实，并控制备选线预算”的阶段
- 最值得投入的仍然是 `cashflow_op` submit-oriented 微调
- `cogs` 和 `lctq` 都保留研究价值，但都不应继续拿主预算大规模扩张
- `dpq` 当前可以视为低优先级暂停线

当前推荐动作：

1. 把 `cashflow_op` 视为唯一正式主干。
2. 把 `cogs` 作为已验证但不过线的事件备选保留。
3. 把 `lctq` 作为长期观察哨兵，仅保留最小观察包。
4. 暂停继续追“第二主线”，除非后续平台或字段状态发生明显变化。

补充：

- 截至 `2026-07-16 round14`，`cashflow_op` 已经不再只是“一条 grouped zscore 主干”
- 它已经确认长出了第二条可提交分支：`group delta-over-std 63/126 over cap`
- 因此当前最稳的理解应是：
  - 数据集层面仍然是“单字段主干”
  - 但字段层面已经是“单字段双结构主线”

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
- 官网按数据类别给出的通用建议是：Fundamental Dataset 优先以 `Industry` Neutralization
  作为基线，因为同一基本面指标对不同行业的含义通常不同。

官方字段元信息层面：
- 字段筛选和排序会使用 `coverage`、`dateCoverage`、`alphaCount`、`userCount`
- 事件前缀字段通常需要更严格的阈值处理
- 当目标 Region 的 Fundamental 使用占比过高时，平台可能暂时禁用相关字段的模拟和提交；需要在 [Alpha distribution](https://platform.worldquantbrain.com/alphas/distribution) 降到 `15%` 以下后恢复访问

## 基本面假设地图

默认模板不应只按字段名扫库，而应先归入可解释的财务假设：

- 盈利能力：利润、毛利、经营利润相对资产、收入或资本的效率
- 流动性：现金、短期资产和短期负债之间的偿付能力
- 偿债能力：债务、利息负担与资产或现金流之间的关系
- 现金流质量：经营现金流相对利润、资产、收入或市值的质量
- 成长：收入、利润、资产和现金流的中长期变化
- 估值：企业价值或市值相对利润、现金流、资产的定价

优先构造有财务恒等式或关系约束支撑的表达式，例如资产与负债/权益、收入与费用、现金流利润与应计利润的差异。现金流显著强于会计利润时可能代表更高盈利质量；利润增长但经营现金流没有同步时，应警惕应计项驱动。

行业口径不一致时，可以围绕资产规模、流动性或自定义财务分类构造 `bucket + densify` 分组，但要控制组数并验证每组样本量。

## Neutralization 建议

官方类别级建议和本地运行证据需要同时保留：

- 官方基线：`Industry`
- 本地已验证挑战版本：`Subindustry`
- `cashflow_op / cap` 这类 grouped relation，应同时保留 Industry 和 Subindustry 对照
- 模板内使用 `group_rank / group_zscore` 不等于已经中性化；仍需明确 settings 层策略
- 模板内使用 `group_neutralize` 时，settings 层设为 `None`，避免双重中性化
- 市值或流动性 bucket 统一先经过 `densify()`，并控制 bucket 数量，避免小组样本过少

选择最终 Neutralization 时，不只比较最高 Sharpe，还要同时看 Sub-Universe、
权重集中度和相邻设置的稳定性。

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

## 当前阶段结论

基于 `2026-07-10` 到 `2026-07-13` 的 `round3 -> round6` 本地运行结果，`fundamental6` 当前已经不再处于“找方向”阶段，而是进入“围绕已验证主线做 submit-oriented 深挖”阶段。

阶段性结论：
- 当前最强、最稳定的主线是：
  - `cashflow_op`
  - `field / cap`
  - `ts_zscore(..., 252)`
  - `group_rank(..., subindustry/industry)`
- 已经稳定打出 `submittable` 的表达式包括：
  - `group_rank(ts_zscore(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 252), subindustry)`
  - `group_rank(ts_zscore(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 252), industry)`
  - `group_rank(ts_delta(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 63) / ts_std_dev(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 126), subindustry)`
- 最接近门槛、但还未正式过线的 near-pass 主线是：
  - `ts_decay_linear(group_rank(ts_zscore(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 252), subindustry), 20)`
  - 它通常卡在：
    - `LOW_SHARPE ~= 1.20~1.21`
    - `LOW_FITNESS ~= 0.78~0.79`

这说明：
- `cashflow_op + cap + grouped zscore_252` 不是偶然结果，而是当前数据集里已经被重复验证的 submit 主干
- `cashflow_op + cap + grouped delta-over-std 63/126` 也已经被验证成第二条可提交结构
- `subindustry` 与 `industry` 两个 grouped 版本都值得保留
- 相比之下，普通单字段 `decay/zscore` 模板大多只是“能跑”，不是“能交”

## 2026-07-16 round14 新增结论

`round14` 的价值很高，因为它把 `cashflow_op` 主线从“单结构成功”推进到了“同字段双结构成功”。

新增确认的可提交分支：

- `group_rank(ts_delta(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 63) / ts_std_dev(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 126), subindustry)`

对应判断：

- `cashflow_op` 当前应理解为两条正式主线并存：
  - `grouped zscore over cap`
  - `group delta-over-std over cap`
- 之前那条 `ts_decay_linear(..., 20)` 近通过分支依然没过线
- 但它仍保持在：
  - `LOW_SHARPE ~= 1.20 ~ 1.21`
  - `LOW_FITNESS ~= 0.78 ~ 0.79`

这轮同时也明确淘汰了一批 refine 方向：

- `industry decay` 明显弱于 `subindustry decay`
- `backfill 504` 方向变差
- `trade_when(volume)` 包装会削弱原有 near-pass 主干

因此从 `2026-07-16 round14` 之后，`cashflow_op` 的推荐优先级应调整为：

1. `grouped zscore over cap`
2. `group delta-over-std over cap`
3. `subindustry decay near-pass`
4. 停止继续投入 `industry decay` / `backfill 504` / `trade_when(volume)` 这些弱 refine

## 已验证的分层判断

主战场：
- `cashflow_op` 是当前最值得继续投入算力的字段
- 应优先使用 relation/grouped 结构，而不是继续堆普通时间窗邻居

次优观察线：
- `cogs + decay_120`
  - 强度不算差，但反复卡在 `LOW_TURNOVER`
- `VECTOR decay_120`
  - `fnd6_cptnewqeventv110_lctq`
  - `fnd6_cptnewqeventv110_dpq`
  - 这两条在修复双重 `vec_avg` 后已稳定可跑，但当前还不如 `cashflow_op` 主线接近提交

弱线 / 暂停线：
- `cash_st`
- `cashflow`
- 普通 `ts_zscore_126/252`
- 普通 `decay_120/252`
- 慢频字段上的短窗或轻微窗口微调

这些方向当前更容易出现的问题是：
- `LOW_SHARPE`
- `LOW_FITNESS`
- `LOW_TURNOVER`
- 或者只是和已知强表达式高度相似，但没有新增价值

## 相关性风险判断

围绕 `cashflow_op` 继续探索，短期内是合理的，但长期只盯一个字段会有明显风险：
- 容易和自己已有表达式发生高 `self-correlation`
- 容易把很多算力花在“同一条信号的小改版”上
- 组合层面的新增价值会越来越低

因此当前建议是：
- 短期：
  - 继续允许围绕 `cashflow_op` 做 1 到 2 轮 submit-oriented 微调
- 中期：
  - 尽快从“单字段 submit”转向“同结构异字段簇扩张”
- 长期：
  - 用字段簇轮换，替代字段单点深挖

更稳的扩张单位应是“字段簇”，而不是单字段：
- 经营现金流簇
- 成本/支出簇
- 事件型 VECTOR 簇

## 当前建议执行顺序

1. 先把 `cashflow_op` 已通过主线视为正式主干。
2. 只对 `cashflow_op` 的 grouped zscore_252 近邻做小范围提交导向微调。
3. 将 `cogs decay_120` 和 `VECTOR decay_120` 保留为备选观察线，而不是主战场。
4. 暂停大范围字段扩搜和 broad-search 回滚。
5. 下一阶段从“单字段 submit”过渡到“同结构多字段簇扩张”。

## 2026-07-16 阶段切换

基于 `round8 -> round11` 的连续验证，当前执行策略需要明确切换：

- `cogs` 线到此为止只保留研究结论，不再继续消耗主预算
- 原因不是流程没修好，而是它在去重修复后仍稳定卡在：
  - `LOW_SHARPE ~= 0.88 ~ 0.89`
  - `LOW_FITNESS ~= 0.77 ~ 0.79`
- 因此 `cogs` 当前应被视为“已验证但不过线”的事件型备选线

下一阶段应改成“第二主线候选字段簇”探索，而不是继续压同一条 `cogs` 表达式。

推荐的 round12 候选字段簇：

- `fnd6_cptnewqeventv110_lctq`
- `fnd6_cptnewqeventv110_dpq`

这两个字段的共同特点是：

- 属于低拥挤的 `VECTOR / event-like` 支路
- 在 `round7` 中都比大多数普通弱线更接近阈值
- 当前还明显弱于 `cashflow_op` 主干，但比继续打 `cogs` 更值得拿预算验证

对应字段文件：

- `templates/fundamental6/refine/archive/fields/clean_verify_round12_second_line_fields.txt`

推荐执行包：

- `templates/fundamental6/refine/archive/round7_low_corr_pack.json`

推荐用途：

- 不是为了立刻 submit
- 而是为了回答“`cashflow_op` 之外，哪个字段簇最像第二主线”

如果 round12 之后这两个字段仍明显低于：

- `Sharpe < 0.9`
- `Fitness < 0.75`

那就说明当前 `fundamental6` 阶段应暂时接受“单主线 + 多备选线”的现实，不要再强行追求第二主线。

## 2026-07-16 round12 后续结论

`round12` 已经把第二主线候选字段簇试了一轮，结果可以进一步收口：

- `lctq` 明显强于 `dpq`
- 但两者都没有达到第二主线门槛
- 当前更合理的做法不是继续并行扩字段，而是把 `lctq` 单独保留为最小观察线

当前对这两条字段的判断：

- `lctq`
  - 最强表达式仍是 `vec_avg_decay_120`
  - 大约停留在 `Sharpe ~= 0.79`、`Fitness ~= 0.67`
  - 可以保留为 `VECTOR` 观察线
- `dpq`
  - 最强表达式仍是 `vec_avg_decay_120`
  - 大约停留在 `Sharpe ~= 0.71`、`Fitness ~= 0.57`
  - 可继续降级，不再作为优先候选

因此从 `2026-07-16 round12` 之后，推荐结构变成：

- 正式主干：`cashflow_op`
- 事件型备选：`cogs`
- 向量观察线：`lctq`
- 暂停线：`dpq`

为避免 `VECTOR` 观察线再次扩散成大包，新增一个最小观察包：

- `templates/fundamental6/refine/lctq_watch_pack.json`

对应字段文件：

- `templates/fundamental6/refine/fields/clean_verify_round13_lctq_watch_field.txt`

这个包的设计原则是：

- 只保留 `lctq` 当前最有信息量的 1 条主干
- 不再保留 `decay_252`，因为它没有形成额外增量证据
- 不再保留 `volume` 触发邻居，因为 `round13` 已证实它略弱于主干
- 不再保留明显偏弱的 `ts_rank_252`
- 不再继续把 `lctq` 当“第二主线候选簇”扩张，而是把它当“长期观察哨兵”

`round13` 之后，`lctq_watch_pack.json` 应理解为：

- 只剩一条主表达式：`vec_avg_decay_120`
- 作用不是为了 submit，而是为了长期监控 `VECTOR` 支路是否有自然改善

## 2026-07-16 round14 后的最小提交资产

为了避免后续每次都从大 refine 包里挑主线，当前 `cashflow_op` 已经单独收成一个最小提交包：

- `templates/fundamental6/refine/cashflow_submit_core_pack.json`

这个包只保留两条已验证可提交主线：

- `grouped zscore over cap`
- `group delta-over-std 63/126 over cap`

对应用途：

- 最小复跑
- 主干稳定性验证
- 提交前快速健康检查

推荐直接使用闭环验证脚本：

```bash
./scripts/run_fundamental6_cashflow_core_verify.sh --dry-run-plan
./scripts/run_fundamental6_cashflow_core_verify.sh
```

这个脚本默认会带上：

- `--stop-after-submittable 1`
- `--no-auto-update-blacklist`
- `cashflow_submit_core_pack.json`
- `clean_verify_round6_submit_field.txt`

这样它的目标很明确：

- 只验证当前最小主干是否还能稳定产出
- 一旦拿到 1 条可提交结果就收口
- 不让最小验证包自动扩散成 refine 长链
- 它是“软收口”: 已经发出去的 pending 任务会继续收尾，但不会再继续进入 refine 放大

如果省略 `--stop-after-submittable`，当前流程会继续：

- 扩到同字段更多 settings / 邻居模板
- 在出现 near-pass 或已通过结果后继续进入 refine 派生
- 导致“小包验证”变成“放大式精修”

它不再包含：

- `decay` near-pass 邻居
- `industry` 弱版本
- `backfill 504` 弱 refine
- `trade_when(volume)` 弱包装

## 2026-07-16 round15 最小提交包复核

`round15` 的意义，不是继续找新结构，而是验证上面这个最小提交包能不能稳定复跑。

对应结果文件：

- `results/fundamental6/clean_verify_round15_cashflow_core_analysis.json`
- `results/fundamental6/clean_verify_round15_cashflow_core_results.jsonl`

核心结果：

- `tested = 15`
- `submittable = 3`
- 但其中有 1 条是同一表达式的重复命名记录
- 因此按唯一表达式看，当前仍然只有 2 条稳定可提交主线

这两条稳定主线分别是：

- `group_rank(ts_zscore(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 252), subindustry)`
- `group_rank(ts_delta(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 63) / ts_std_dev(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 126), subindustry)`

同时也再次确认一批弱 refine 没有恢复：

- `group level over cap` 仍只有大约 `Sharpe ~= 0.8`、`Fitness ~= 0.61`
- `industry` 版本仍弱于 `subindustry`
- `trade_when(volume)` 包装仍会削弱主干
- 小 `decay` 邻居没有形成新增提交价值

所以 `round15` 的真正结论是：

- `cashflow_submit_core_pack.json` 已经可以视为后续 `fundamental6` 的最小复跑资产
- 当前阶段不应再对这些弱 refine 抱有“再跑一次也许会变强”的预期
- `fundamental6` 的重点已经从“继续扩模板”转成“围绕双主线做低频复核和提交运营”

## 2026-07-17 round16 低频复跑确认

`round16` 的意义，是在新一天重新跑一次同一个最小提交包，确认主干没有漂移。

对应结果文件：

- `results/fundamental6/clean_verify_round16_cashflow_core_analysis.json`
- `results/fundamental6/clean_verify_round16_cashflow_core_results.jsonl`

核心结果：

- `tested = 15`
- `submittable = 3`
- `error_count = 0`
- 其中仍有 1 条是同一表达式的重复命名记录
- 所以按唯一表达式看，结论仍然是 2 条稳定可提交主线

再次复现的两条正式主线：

- `group_rank(ts_zscore(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 252), subindustry)`
- `group_rank(ts_delta(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 63) / ts_std_dev(winsorize(ts_backfill(cashflow_op, 120), std=4)/cap, 126), subindustry)`

同时也再次确认弱 refine 仍然没有恢复：

- `group level over cap` 仍大约只有 `Sharpe ~= 0.80`、`Fitness ~= 0.61`
- `industry` 版本仍大约只有 `Sharpe ~= 0.76 ~ 0.78`、`Fitness ~= 0.61 ~ 0.62`
- `trade_when(volume)` 仍大约只有 `Sharpe ~= 0.78 ~ 0.80`、`Fitness ~= 0.58 ~ 0.60`
- `decay(6)` 仍大约只有 `Sharpe ~= 0.78`、`Fitness ~= 0.58`

这说明：

- `round16` 不是发现了新主线，而是再次确认旧结论稳定
- `cashflow_submit_core_pack.json` 已经具备“跨天低频复跑”的最小运营价值
- 当前 `fundamental6` 不应再继续扩这些已验证偏弱的 refine 邻居

## 2026-07-24 闭环验证流程修正

`2026-07-24` 的一次真实小批次运行，把一个容易被忽略的问题跑实了：

- `cashflow_submit_core_pack.json` 文件里虽然只有 2 条主模板
- 但如果只是直接运行，而不设置 `--stop-after-submittable`
- 当前调度会继续扩到更多 settings 组合、邻居模板，甚至自动进入 refine 链

这意味着：

- “最小提交包”本身没问题
- 真正缺的不是模板，而是验证流程的停止边界

因此从这一天开始，`fundamental6` 的最小复跑应该固定理解为：

- 用 `cashflow_submit_core_pack.json`
- 用单字段白名单 `clean_verify_round6_submit_field.txt`
- 显式设置 `--stop-after-submittable 1`
- 默认关闭 blacklist 自动更新

如果目标不是健康检查，而是继续放大可提交结果，那才应该故意去掉这个停止条件。

## 模板包阶段角色

到当前阶段，`fundamental6` 的本地资产应按“现役 / 观察 / 归档”理解：

现役：
- `templates/fundamental6/library.json`
  - 第一阶段 broad 主干探索
- `templates/fundamental6/refine/default_neighbors.json`
  - 第二阶段现役 refine 扩展带
  - 只保留仍有增量价值的 `cashflow_op` 主线近邻，以及最小 `VECTOR` 哨兵
- `templates/fundamental6/refine/cashflow_submit_core_pack.json`
  - 最小复跑、主干健康检查、提交前低成本稳定性确认

观察：
- `templates/fundamental6/refine/lctq_watch_pack.json`
  - 长期观察 `VECTOR` 支路是否自然改善
  - 不是 submit 主包

归档：
- `templates/fundamental6/refine/archive/*.json`
  - 保存 round5~round9 这类历史轮次包
  - 用途是回看结论，不再作为现役执行入口
- `templates/fundamental6/refine/archive/fields/*.txt`
  - 保存历史字段白名单 fixture
  - 当前只保留观察线所需的最小字段文件在现役目录

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

当前默认库应理解为：给 broad exploration 用的、进一步窄化后的生产主队列。

核心原则：
- `default` 里只保留 4 个慢频核心种子
- vector / event-conditioned 家族是专项分支，不是通用 broad-search 默认种子
- 对 `VECTOR`，broad 中只保留单通道最小代表主干；`GROUP / SET` 在 `fundamental6` 当前不作为现役分支维护
- cross-field ratio/pair 探索集中在 account/matrix 专用支路，不要把 scalar `default` 撑得过宽
- 额外长窗口邻居、`rawfill/longfill` 近邻、旧式横截面包装器，如果没有反复证明有效，就都作为 refine 候选
- 单独的 decay 邻居、liquidity-bucket 变体，也都更适合作为 refine 候选，而不是 broad-search 默认
- 当前这些仍值得保留的恢复分支，收敛在 `templates/fundamental6/refine/default_neighbors.json`

Refine pack 约定：
- `default_neighbors.json` 现在应被理解为新默认主干外侧的一圈“现役扩展带”，而不是旧 scalar 剩余物的堆放地
- 它主要负责扩以下内容：
  - `cashflow_op` 当前两条正式主线附近的低预算验证邻居
  - 仍接近门槛的 `subindustry decay near-pass`
  - 一个最小 `VECTOR` 观察哨兵
- 已被证伪或只剩历史价值的 `industry` 弱版本、`backfill 504`、`trade_when(volume)`、大批普通时间窗邻居，都下沉到 `archive/`

## 不建议做的事

- 不要把短窗模板当作季度更新字段的一线默认模板。
- 不要把 event/vector 专用家族重新混回通用 scalar broad-search 池。
- 不要重新引入模板内 `group_neutralize`，再和 settings 层 `neutralization=SUBINDUSTRY` 叠加。

## 哪些方向更适合 fundamental6

- 慢频单字段稳定器，例如 `ts_rank_120`，以及 `zscore + decay` 复合主干
- 排序前做较重的预处理，尤其是 `ts_backfill + winsorize`
- relation-based 模板，例如 `ratio_cap`、`ratio_assets`、`bucket_ratio` 等跨字段比较
- 带 `densify(...)` 的 bucket/group 结构，尤其是围绕 `cap` 和流动性分层
- 用字段自身变化触发的 VECTOR/event 模板，而不是泛化市场活跃度触发
- 默认 broad-search 先窄，再接 refine pack，而不是第一轮就压入大量近似模板
- 对高拥挤经典字段，先用 relation/grouped 主干，再把额外单字段邻居留到 refine

## 哪些方向通常表现较差

- 在慢更新基本面字段上使用 `5/20` 这类短窗 rank、zscore、decay 家族
- 一大批只在邻近窗口上微调的单字段模板
- 把 scalar、vector、event-conditioned 结构混进同一个通用 broad-search 池
- 双重中性化：模板内 `group_neutralize` + settings 层 `neutralization=SUBINDUSTRY`
- 在主要失败模式已经明确后，仍然用 broad search 单纯放大数量
- 把 `vec_sum` 双通道邻居和更长窗口邻居，当作第一轮默认模板，而不是第二轮 refine 分支

## 推荐流程

Broad exploration：
- 默认主干保持窄，并且显式适配慢频数据
- vector/event-conditioned 支路保持专项化，不和通用 broad-search 默认种子混用
- 让 field-relation 模板逐步替代单字段变换的堆叠

Focused refine：
- 现役 `refine/default_neighbors.json` 只负责主线近邻与最小观察哨兵
- 只有在主 scalar 主干被验证后，再扩少量 submit-oriented 邻居
- 如果只是回看历史结论，去 `refine/archive/`，不要直接把历史包当现役入口

## blacklist 的当前作用

- `blacklists/fundamental6/blacklist.json` 仍然有保留必要
- 原因不是它现在内容丰富，而是运行时策略仍会读写这个文件；它是统一 blacklist 机制的一部分，不是纯文档摆设
- 当前它为空，意味着：
  - 现阶段 `fundamental6` 的主问题已经主要通过模板收窄和流程收口解决
  - 还没有新的稳定弱模板需要沉淀成 dataset 级 blacklist 规则
- 因此现在更合理的做法是“保留空文件作为运行时边界”，而不是删除整个目录

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
