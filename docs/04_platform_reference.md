# WorldQuant BRAIN 平台术语与状态 Reference

> 目标：把平台里最容易混淆的术语、状态、评分、OS 页面字段收口成一篇可快速查阅的文档。

---

## 1. 这篇文档适合什么时候看

当你遇到下面这些问题时，先来这里查：

- `IS` 和 `OS` 到底分别是什么？
- `Semi-OS` 放在时间轴的哪里？
- `OSTEST-PENDING`、`OSTEST-DECM` 是什么意思？
- 为什么 OS 页很多地方是 `N/A`？
- `Meta Score`、`Meta Alpha Count` 在看什么？
- `Universe`、`Weight`、`Booksize`、`NaN`、`Pasteurize` 到底怎么理解？

这篇文档不负责讲“怎么做 Alpha”，而是负责讲“平台这些词到底在说什么”。

---

## 2. 最核心的时间维度：IS 和 OS

### 2.1 IS

`IS` = `In-Sample`

官方语义：

- 这是 Alpha 首次模拟日期之前的历史回测表现
- 也就是你在 `Simulate` 结果页直接看到的表现

可以把它理解为：

- 历史样本内表现
- 本地研究阶段最先看到的结果

### 2.2 OS

`OS` = `Out-Sample`

官方语义：

- 这是 Alpha 提交之后的表现
- 更接近“真实世界”滚动产生的后续表现

可以把它理解为：

- 样本外表现
- 正式提交之后才开始逐步积累的数据

### 2.3 `Semi-OS`

官方 Glossary 里把它单独列成了一个术语：

- `Semi-OS` 指的是 `IS` 结束之后
- 到你真正提交这条 Alpha 之前
- 中间这一段时间

它很容易被忽略，因为很多人脑中只有：

- 回测阶段
- 提交以后

但平台其实把中间这段也单独命名了。更实用的理解是：

- `IS`：你现在在本地最容易看到的历史成绩
- `Semi-OS`：还没正式进入 OS 前的一段过渡区间
- `OS`：真正提交之后逐步滚动积累的样本外成绩

### 2.4 一个很重要的点

官方明确说明：

- `IS` 和 `OS` 使用的是同一套 neutralization 设置

所以不要把 OS 表现变化简单理解成“平台换了 neutralization”。

### 2.5 `Test Period`

官方 Learn 文档对 `Test Period` 的定义很明确：

- 它是在 5 年 IS 内再切出一段 `Train/Test`
- Train 更适合开发 Alpha
- Test 更适合验证是否过拟合

最容易记错的一点是：

- `Test Period` 会影响统计和图表展示
- 但 submission tests 仍然跑完整 5 年 IS

页面操作上还要注意：

- Stats Summary 默认显示 Train 段，可通过 `TEST / IS` 切换查看 Test 段或完整 IS
- 图表中的 Test 段以单独颜色标识，隐藏或显示只改变页面展示
- 如果设置了 Test Period，官方页面说明提交前必须先通过 `Show test period` 显示该区段

所以它更像：

- 一个研究验证工具

而不是：

- 一个改变平台正式提交口径的开关

---

## 3. 最常见状态词典

### 3.1 `IS-FAIL`

官方语义：

- Alpha 没有通过基础 IS 门槛
- 通常是 Sharpe 等基础质量线没过
- 不会进入 OS 测试阶段

### 3.2 `OSTEST-PENDING`

官方语义：

- Alpha 已进入 OS 测试
- 但部分 OS 测试或统计还未完成

这通常不代表异常，而代表：

- 还在等待更多数据
- 还在等部分测试完成

### 3.3 `OSTEST-PASS`

官方语义：

- OS 测试通过

### 3.4 `OSTEST-FAIL`

官方语义：

- OS 测试失败

### 3.5 `OSTEST-DECM`

官方语义：

- 官方说明这是已失败、后续不再继续测试的状态
- 这种 Alpha 不再获得评分

这类状态对本地研究的启发是：

- 它不是“再等等可能会转好”
- 更应该把它视为阶段性终止信号

### 3.6 一条更完整的生命周期

