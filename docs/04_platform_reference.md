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

官方 Glossary 的定义很直接：

- 它衡量的是当前 Alpha
- 和平台所有顾问已提交 Alpha 之间的最大相关性

可以把它和 `SelfCorr` 对照着记：

- `SelfCorr` 更像“和你自己已有池子太像”
- `PROD_CORRELATION` 更像“和平台已有池子太像”

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

如果你的本地文档未来继续服务竞赛使用，这一块值得单独维护，但和普通 Alpha 研究文档要保持边界。

### 6.3.1 `Challenge-Country Leaderboard`

Challenge-Country Leaderboard 更像地区维度的挑战排名入口。它会受挑战积分、活动和
平台定义的排名规则影响，不等同于普通 Alpha submission 的质量判断。

对本仓库而言：

- 它可以说明用户为什么关注某些比赛分数
- 但不应该反向改变 alpha runner 的默认筛选逻辑
- 研究质量仍以 Sharpe、Fitness、Turnover、相关性、稳健性和提交检查为主

### 6.3.2 IQC 信息的文档边界

IQC FAQ 覆盖报名、组队、阶段分数、leaderboard 更新、顾问权益和付款时间等大量动态信息。
这些内容容易随赛季变化，本仓库只保留与研究状态有关的稳定语义：

- Stage 1 通常更偏 IS/leaderboard 计分展示
- 后续阶段和最终评价会继续关注 OS 和提交结果
- 团队、付款、资格和证书等规则不进入研究方法文档

如果后续要做竞赛专用自动化，应另行维护赛季配置，而不是把动态规则写死进模板。

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

## 11. Operators 官方快照与分类

Operators 的精确定义、参数和分类以平台当前可见页面/API 为准。本地保存了一份 `2026-08-03`
账号可见快照，作为离线查表入口：

- 本地索引：[source_snapshots/worldquant_operators_2026-08-03/README.md](source_snapshots/worldquant_operators_2026-08-03/README.md)
- 官方 API：`https://api.worldquantbrain.com/operators`
- 捕获日期：`2026-08-03`
- 官网复核：`2026-08-04`，算子数量、签名和说明未变化；见 [增量记录](source_snapshots/worldquant_review_2026-08-04/README.md)

当前快照包含 `66` 个 `base` 算子，分布如下：

| 分类 | 数量 | 本地明细 |
|---|---:|---|
| Arithmetic | 15 | [arithmetic.md](source_snapshots/worldquant_operators_2026-08-03/arithmetic.md) |
| Cross Sectional | 6 | [cross-sectional.md](source_snapshots/worldquant_operators_2026-08-03/cross-sectional.md) |
| Group | 6 | [group.md](source_snapshots/worldquant_operators_2026-08-03/group.md) |
| Logical | 11 | [logical.md](source_snapshots/worldquant_operators_2026-08-03/logical.md) |
| Time Series | 24 | [time-series.md](source_snapshots/worldquant_operators_2026-08-03/time-series.md) |
| Transformational | 2 | [transformational.md](source_snapshots/worldquant_operators_2026-08-03/transformational.md) |
| Vector | 2 | [vector.md](source_snapshots/worldquant_operators_2026-08-03/vector.md) |

使用时要注意两个边界：

- 这是一份带日期的账号可见快照，不表示所有账号、所有等级、所有时间都只有这些算子。
- 主文档只总结分类和研究用途；逐个算子的签名、说明和例子在快照文件里查，避免把 reference 变成重复镜像。

---

## 12. Coverage、Alpha list、Correlation 工具

### 12.1 `Coverage`

官方 Glossary 的定义是：

- `Coverage` 指在当前 Universe 里
- 某个 data field 有定义值的 instrument 占比

这对研究的直接意义是：

- coverage 低，不代表字段一定不能用
- 但通常需要配合 `ts_backfill`、`kth_element`、`group_backfill` 之类方法处理缺失

所以在本仓库里看到 `coverage / dateCoverage` 过滤时，可以把它理解成：

- 先验质量信号
- 不是绝对真理

一个非常实用的联合理解是：

- `coverage = 0.5`
  - 更接近“横截面覆盖率”
  - 代表在当前 Universe 里，平均只有大约一半股票在某个时点上有这个字段值
- `dateCoverage = 1.0`
  - 更接近“时间跨度覆盖率”
  - 代表这条字段在整个历史时间轴上基本一直存在，不是某几年整段缺失

所以如果你同时看到：

- `coverage = 0.5`
- `dateCoverage = 1.0`

不要把它理解成矛盾，而应该理解成：

- 历史跨度是完整的
- 但单日横截面覆盖并不满

对实战最重要的启示是：

- 这类字段往往不是“没有历史”，而是“每天只有部分股票有值”
- 更需要：
  - `ts_backfill`
  - 必要时的 group/backfill 思路
  - 更稳的平滑和预处理
- 不太适合直接套短窗、高敏感、依赖满覆盖的模板

换句话说：

