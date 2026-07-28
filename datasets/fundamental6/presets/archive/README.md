# fundamental6 历史专项预设与验证记录

历史专项预设归档在这里。

- 这些文件用于回看阶段结论和复盘过程。
- 它们不再作为 `fundamental6` 当前的现役执行入口。
- 当前现役入口只保留：
  - `../default_neighbors/template.json`
  - `../cashflow_submit_core/template.json`
  - `../cashflow_submit_zscore_core/template.json`
  - `../lctq_watch/template.json`

新增结论如果已经影响当前执行方式，应先更新数据集根 README 的执行摘要；
逐轮证据、已停止分支和历史命令再记录在本文件。

## 逐轮验证记录
### 2026-07-16 round14 新增结论

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

### 已验证的分层判断

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

### 相关性风险判断

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

### 当时建议执行顺序

1. 先把 `cashflow_op` 已通过主线视为正式主干。
2. 只对 `cashflow_op` 的 grouped zscore_252 近邻做小范围提交导向微调。
3. 将 `cogs decay_120` 和 `VECTOR decay_120` 保留为备选观察线，而不是主战场。
4. 暂停大范围字段扩搜和 broad-search 回滚。
5. 下一阶段从“单字段 submit”过渡到“同结构多字段簇扩张”。

### 2026-07-16 阶段切换

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

- `datasets/fundamental6/presets/archive/clean_verify_round12_second_line/fields.txt`

推荐执行包：

- `datasets/fundamental6/presets/archive/round7_low_corr/template.json`

推荐用途：

- 不是为了立刻 submit
- 而是为了回答“`cashflow_op` 之外，哪个字段簇最像第二主线”

如果 round12 之后这两个字段仍明显低于：

- `Sharpe < 0.9`
- `Fitness < 0.75`

那就说明当前 `fundamental6` 阶段应暂时接受“单主线 + 多备选线”的现实，不要再强行追求第二主线。

### 2026-07-16 round12 后续结论

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

- `datasets/fundamental6/presets/lctq_watch/template.json`

对应字段文件：

- `datasets/fundamental6/presets/lctq_watch/fields.txt`

这个包的设计原则是：

- 只保留 `lctq` 当前最有信息量的 1 条主干
- 不再保留 `decay_252`，因为它没有形成额外增量证据
- 不再保留 `volume` 触发邻居，因为 `round13` 已证实它略弱于主干
- 不再保留明显偏弱的 `ts_rank_252`
- 不再继续把 `lctq` 当“第二主线候选簇”扩张，而是把它当“长期观察哨兵”

`round13` 之后，`lctq_watch preset` 应理解为：

- 只剩一条主表达式：`vec_avg_decay_120`
- 作用不是为了 submit，而是为了长期监控 `VECTOR` 支路是否有自然改善

### 2026-07-16 round14 后的最小提交资产

为了避免后续每次都从大 refine 包里挑主线，当前 `cashflow_op` 已经单独收成一个最小提交包：

- `datasets/fundamental6/presets/cashflow_submit_core/template.json`

这个包只保留两条已验证可提交主线：

- `grouped zscore over cap`
- `group delta-over-std 63/126 over cap`

对应用途：

- 最小复跑
- 主干稳定性验证
- 提交前快速健康检查

推荐直接使用下面这组等价命令：

```bash
PYTHONPATH=src python3.10 -m alpha --dry-run-plan \
  --dataset-id fundamental6 \
  --template-library-file datasets/fundamental6/presets/cashflow_submit_core/template.json \
  --include-fields-file datasets/fundamental6/presets/cashflow_submit_core/fields.txt \
  --include-templates-file datasets/fundamental6/presets/cashflow_submit_core/templates.txt \
  --limit 1 \
  --max-templates-per-field 5 \
  --max-templates-per-family 2 \
  --field-template-batch-size 1 \
  --stop-after-submittable 1 \
  --no-auto-update-blacklist \
  --run-name verify_cashflow_core_$(date +%F)

PYTHONPATH=src python3.10 -m alpha \
  --dataset-id fundamental6 \
  --template-library-file datasets/fundamental6/presets/cashflow_submit_core/template.json \
  --include-fields-file datasets/fundamental6/presets/cashflow_submit_core/fields.txt \
  --include-templates-file datasets/fundamental6/presets/cashflow_submit_core/templates.txt \
  --limit 1 \
  --max-templates-per-field 5 \
  --max-templates-per-family 2 \
  --field-template-batch-size 1 \
  --stop-after-submittable 1 \
  --no-auto-update-blacklist \
  --run-name verify_cashflow_core_$(date +%F)
```

这组命令固定使用：

- `--stop-after-submittable 1`
- `--no-auto-update-blacklist`
- `cashflow_submit_core preset`
- `cashflow_submit_core preset` 的 `fields.txt` 和 `templates.txt`

这样它的目标很明确：

- 只验证当前最小主干是否还能稳定产出
- 一旦拿到 1 条可提交结果就收口
- 不让最小验证包自动扩散成 refine 长链
- 它是“软收口”: 已经发出去的 pending 任务会继续收尾，但不会再继续进入 refine 放大
- 它验证的是“可提交资格”，不是自动正式提交

当前现役闭环入口应理解为：

- 模板包：`datasets/fundamental6/presets/cashflow_submit_core/template.json`
- 字段白名单：`datasets/fundamental6/presets/cashflow_submit_core/fields.txt`
- 模板白名单：`datasets/fundamental6/presets/cashflow_submit_core/templates.txt`
- 执行方式：直接运行上面的固定命令