如果把上面的术语串起来，平台的一条 Alpha 更像是在经过：

1. `Simulate`：先看 5 年 `IS`
2. `Check submission`：先过基础门槛和检查项
3. `Submit`：真正送入平台后续流程
4. `Semi-OS`：提交前的过渡区间
5. `OS`：提交后的真实滚动表现

这也是为什么：

- 本地 `submittable=true` 只是“有资格继续”
- 本地 runner 当前默认不会自动执行正式 `submit`
- 它不等于“这条 Alpha 已经长期成立”
- 它也不等于“这条 Alpha 已经进入平台 `ACTIVE` 生命周期”

### 3.7 `UNSUBMITTED`、`ACTIVE`、`DECOMMISSIONED`

- `UNSUBMITTED`：仍在研究区，尚未正式提交；模拟通过也仍属于这一状态
- `ACTIVE`：已提交并处于有效生命周期内；对 Consultant 而言，ACTIVE Alpha 才可能继续累积权重
- `DECOMMISSIONED`：已退出有效生产生命周期，常见原因包括数据集不再可用、长期 OS 表现不佳，或平台基于整体管理做出的调整

因此不要把“曾经提交成功”理解成永久有效。提交后的 OS 稳定性、数据可用性和池子价值仍会影响 Alpha 的后续状态。

---

## 4. 为什么 OS 页面会出现 `N/A`

官方解释非常明确：

- OS 页面并不会在第一次 OS 仿真后立刻拥有所有统计值
- 很多字段要等足够多的新交易日积累后才会显示

例如官方给出的例子：

- `Sharpe125` 需要等 125 个交易日过去后才会出现

所以：

- `N/A` 不一定表示坏掉
- 很多时候只是“样本还不够长”

---

## 5. OS 测试到底在看什么

官方明确提到几类关键 OS 测试：

### 5.1 `SelfCorr`

- 看你当前 Alpha 和你自己其他 OS Alpha 的相关性
- 如果一组 Alpha 太像，通常只有其中一部分能通过

### 5.2 `ISSharpe / OSSharpe Ladder`

- 用来判断 Alpha 的表现是否显著
- 本质上是在过滤“随机噪声看起来像信号”的假阳性

对本地研究最重要的启发：

- 不是“回测不错”就一定算通过
- 平台会进一步判断这个结果是不是足够显著、足够独特

### 5.3 `PROD_CORRELATION`