- `dateCoverage` 更回答“这条字段历史上在不在”
- `coverage` 更回答“这条字段每天覆盖了多少股票”

### 12.2 `Alpha list`

官方 Glossary 里把 `Alpha list` 定义成：

- 用来比较多条 Alpha
- 以及查看它们彼此相关性的工具

对本地工作流最有用的启发是：

- 不要只盯单条 Alpha
- 也要看一组 Alpha 是否只是高相关的小变体

### 12.2.1 `alphaCount` / `userCount` 怎么看

这两个指标更适合被理解成：

- `alphaCount`
  - 有多少条 Alpha 用过这个字段
- `userCount`
  - 有多少个用户用过这个字段

所以它们本质上在描述：

- 这个字段拥不拥挤
- 常不常见
- 是否容易撞到大众表达式

实战里可以先这样读：

- 高 `alphaCount` / 高 `userCount`
  - 不是不能用
  - 但通常不能“普通地用”
  - 更适合做字段关系、grouped structure、特殊预处理、或跨字段组合
- 低 `alphaCount` / 低 `userCount`
  - 不代表一定更强
  - 只代表它没那么拥挤，更可能带来独特性

比如在 `fundamental6` 上：

- 很多经典 `MATRIX` 字段很拥挤
  - 例如 `assets`、`debt`、`capex`、`cashflow_op`
- 而 `VECTOR/event` 分支整体更不拥挤

所以更好的默认研究动作通常是：

- 对拥挤的经典字段，少做最直白的单字段模板堆叠
- 对相对不拥挤的分支，优先考虑专项模板和结构差异

### 12.2.2 放到 `fundamental6` 上该怎么整体理解

> 以 fundamental6 为例的详细分析已移至
> [datasets/fundamental6/README.md](../datasets/fundamental6/README.md)。

### 12.2.3 `Dataset Value Score`

官网把 Dataset Value Score 定义为数据集“未被充分使用”的程度，该指标目前主要
面向 Consultant。它不是传统意义上的 Value Factor，也不等于数据质量分数。

更合适的理解是：

- 分数较高：平台更鼓励探索，通常代表相对没被充分利用
- 分数较低：不代表数据差，但可能已经更拥挤

因此筛选数据集时应把它和 `coverage / alphaCount / userCount` 一起看，不能只按
Value Score 排序就直接投入大量仿真预算。

### 12.2.4 `Dataset Usage Management`

Dataset Usage Management 是平台对某些 dataset category 使用权限和使用阈值的管理机制。
它和字段本身的统计质量不是同一个概念。

实战上要分清：

- 字段质量差：coverage、dateCoverage、分布、更新频率或历史结果不好
- 数据集受管理：平台权限或阈值限制导致某类 dataset 暂时不能继续正常使用

所以在本仓库里不应把“访问受限”自动写成字段 blacklist。更稳妥的处理是：

- 保留历史结果
- 在数据集 README 或运行总结中记录访问状态
- 给同类 idea 寻找替代 dataset category
- 等平台访问恢复后再重新验证

### 12.3 `Correlation`

官方 Glossary 直接把 Correlation 解释成：

- 衡量 Alpha 独特性的指标

这和本地研究流程是直接对应的：

- `SELF_CORRELATION` 更像“和自己池子太像”
- `PROD_CORRELATION` 更像“和平台已有池子太像”

所以相关性问题本质上不是“结果页面的小红字”，而是平台在判断：

- 这条 Alpha 有没有增量价值

### 12.4 Alpha 页面与 Alpha List 操作

官网 Alpha 页面支持筛选、排序以及增删列；隐藏的 Alpha 可以通过 `Hidden` filter 找回。当前没有删除 Alpha 的功能，但可以重命名，未重命名时可能显示为 `anonymous`。`Alpha list` 用于把多条 Alpha 放在一起比较表现和相关性。

页面不提供完整 Alpha output vector，也不提供每只股票逐日权重明细；研究时不要把页面可见的汇总指标误认为底层持仓明细。

