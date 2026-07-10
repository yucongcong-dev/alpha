# WorldQuant BRAIN 术语、状态与页面语义

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
- 它不等于“这条 Alpha 已经长期成立”

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

可以把它理解成：

- 每交易一美元能赚多少钱

所以：

- 高 Turnover 不一定坏
- 但高 Turnover 如果没有足够高的信号质量和 margin 支撑，就会很脆弱

---

## 10. 字段类型词典

这一节主要解释字段右侧常见的 `type`，尤其是：

- `MATRIX`
- `VECTOR`
- `GROUP`
- `SET`

它们不是“质量评级”，而是字段的数据形态。

### 10.1 `MATRIX`

可以把 `MATRIX` 理解成：

- 普通单值型字段
- 对每个股票、每个日期，通常对应一个数

典型例子：

- `assets`
- `cash_st`
- `debt`
- `cashflow_op`

这类字段通常最适合直接进入普通标量模板，例如：

- `rank(...)`
- `ts_rank(...)`
- `ts_zscore(...)`
- `ts_decay_linear(...)`

对研究流程的直接意义是：

- 如果你看到字段类型是 `MATRIX`，默认先按“普通基本面/标量字段”处理
- 它通常适合做慢频稳定化、cross-field ratio、group relative 结构

### 10.2 `VECTOR`

可以把 `VECTOR` 理解成：

- 向量型字段
- 对每个股票、每个日期，不一定是一个单独的数，更像一组值、事件集合，或需要先聚合的内容

在表达式里，这类字段通常不适合直接像标量一样硬套普通模板，而更常见的第一步是：

- `vec_avg(...)`
- `vec_sum(...)`

比如本仓库在 `fundamental6` 里保留过这类结构：

- `rank(ts_rank(vec_avg({field}), 60))`
- `rank(ts_rank(vec_sum({field}), 60))`

对研究流程的直接意义是：

- `VECTOR` 更适合单独作为 event/vector 专项分支
- 不建议和普通 `MATRIX` 字段放进同一个 broad-search 池里无差别扫
- 它往往更依赖：
  - 先聚合
  - 再平滑
  - 再决定是否需要事件触发

### 10.3 `GROUP`

可以把 `GROUP` 理解成：

- 组结构字段
- 它更像“某个对象属于哪个组”或“某种分组语义”

这类字段常见的用途不是直接拿去做普通时间序列变换，而是参与：

- `group_rank`
- `group_neutralize`
- `group_backfill`
- bucket/group 相关结构

在本仓库的模板语境里，`GROUP` 分支经常意味着：

- 先把字段转成适合组内比较的结构
- 再做 rank / zscore / decay

更实用的记法是：

- `MATRIX` 更像“数值本身”
- `GROUP` 更像“分组语义”

### 10.4 `SET`

可以把 `SET` 理解成：

- 集合型字段
- 它和 `VECTOR` 一样，都不是最朴素的单值标量

在实战里，`SET` 和 `VECTOR` 往往都不适合直接按普通标量字段粗暴处理，通常更适合：

- 单独分支
- 保留更窄的默认模板主干
- 先做聚合或结构转换，再进入时序/截面模板

如果当前没有平台级更细的字段释义，研究时可以先把它当作：

- “需要额外结构处理的非标量字段”

而不是：

- “直接可和 `assets`、`debt` 一样处理的字段”

### 10.5 一个够用的实战记忆法

如果只想快速判断研究路线，可以先这样记：

- `MATRIX`：普通单值字段
  - 默认走标量主干模板
- `VECTOR`：向量/事件型字段
  - 默认先 `vec_avg / vec_sum`
- `GROUP`：分组语义字段
  - 默认考虑 group 相关结构
- `SET`：集合型字段
  - 默认单独处理，不和普通标量字段混扫

对 `fundamental6` 这种数据集，这个区分尤其重要：

- `MATRIX` 适合作为基本面主干
- `VECTOR` 更适合作为事件/向量专项支路
- `GROUP / SET` 不该简单混回普通标量模板池

---

## 11. Coverage、Alpha list、Correlation 工具

### 11.1 `Coverage`

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

### 11.2 `Alpha list`

官方 Glossary 里把 `Alpha list` 定义成：

- 用来比较多条 Alpha
- 以及查看它们彼此相关性的工具

对本地工作流最有用的启发是：

- 不要只盯单条 Alpha
- 也要看一组 Alpha 是否只是高相关的小变体

### 11.2.1 `alphaCount` / `userCount` 怎么看

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

### 11.2.2 放到 `fundamental6` 上该怎么整体理解

如果把上面的 `MATRIX / VECTOR / coverage / dateCoverage / alphaCount / userCount` 一起看，`fundamental6` 更适合被理解成：

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

### 11.3 `Correlation`

官方 Glossary 直接把 Correlation 解释成：