它衡量候选和平台已有生产 Alpha 的相似程度；完整定义和 submission check 语义见
[提交检查词典](#137-prod_correlation)。

---

## 6. 评分与池子视角

### 6.1 `Meta Score`

官方语义：

- 它不是看单条 Alpha
- 它看的是你整个 Alpha 池子的组合质量

官方特别提到会关注：

- 组合 Sharpe
- 平均 Turnover
- 相关性

### 6.2 `Meta Alpha Count`

官方语义：

- 指进入 meta 评分计算的 Alpha 数量

这提醒我们：

- 不是“提交越多越好”
- 高相关、同质化、噪声型提交未必能增加组合价值

### 6.3 `IQC score` / leaderboard 分数

官方 FAQ 的竞赛口径大意是：

- leaderboard 上先展示基于 IS 结果的分数
- 阶段结束后会继续结合 OS 结果

这些分数不等同于普通 Alpha submission 的质量判断，也不应反向改变 runner 的默认筛选逻辑。
报名、组队、赛季、资格、证书和付款等动态规则统一见
[05 平台运营 Reference](05_platform_operations_reference.md)。

### 6.4 D1 / D0 Fitness 评级

官网给出的显示档位并不相同：

| 评级 | D1 Fitness | D0 Fitness |
|---|---:|---:|
| Average | `> 1.0` | `> 1.3` |
| Good | `> 1.5` | `> 1.95` |
| Excellent | `> 2.0` | `> 2.6` |
| Spectacular | `> 2.5` | `> 3.25` |

D0 的门槛更高，因此不能只看绝对 Fitness 数字就断言 D0 优于 D1；还要结合 Delay 匹配、换手和交易成本压力判断。

---

## 7. Universe、Weight、Booksize

### 7.1 `Universe`

官方定义：

- Universe 是市场里最具流动性的一篮子股票

例如：

- `TOP500`
- `TOP1000`
- `TOP2000`
- `TOP3000`

它们是按流动性分层的集合关系，不只是股票数量不同。

### 7.2 `Weight`

官方解释：

- 表达式先为每只股票产生 Alpha value
- 再应用 neutralization、decay 等设置
- 再按 `booksize` 缩放成最终资金配置

所以 `weight` 不是原始字段值，也不是表达式文本本身，而是平台处理后的组合分配结果。

### 7.3 `Booksize`

官方 Glossary 的口径更具体：

- 平台使用固定 `booksize = $20 million`
- 模拟利润不会做再投资
- 模拟亏损会被现金注入补回

所以平台上的很多结果都带着这层统一约束：

- 资金底座固定
- 收益不会因为“赚了钱再滚大本金”而膨胀
- 亏损也不会因为“本金越亏越小”而自动收缩

对实战最重要的意义是：

- 很多收益率、回撤、资金分配口径，都不是你自己随便定义的
- 它们是平台统一口径的一部分

---

## 8. `NaN`、`0`、`INF`、`Pasteurize`

### 8.1 `NaN`

官方定义：

- `NaN` = `Not a Number`
- 常见于无效计算、坏数据、缺失数据、不可用数据

对持仓语义最重要的一点：

- `Alpha = NaN` 表示该股票不持仓

### 8.2 `0`

官方明确提醒：

- `0` 不等于 `NaN`
- 因为 `0` 经过 decay、neutralization 等处理后仍可能变成非 0

所以：

- `NaN` 是“没有仓位”
- `0` 更像是“当前原始值为 0，但后续可能变化”

### 8.3 `INF`

常见于：

- 除零
- 极端值爆炸

### 8.4 `Pasteurize`

官方给出的关键作用有两个：

1. 把 `INF` 替换成 `NaN`
2. 把当前 Universe 外的 instrument 设成 `NaN`

因此它的作用不止是异常值清理，还涉及：

- Universe 边界控制
- group operator 输入集合控制

这也是为什么它经常和下面这些东西一起被讨论：

- cross operations
- group operators
- coverage 变化

因为它不只是“把坏值洗掉”，还会改变后续有哪些 instrument 继续参与计算。

---

### 8.5 `truncate(...)`、`truncation`、`group_neutralize(...)`、`neutralization`

这几组词在平台里非常容易混。

先记最重要的边界：

- `truncate(...)`
  - 表达式算子
  - 更像信号内部裁极值
- `truncation`
  - 平台设置
  - 更像最终组合权重上限
- `group_neutralize(...)`
  - 表达式算子
  - 更像组内相对化
- `neutralization`
  - 平台设置
  - 更像组合层中性化

这层边界很重要，因为它决定了：

- 你是在改“信号长什么样”
- 还是在改“平台怎样把信号变成最终组合”

### 8.6 `NaNHandling`

- `OFF`：保留算子自然产生的缺失语义
- `ON`：平台会对部分缺失情形做自动处理；例如全为 NaN 的时间序列窗口可能得到 `0`，部分 group operator 也可能返回组内值

它可能提高覆盖率，但也可能把“真实零值”和“缺失后补出的零值”混在一起。它不是手写 `is_nan(...)` 的替代品，也不同于某些算子的 `filter=true` 参数。

### 8.7 `Unit Handling`

平台会检查表达式里的单位是否合理，例如“金额 + 比率”可能产生单位警告。单位警告用于帮助发现表达式语义错误，但官方说明它本身不会阻止提交。

研究时仍应优先修正不合理单位，因为“能提交”不等于“经济含义成立”。

---

## 9. 交易成本、Turnover、Margin

### 9.1 `Transaction Cost`

官方语义：

- 这是交易需要支付的成本
- 与 Turnover 强相关

### 9.2 一个很容易误解的点

官方明确说明：

- 模拟结果本身 **不直接包含** 交易成本

所以如果你看到高 Returns，不要默认理解成：

- “已经扣完真实交易成本后还这么高”

### 9.3 `Turnover`

对平台而言：

- 它是交易频率和交易成本压力的重要 proxy

### 9.4 `Margin`

官方定义为：

```text
Margin = PnL / total dollars traded
```

可以把它理解成每交易一美元能赚多少钱。官方建议优先提高 Returns，同时管理 Turnover；它没有把某个 Margin 数字写成所有设置通用的硬门槛。

所以：

- 高 Turnover 不一定坏
- 但高 Turnover 如果没有足够高的信号质量和 margin 支撑，就会很脆弱

---

## 10. 字段类型词典

字段右侧的 `type` 描述数据形态，不是质量评级。具体怎样分流研究和模板，见
[02 的 MATRIX、VECTOR、GROUP 研究分工](02_research_and_data_guide.md)。

### 10.1 `MATRIX`

每个 `date × instrument` 通常只有一个值，是最常见的标量字段形态，例如
`assets`、`debt` 和 `cashflow_op`。

这类字段可以直接进入普通截面和时间序列算子，例如 `rank()`、`ts_rank()`、
`ts_zscore()` 和 `group_rank()`。

### 10.2 `VECTOR`

每个 `date × instrument` 可以包含数量不固定的一组值，常见于事件或明细集合。
它不能直接当作单值标量使用，通常要先经过 `vec_*` 聚合算子，例如：

- `vec_count()`
- `vec_avg()`
- `vec_max()`
- `vec_stddev()`
- `vec_skewness()`

聚合后得到 MATRIX 形态的单值，才能继续进入普通时序或截面算子。

上面是 Learn 的 Vector Data Fields 教程用于说明聚合语义的例子，不等于当前账号一定能在
Operators 页面看到全部算子。`2026-08-03` 当前账号的 Operators API 快照只返回
`vec_avg()` 和 `vec_sum()` 两个 Vector 算子。使用其他 `vec_*` 前应先查询当前 Operators
页面/API；runner 和模板资产只能自动生成已经在账号可见快照或实际模拟中验证过的算子。

### 10.3 `GROUP`

GROUP 字段表示 instrument 所属的类别或分组，例如 `sector`、`industry`、
`subindustry` 和 `exchange`。它通常作为 group operator 的分组输入，而不是方向信号：

- `group_rank(x, group)`
- `group_zscore(x, group)`
- `group_neutralize(x, group)`
- `group_backfill(x, group, d)`

### 10.4 `SET`

SET 是集合型非标量字段。具体可用算子取决于平台当前字段和 operator 签名；不要在没有
聚合或转换的情况下把它当作 MATRIX 使用。精确签名应查 Operators 页面或本地官方快照。

### 10.5 `bucket()` 与 `densify()`

除了使用已有 GROUP 字段，还可以从普通数值动态创建分组：

```text
asset_group = bucket(rank(assets), range="0.1, 1, 0.1");
group_zscore(alpha, densify(asset_group))
```

- `bucket()` 按数值区间生成组。
- `densify()` 去掉空组并压紧组编号。
- group operator 只在同组 instrument 之间计算。

分组过细会让每组样本过少；Universe 越小，越应控制 bucket 数量。

---

## 11. Operators 官方快照

Operators 的精确定义、参数和分类以平台当前可见页面/API 为准。本地最新目录保留了一份
`2026-08-03` 捕获的账号可见快照，作为离线查表入口：

- 本地索引：[source_snapshots/worldquant_operators_2026-08-06/README.md](source_snapshots/worldquant_operators_2026-08-06/README.md)
- 官方 API：`https://api.worldquantbrain.com/operators`
- 数据捕获日期：`2026-08-03`；目录日期：`2026-08-06`（当天 API 返回 `401`，使用历史数据回退）

使用时要注意两个边界：

- 这是一份带日期的账号可见快照，不表示所有账号、所有等级、所有时间都看到相同算子。
- Learn Documentation 与 Operators API 是两个官方来源；教程可能介绍当前账号 API 没有返回的
  算子，实际可执行性以当前账号的 Operators 页面/API 和模拟结果为准。
- 分类数量、逐个算子的签名、说明和例子只在快照索引维护，主文档不再复制。

---

## 12. Coverage、Alpha list、Correlation 工具

本节只解释页面指标和工具。字段筛选顺序、体检方法和仓库策略见
[02 数据研究与仓库实践](02_research_and_data_guide.md)。

### 12.1 `Coverage` 与 `dateCoverage`

`Coverage` 表示当前 Universe 中，某个 data field 有定义值的 instrument 占比；
它更接近横截面覆盖率。

`dateCoverage` 表示字段在历史时间轴上的可用跨度。例如：

- `coverage = 0.5`：某个时点平均约一半 instrument 有值。
- `dateCoverage = 1.0`：字段在整个历史区间基本持续存在。

两者不矛盾：字段可以覆盖完整历史年份，但每天只覆盖部分股票。

### 12.2 `Alpha list`

Alpha list 用于比较多条 Alpha 的表现和彼此相关性。它展示汇总指标，不提供完整 Alpha
output vector 或每只股票的逐日权重明细。

### 12.3 `alphaCount` 与 `userCount`

- `alphaCount`：使用过该字段的 Alpha 数量。
- `userCount`：使用过该字段的用户数量。

它们描述字段使用度和拥挤程度，不直接表示字段质量。较低数值只说明使用较少，不保证信号更强。

### 12.4 `Dataset Value Score`

Dataset Value Score 描述数据集“未被充分使用”的程度，目前主要面向 Consultant。
它不是传统 Value Factor，也不是数据质量分数；动态口径以平台当前页面为准。

### 12.5 `Dataset Usage Management`

Dataset Usage Management 是平台对特定 dataset category 的访问和使用阈值管理。
它与 coverage、更新频率等字段质量指标不是同一概念；访问受限也不等于字段本身失效。

### 12.6 `Correlation`

Correlation 用于衡量 Alpha 的独特性：

- `SELF_CORRELATION` 比较用户自己的 Alpha。
- `PROD_CORRELATION` 比较平台已有生产 Alpha。

具体 submission check 语义见下一章；降低相关性的研究动作见
[03 优化与提交](03_optimization_and_submission.md)。

### 12.7 Alpha 页面操作

Alpha 页面支持筛选、排序、增删列和重命名。隐藏的 Alpha 可通过 `Hidden` filter 找回；
当前没有删除 Alpha 的功能，未重命名时可能显示为 `anonymous`。

官方来源：[How to view your Alphas](https://support.worldquantbrain.com/hc/en-us/articles/24439802248471-How-to-view-your-Alphas)；
[How do I delete my Alphas?](https://support.worldquantbrain.com/hc/en-us/articles/5971823272215-How-do-I-delete-my-Alphas)；
[Can I give meaningful names to my Alphas?](https://support.worldquantbrain.com/hc/en-us/articles/5969975774103-Can-I-give-meaningful-names-to-my-Alphas)；
[Can I see the Alpha output vector?](https://support.worldquantbrain.com/hc/en-us/articles/5969712153239-Can-I-see-the-Alpha-output-vector)

### 12.8 Simulation 的频率与取消

BRAIN Alpha 按日模拟和再平衡，不模拟高频或日内交易。正在运行的 simulation 可以使用
`Cancel simulation` 中止。

官方来源：[Does BRAIN platform simulate high frequency trade and intraday trade?](https://support.worldquantbrain.com/hc/en-us/articles/5971017679639-Does-BRAIN-platform-simulate-high-frequency-trade-and-intraday-trade)；
[Is it possible to abort a running simulation?](https://support.worldquantbrain.com/hc/en-us/articles/5971303624471-Is-it-possible-to-abort-a-running-simulation)

---

## 13. 提交检查词典

本节只记录页面语义、公式和带日期的常见门槛。诊断顺序和改进动作统一见
[03 优化与提交](03_optimization_and_submission.md)。

### 常见硬门槛快照（2026-07-31）

| 检查 | 当前常见口径 |
|---|---|
| D1 Fitness | 严格 `> 1` |
| D1 Sharpe | 严格 `> 1.25` |
| Turnover | 严格 `> 1%` 且 `< 70%` |
| 单只股票最大权重 | `< 10%`，并满足有效权重覆盖要求 |
| Self-Correlation | 通常要求 `< 0.7`；超出时存在表现改善例外判断 |
| Sub-Universe Sharpe | 按子 Universe 与原 Universe 的相对大小缩放 |

页面值可能经过四舍五入，显示为 `1.00` 或 `1.25` 不代表底层值已经严格越过门槛。
检查也可能随 Delay、Region、Universe、Alpha 类型和平台版本变化，因此这张表不能当作
永久全球规则。

### 13.1 `LOW_SHARPE`

表示风险调整后收益未达到当前 Alpha 类型对应的 Sharpe 门槛。

### 13.2 `LOW_FITNESS`

表示 Fitness 未达到门槛。官方公式为：

```text
Fitness = Sharpe * sqrt(abs(Returns) / max(Turnover, 0.125))
```

因此它由 Sharpe、Returns 和 Turnover 共同决定，不是独立统计量。

### 13.3 `HIGH_TURNOVER`

表示 Turnover 超过当前检查上限。Turnover 描述组合在相邻日期之间的持仓变化程度；
它是交易成本压力的 proxy，但模拟收益本身不直接扣除真实交易成本。

### 13.4 `CONCENTRATED_WEIGHT` 与 `WEIGHT_COVERAGE`

前者表示单只或少数股票的权重过于集中；后者表示有效权重没有稳定覆盖足够多的
Universe 成分。两者都属于组合权重分布检查。

### 13.5 `LOW_SUB_UNIVERSE_SHARPE`

表示 Alpha 在更小、更液态的子 Universe 中不够稳。官网给出的检查线为：

```text
subuniverse_sharpe
>= 0.75 * sqrt(subuniverse_size / alpha_universe_size) * alpha_sharpe
```

阈值随子 Universe 相对大小变化，不是统一固定数值。

### 13.6 `SELF_CORRELATION`

表示新 Alpha 与用户自己的已有 Alpha 过于相似。常见语义是：最大自相关高于 `0.7`
时，如果新 Alpha 的表现没有比相关 Alpha 至少改善约 `10%`，检查可能失败。

官方来源：[Self-correlation error message](https://support.worldquantbrain.com/hc/en-us/articles/6726867827991)
（复核 2026-07-31）。

### 13.7 `PROD_CORRELATION`

表示 Alpha 与平台已有生产 Alpha 的相关性过高，用于衡量候选是否具有足够增量价值。

### 13.8 最不流动 50% 的 after-cost Sharpe

平台会检查原 Universe 中最不流动的 50% 股票在计入交易成本后的 Sharpe。官网示例要求
该部分达到原 Universe after-cost Sharpe 的约 `52.5%`（复核 2026-07-31）。

### 13.9 `Alpha better suited for Delay 1`

该 D0 提示表示同一 Alpha 在 D1 的 Sharpe 更高。官方来源：
[Alpha better suited for Delay 1](https://support.worldquantbrain.com/hc/en-us/articles/19083452017559)
（复核 2026-07-31）。

### 13.10 `Max Trade`

`Max Trade` 是模拟设置中的单票交易约束开关，不是文档已确认的固定 submission
threshold。本仓库默认保持 `OFF`，需要时显式开启。

### 13.11 特殊 Alpha 类型

官方 Learn 的 Alpha Submission 页面还定义了几类特殊 Alpha。它们会改变适用检查或
候选归类，不能只套用普通 Alpha 的门槛表。

| 类型 | 官方定义与额外规则 |
|---|---|
| `ATOM` | 只使用 `1` 个 dataset 的字段；`currency`、`country`、`exchange`、`sector`、`industry`、`subindustry`、`market` 等 grouping 字段不计入 dataset 数量。`inst_pnl(...)` 会按使用 `pv1` 计算。ATOM 可以跳过 IS Ladder Sharpe，但仍须通过普通 IS tests 和 2Y Sharpe test。 |
| `Pyramid` | Pyramid 由 `Region + Delay + dataset category` 组合定义；一个候选最多贡献到 `2` 个 pyramids。上述 grouping 字段不计入 pyramid 数量。 |
| `Power Pool` | 官方页面列出的口径包括：USA D1、Sharpe `>= 1.0`、唯一 operator 数 `<= 8`、非 grouping data field 数 `<= 3`、Power Pool 内 Self-Correlation `<= 0.5`、Turnover 在 `1%-70%` 之间。标记过 Power Pool 的 Alpha 即使之后取消标签，仍会留在对应 self-correlation pool。 |

这些类型、标签入口和门槛可能受账号等级与平台版本影响。上表来自 `2026-08-06`
Documentation 快照；实际判断以当前 Alpha 页面和 Check Submission 返回为准。

### 13.12 GLB Sub-Geography Sharpe

GLB Alpha 还会检查三个地区的 Sharpe。`2026-08-06` 官方页面给出的口径是：

| 地区 | Sharpe cutoff |
|---|---:|
| `AMER` | `>= 1` |
| `APAC` | `>= 1` |
| `EMEA` | `>= 1` |

这项检查用于避免全球 Alpha 的 PnL 过度依赖单一地区。诊断时应分别查看地区 PnL、
流动性、行业暴露和 Coverage，而不是只提高 GLB 汇总 Sharpe。

### 13.13 ASI Japan Robustness Sharpe

ASI Alpha 还可能接受 Japan Robustness Sharpe 检查。`2026-08-06` 官方页面给出的 cutoff
是 `>= 1`。需要特别注意：

- 该检查使用的 Japan universe 与 Visualization Tool 展示的 Japan universe 不同。
- Visualization Tool 仍适合检查 Japan PnL、Turnover、Coverage、行业和市值暴露，但其中的
  Japan Sharpe 不保证与 submission test 数值完全一致。
- 改进时优先检查流动性、行业暴露、单票集中度和 Turnover，不应只做地区专属参数拟合。

### 13.14 Check Submission 消息顺序

官方 Learn 页面说明，Check Submission 或 Submit Alpha 会按顺序执行检查，遇到失败时显示
对应消息。`2026-08-06` 页面列出的顺序是：

1. Weight test
2. Correlation test
3. Fitness test
4. D0 `checkDelay1Sharpe`
5. Sub-Universe test

因此页面只显示某个失败项，不代表排在它后面的检查已经通过。平台可能调整检查集合与顺序，
本地分析应保存实际 Check Submission 返回，不能根据这张顺序表推断未显示项的终态。

官方来源：[Clear these tests before submitting an Alpha](https://platform.worldquantbrain.com/learn/documentation/interpret-results/alpha-submission)
（本地 Documentation 快照：`2026-08-06`）。

---

## 14. PnL、Drawdown、平滑

### 14.1 `PnL`

你看到的 PnL 是组合层面的表现，不是单只股票单独收益图。

### 14.2 `Drawdown`

就是组合从峰值往下回撤的幅度。

### 14.3 PnL 为什么会突然跳

PnL 跳变属于表达式和持仓结构诊断问题，具体原因与改进动作统一见
[03 的 PnL 跳变章节](03_optimization_and_submission.md#18-pnl-曲线突然跳变时先查什么)。

---

## 15. `Neutralization` 的页面语义

平台语义里：

- 先有表达式原始值
- 如果指定了 neutralization，平台不会直接拿原始值当最终持仓
- 而是先做中性化，再进入后续处理

所以 neutralization 在平台中是“组合层面的结构变换”，不是简单注释项。

不同数据类别怎样选择 neutralization，以及应该放在 settings 还是表达式中，见
[03 的最终决策章节](03_optimization_and_submission.md#221-neutralization-的最终决策)。

---

## 16. 最常见的误读速查

| 常见误读 | 正确理解 |
|---|---|
| `N/A` 就是异常 | OS 样本未积累完成时也可能显示 `N/A` |
| `0` 表示不持仓 | `NaN` 才更接近不持仓；`0` 仍是有效信号值 |
| 模拟结果已扣除真实交易成本 | 模拟不直接包含交易成本，Turnover 只是 proxy |
| 提交更多同类 Alpha 一定更好 | Meta Score 同时关注相关性和候选池质量 |
| OS 只是 IS 的重复显示 | OS 是提交后逐步积累的样本外表现 |

---

## 17. 官方来源

本篇主要整理自这些官方 FAQ：

- [What do in sample and out sample mean?](https://api.worldquantbrain.com/faqs/in-sample-out-sample-alphas)
- [Why do my Alphas in out sample show NA?](https://api.worldquantbrain.com/faqs/out-sample-testing)
- [Can you please throw some light on the OS-Tests being performed on the Alphas?](https://api.worldquantbrain.com/faqs/status)
- [Could you please throw some light on meta score and meta alpha count?](https://api.worldquantbrain.com/faqs/meta-score-count)
- [What is transaction cost? And is it important?](https://api.worldquantbrain.com/faqs/transaction-cost)
- [Does the simulation include trading costs?](https://api.worldquantbrain.com/faqs/trading-costs)
- [How to improve margins in simulation results](https://support.worldquantbrain.com/hc/en-us/articles/20311116434839-How-to-improve-margins-in-simulation-results)
- [Is it necessary to have turnover below 40% for the Alpha to be evaluated?](https://support.worldquantbrain.com/hc/en-us/articles/5969425740823-Is-it-necessary-to-have-turnover-40-for-the-Alpha-to-be-evaluated)
- [Can you please explain Universes top 2000, top 500, etc.?](https://api.worldquantbrain.com/faqs/universe-explanation)
- [Even after searching a lot, I am unable to find out more information about stock weights](https://api.worldquantbrain.com/faqs/info-about-stock-weight)
- [What does NaN mean? Is it equal to zero?](https://api.worldquantbrain.com/faqs/nan-zero)
- [Can you please explain the actual effect of Pasteurize(x)?](https://api.worldquantbrain.com/faqs/pasteurize)
- [I want to smooth the PnL curve](https://api.worldquantbrain.com/faqs/smooth-pnl-curve)
- [What is ISladder test and how is it constructed?](https://api.worldquantbrain.com/faqs/isladder-test)
- [What is the IQC scoring metrics?](https://api.worldquantbrain.com/faqs/iqc-scoring-metrics)
- [After I submit an alpha, how much time does it take for it to be reflected as the score on leaderboard?](https://api.worldquantbrain.com/faqs/score-update-frequency)
- [Understanding Data in BRAIN: Key Concepts and Tips](https://platform.worldquantbrain.com/learn/documentation/understanding-data/data)
- [Group Data Fields](https://platform.worldquantbrain.com/learn/documentation/understanding-data/group-data-fields)
- [Operators API](https://api.worldquantbrain.com/operators)
- [D0](https://platform.worldquantbrain.com/learn/documentation/advanced-topics/getting-started-d0)
- [Simulation Settings](https://platform.worldquantbrain.com/learn/documentation/create-alphas/simulation-settings)
- [Dataset Usage Management](https://support.worldquantbrain.com/hc/en-us/articles/22696472589079-What-s-Dataset-Usage-Management)
- [Self-Correlation](https://support.worldquantbrain.com/hc/en-us/articles/19083458643863-Error-Message-Alpha-is-too-correlated-with-your-other-Alphas)
- [Sub-Universe Sharpe](https://support.worldquantbrain.com/hc/en-us/articles/19083526884759-Error-Message-Sub-universe-Sharpe-is-below-cutoff)
- [Most illiquid 50% instruments after-cost test](https://support.worldquantbrain.com/hc/en-us/articles/19083525654551-Error-message-Most-illiquid-50-instruments-after-cost-Sharpe-is-above-cutoff-of-original-universe)
- [Alpha better suited for Delay 1](https://support.worldquantbrain.com/hc/en-us/articles/19083452017559-Error-Message-Alpha-better-suited-for-Delay-1)