官方来源：[How to view your Alphas](https://support.worldquantbrain.com/hc/en-us/articles/24439802248471-How-to-view-your-Alphas)；[How do I delete my Alphas?](https://support.worldquantbrain.com/hc/en-us/articles/5971823272215-How-do-I-delete-my-Alphas)；[Can I give meaningful names to my Alphas?](https://support.worldquantbrain.com/hc/en-us/articles/5969975774103-Can-I-give-meaningful-names-to-my-Alphas)；[Can I see the Alpha output vector?](https://support.worldquantbrain.com/hc/en-us/articles/5969712153239-Can-I-see-the-Alpha-output-vector)

### 12.5 Simulation 的频率与取消

BRAIN Alpha 按日模拟、按日再平衡，不模拟高频或日内交易。正在运行的 simulation 可以使用 `Cancel simulation` 中止。

官方来源：[Does BRAIN platform simulate high frequency trade and intraday trade?](https://support.worldquantbrain.com/hc/en-us/articles/5971017679639-Does-BRAIN-platform-simulate-high-frequency-trade-and-intraday-trade)；[Is it possible to abort a running simulation?](https://support.worldquantbrain.com/hc/en-us/articles/5971303624471-Is-it-possible-to-abort-a-running-simulation)

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

---

## 14. PnL、Drawdown、平滑

### 14.1 `PnL`

你看到的 PnL 是组合层面的表现，不是单只股票单独收益图。

### 14.2 `Drawdown`

就是组合从峰值往下回撤的幅度。

### 14.3 PnL 为什么会突然跳

官方给出的常见原因主要有：

1. `NaN` 和非 `NaN` 频繁切换
2. Alpha 值变化太快
3. 单只股票权重过高

具体诊断和改进动作见 [03 的 PnL 跳变章节](03_optimization_and_submission.md)。

---

## 15. `Neutralization` 的页面语义

如果你不只是想查页面语义，而是想进一步理解：

- 为什么不同数据类别会偏向不同 neutralization
- 什么时候该放在 settings，什么时候该写进表达式
- `D0` 和提交门槛为什么要一起看

继续看：

- [03_optimization_and_submission.md](03_optimization_and_submission.md)

平台语义里：

- 先有表达式原始值
- 如果指定了 neutralization，平台不会直接拿原始值当最终持仓
- 而是先做中性化，再进入后续处理

所以 neutralization 在平台中是“组合层面的结构变换”，不是简单注释项。

---

## 16. 最常见的误读速查

### 16.1 `N/A = 异常`

不一定。  
很多时候只是 OS 样本还没积累够。

### 16.2 `0 = 不持仓`

不对。  
`NaN` 才更接近“不持仓”。

### 16.3 `模拟结果已经扣了真实交易成本`

不对。  
官方说模拟结果不直接包含交易成本，Turnover 只是 proxy。

### 16.4 `提交更多同类 Alpha 一定更好`

不对。  
官方 `Meta Score` 明确看组合相关性与池子质量。

### 16.5 `OS 只是 IS 的重复显示`

不对。  
OS 是提交之后逐步积累出来的样本外表现。

### 16.6 `FAQ 全部都应该进研究文档`

不对。
FAQ 里有大量顾问申请、Workday、银行账户、Referral、账号和竞赛运营信息。它们是平台使用资料，
但不是本仓库 alpha 生成和提交策略的核心知识。能影响研究流程、页面状态、错误码或指标解释的内容，
进入 01-04；纯平台运营内容进入 [05_platform_operations_reference.md](05_platform_operations_reference.md)。

---

## 17. 建议怎样配合其他文档使用

- 想理解平台在做什么：
  看 [01_beginner_guide.md](01_beginner_guide.md)
- 想理解失败项和优化动作：
  看 [03_optimization_and_submission.md](03_optimization_and_submission.md)
- 想理解这些术语在页面和状态里是什么意思：
  看这篇
- 想把平台逻辑落到本仓库：
  看 [02_research_and_data_guide.md](02_research_and_data_guide.md)

---

## 18. 官方来源

本篇主要整理自这些官方 FAQ：

- [What do in sample and out sample mean?](https://api.worldquantbrain.com/faqs/in-sample-out-sample-alphas)
- [Why do my Alphas in out sample show NA?](https://api.worldquantbrain.com/faqs/out-sample-testing)
- [Can you please throw some light on the OS-Tests being performed on the Alphas?](https://api.worldquantbrain.com/faqs/status)
- [Could you please throw some light on meta score and meta alpha count?](https://api.worldquantbrain.com/faqs/meta-score-count)
- [What is transaction cost? And is it important?](https://api.worldquantbrain.com/faqs/transaction-cost)
- [Does the simulation include trading costs?](https://api.worldquantbrain.com/faqs/trading-costs)
- [Can you please explain Universes top 2000, top 500, etc.?](https://api.worldquantbrain.com/faqs/universe-explanation)
- [Even after searching a lot, I am unable to find out more information about stock weights](https://api.worldquantbrain.com/faqs/info-about-stock-weight)
- [What does NaN mean? Is it equal to zero?](https://api.worldquantbrain.com/faqs/nan-zero)
- [Can you please explain the actual effect of Pasteurize(x)?](https://api.worldquantbrain.com/faqs/pasteurize)
- [I want to smooth the PnL curve](https://api.worldquantbrain.com/faqs/smooth-pnl-curve)
- [What is ISladder test and how is it constructed?](https://api.worldquantbrain.com/faqs/isladder-test)
- [What is the IQC scoring metrics?](https://api.worldquantbrain.com/faqs/iqc-scoring-metrics)
- [After I submit an alpha, how much time does it take for it to be reflected as the score on leaderboard?](https://api.worldquantbrain.com/faqs/score-update-frequency)
- [What is Challenge-Country Leaderboard?](https://support.worldquantbrain.com/hc/en-us/articles/41765589602327-What-is-Challenge-Country-Leaderboard)
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