如果省略 `--stop-after-submittable`，当前流程会继续：

- 扩到同字段更多 settings / 邻居模板
- 在出现 near-pass 或已通过结果后继续进入 refine 派生
- 导致“小包验证”变成“放大式精修”

它不再包含：

- `decay` near-pass 邻居
- `industry` 弱版本
- `backfill 504` 弱 refine
- `trade_when(volume)` 弱包装

### 2026-07-16 round15 最小提交包复核

`round15` 的意义，不是继续找新结构，而是验证上面这个最小提交包能不能稳定复跑。

当时的本地运行产物未作为长期资产保留；核心指标和表达式结论已完整沉淀如下。

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

- `cashflow_submit_core preset` 已经可以视为后续 `fundamental6` 的最小复跑资产
- 当前阶段不应再对这些弱 refine 抱有“再跑一次也许会变强”的预期
- `fundamental6` 的重点已经从“继续扩模板”转成“围绕双主线做低频复核和提交运营”

### 2026-07-17 round16 低频复跑确认

`round16` 的意义，是在新一天重新跑一次同一个最小提交包，确认主干没有漂移。

当时的本地运行产物未作为长期资产保留；核心指标和复现结论已完整沉淀如下。

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
- `cashflow_submit_core preset` 已经具备“跨天低频复跑”的最小运营价值
- 当前 `fundamental6` 不应再继续扩这些已验证偏弱的 refine 邻居

### 2026-07-24 闭环验证流程修正

`2026-07-24` 的一次真实小批次运行，把一个容易被忽略的问题跑实了：

- `cashflow_submit_core preset` 文件里虽然只有 2 条主模板
- 但如果只是直接运行，而不设置 `--stop-after-submittable`
- 当前调度会继续扩到更多 settings 组合、邻居模板，甚至自动进入 refine 链

这意味着：

- “最小提交包”本身没问题
- 真正缺的不是模板，而是验证流程的停止边界

因此从这一天开始，`fundamental6` 的最小复跑应该固定理解为：

- 用 `cashflow_submit_core preset`
- 用单字段白名单 `presets/cashflow_submit_core/fields.txt`
- 用双模板白名单 `presets/cashflow_submit_core/templates.txt`
- 显式设置 `--stop-after-submittable 1`
- 默认关闭 blacklist 自动更新

如果目标不是健康检查，而是继续放大可提交结果，那才应该故意去掉这个停止条件。

### 2026-07-24 真实健康检查结果

在把现役字段白名单和模板白名单收正之后，同一天又做了一次真实验证：

- 执行方式：直接运行最小健康检查命令
- 运行产物不作为长期知识资产；本轮关键结果已记录在本节
- 本轮实际是“单枪健康检查”，不是“双模板全量展开”

本轮落地结果：

- `tested = 1`
- `submittable = 1`
- `errors = 0`
- `submitted = false`

命中的主线是：

- `group_rank(ts_delta(winsorize(ts_backfill(cashflow_op, 120), std=4) / cap, 63) / ts_std_dev(winsorize(ts_backfill(cashflow_op, 120), std=4) / cap, 126), subindustry)`

对应平台结果：

- `alpha_id = A17weAVw`
- `template = group_ratio_delta_over_std_63_126_over_cap`
- `checks passed`

这轮结果把当前闭环又确认了一次：

- 现役脚本已经不再从 `archive/` 漏回旧入口
- 最小复跑已经从“可能悄悄扩包”收成“命中即停”的健康检查
- `fundamental6` 当前最合理的节奏，仍然是低频复跑与提交运营，而不是恢复大范围扩模板

### 2026-07-24 rerun 双主线复现

在当天后续又做了一轮 `core pack` 真实复跑：

- 运行产物不作为长期知识资产；本轮关键结果已记录在本节
- 本轮目标：不是继续找新模板，而是确认现役双主线能否在同一天再次一起复现

核心结果：

- `tested = 2`
- `submittable = 2`
- `errors = 0`

两条正式主线都拿到了 `submittable=true`：

- `group_ratio_delta_over_std_63_126_over_cap`
  - `alpha_id = A17weAVw`
- `hc_ratio_group_zscore_252_over_cap`
  - `alpha_id = 3qe7krMQ`

这轮的重要意义是：

- `fundamental6` 当前两条正式主线，不只是历史上分别通过过
- 而是在 `2026-07-24` 同一天的现役 `core pack` 复跑里再次同时复现
- 因此当前完全可以把 `cashflow_submit_core preset` 视为稳定的双主线运营入口

### 2026-07-24 zscore-only pack 独立验证

除了双主线 `core pack` 复跑之外，当天还单独把 `grouped zscore over cap` 这条主线拆成一模板 pack 做了独立验证：

- 模板包：`datasets/fundamental6/presets/cashflow_submit_zscore_core/template.json`
- 运行产物不作为长期知识资产；本轮关键结果已记录在本节

核心结果：

- `tested = 1`
- `submittable = 1`
- `errors = 0`

对应结果：

- `template = hc_ratio_group_zscore_252_over_cap`
- `alpha_id = 3qe7krMQ`

这轮的额外价值不只是再次通过，而是顺手验证了一个流程修复：

- 当显式指定专项 preset 模板库时，执行器现在不会再偷偷混入自动生成的 `MATRIX` 模板
- 也不会再混入 `iter_*` 反馈变异模板
- 这意味着 `fundamental6` 的最小 `refine preset` 终于真正具备“闭集执行”语义