- 衡量 Alpha 独特性的指标

这和本地研究流程是直接对应的：

- `SELF_CORRELATION` 更像“和自己池子太像”
- `PROD_CORRELATION` 更像“和平台已有池子太像”

所以相关性问题本质上不是“结果页面的小红字”，而是平台在判断：

- 这条 Alpha 有没有增量价值

---

## 12. 提交检查词典

这一节不追求覆盖平台所有检查，而是优先解释本仓库最常遇到的几类。

### 12.1 `LOW_SHARPE`

- 风险调整后的收益不够稳定
- 更像“信号质量不够硬”，而不只是收益不够高

本地通常优先检查：

- 是否缺少标准化
- 是否缺少 group-relative 结构
- 是否没有做足够平滑

### 12.2 `LOW_FITNESS`

官方公式是：

- `Fitness = Sharpe * sqrt(abs(Returns) / max(Turnover, 0.125))`

所以它不是独立问题，而是下面三者之一或组合：

- `Sharpe` 不够
- `Returns` 不够
- `Turnover` 太高

### 12.3 `HIGH_TURNOVER`

- 代表信号变化太快
- 真实交易成本压力通常也会更高

在本仓库里更常见的修法是：

- 增加 `Decay`
- 用 `trade_when`
- 用更稳定的截面整形和 backfill

### 12.4 `CONCENTRATED_WEIGHT`

- 代表少数股票权重过大
- 更接近“组合结构问题”，不只是表达式长得难看

优先怀疑：

- 极端值没处理
- `truncation` 太松
- 没有做 rank / group 处理

### 12.5 `LOW_SUB_UNIVERSE_SHARPE`

Glossary 把 robust performance 明确当成平台关心的方向。

对实战更好记的理解是：

- 你的 Alpha 在更小、更液态的子宇宙里不够稳
- 它提示的往往不是“再调一个窗口”，而是结构泛化能力不够

### 12.6 `SELF_CORRELATION`

- 和你自己已有 Alpha 太像
- 平台通常不会鼓励你反复提交同一个想法的近邻分支

所以本地更推荐：

- 换字段关系
- 换模板家族
- 换 grouping

而不是只做：

- `20 -> 22`
- `60 -> 63`

### 12.7 `PROD_CORRELATION`

- 和平台已有已提交 Alpha 太像
- 说明它缺少足够的独特性

这类问题通常也更适合做结构替换，而不是参数微调。

### 12.8 `WEIGHT_COVERAGE`

虽然它在不同页面或 FAQ 里展示口径可能略有不同，但核心都指向：

- 你的组合权重没有足够稳定、足够均匀地覆盖当前 Universe

本地最实用的检查方向通常是：

- 是否有大量 `NaN`
- 是否 coverage 很低却没做 backfill
- 是否某些极端值把权重挤到少数股票上

---

## 13. PnL、Drawdown、平滑

### 13.1 `PnL`

你看到的 PnL 是组合层面的表现，不是单只股票单独收益图。

### 13.2 `Drawdown`

就是组合从峰值往下回撤的幅度。

### 13.3 PnL 为什么会突然跳

官方给出的常见原因主要有：

1. `NaN` 和非 `NaN` 频繁切换
2. Alpha 值变化太快
3. 单只股票权重过高

常见修法：

- `backfill`
- `decay`
- 更严格的 `truncation`

---

## 14. `Neutralization` 的页面语义

平台语义里：

- 先有表达式原始值
- 如果指定了 neutralization，平台不会直接拿原始值当最终持仓
- 而是先做中性化，再进入后续处理

所以 neutralization 在平台中是“组合层面的结构变换”，不是简单注释项。

---

## 15. 最常见的误读速查

### 15.1 `N/A = 异常`

不一定。  
很多时候只是 OS 样本还没积累够。

### 15.2 `0 = 不持仓`

不对。  
`NaN` 才更接近“不持仓”。

### 15.3 `模拟结果已经扣了真实交易成本`

不对。  
官方说模拟结果不直接包含交易成本，Turnover 只是 proxy。

### 15.4 `提交更多同类 Alpha 一定更好`

不对。  
官方 `Meta Score` 明确看组合相关性与池子质量。

### 15.5 `OS 只是 IS 的重复显示`

不对。  
OS 是提交之后逐步积累出来的样本外表现。

---

## 16. 建议怎样配合其他文档使用

- 想理解平台在做什么：
  看 [01_beginner_guide.md](01_beginner_guide.md)
- 想理解失败项和优化动作：
  看 [02_optimization_guide.md](02_optimization_guide.md)
- 想理解这些术语在页面和状态里是什么意思：
  看这篇
- 想把平台逻辑落到本仓库：
  看 [03_repo_practice_guide.md](03_repo_practice_guide.md)

---

## 17. 官方来源

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
