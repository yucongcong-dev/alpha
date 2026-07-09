# WorldQuant BRAIN 术语、状态与页面语义

> 目标：把平台里最容易混淆的术语、状态、评分、OS 页面字段收口成一篇可快速查阅的文档。

---

## 1. 这篇文档适合什么时候看

当你遇到下面这些问题时，先来这里查：

- `IS` 和 `OS` 到底分别是什么？
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

### 2.3 一个很重要的点

官方明确说明：

- `IS` 和 `OS` 使用的是同一套 neutralization 设置

所以不要把 OS 表现变化简单理解成“平台换了 neutralization”。

### 2.4 `Test Period`

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

## 10. Coverage、Alpha list、Correlation 工具

### 10.1 `Coverage`

官方 Glossary 的定义是：

- `Coverage` 指在当前 Universe 里
- 某个 data field 有定义值的 instrument 占比

这对研究的直接意义是：

- coverage 低，不代表字段一定不能用
- 但通常需要配合 `ts_backfill`、`kth_element`、`group_backfill` 之类方法处理缺失

所以在本仓库里看到 `coverage / dateCoverage` 过滤时，可以把它理解成：

- 先验质量信号
- 不是绝对真理

### 10.2 `Alpha list`

官方 Glossary 里把 `Alpha list` 定义成：

- 用来比较多条 Alpha
- 以及查看它们彼此相关性的工具

对本地工作流最有用的启发是：

- 不要只盯单条 Alpha
- 也要看一组 Alpha 是否只是高相关的小变体

### 10.3 `Correlation`

官方 Glossary 直接把 Correlation 解释成：

- 衡量 Alpha 独特性的指标

这和本地研究流程是直接对应的：

- `SELF_CORRELATION` 更像“和自己池子太像”
- `PROD_CORRELATION` 更像“和平台已有池子太像”

所以相关性问题本质上不是“结果页面的小红字”，而是平台在判断：

- 这条 Alpha 有没有增量价值

---

## 11. PnL、Drawdown、平滑

### 10.1 `PnL`

你看到的 PnL 是组合层面的表现，不是单只股票单独收益图。

### 10.2 `Drawdown`

就是组合从峰值往下回撤的幅度。

### 10.3 PnL 为什么会突然跳

官方给出的常见原因主要有：

1. `NaN` 和非 `NaN` 频繁切换
2. Alpha 值变化太快
3. 单只股票权重过高

常见修法：

- `backfill`
- `decay`
- 更严格的 `truncation`

---

## 11. `Neutralization` 的页面语义

平台语义里：

- 先有表达式原始值
- 如果指定了 neutralization，平台不会直接拿原始值当最终持仓
- 而是先做中性化，再进入后续处理

所以 neutralization 在平台中是“组合层面的结构变换”，不是简单注释项。

---

## 12. 最常见的误读速查

### 12.1 `N/A = 异常`

不一定。  
很多时候只是 OS 样本还没积累够。

### 12.2 `0 = 不持仓`

不对。  
`NaN` 才更接近“不持仓”。

### 12.3 `模拟结果已经扣了真实交易成本`

不对。  
官方说模拟结果不直接包含交易成本，Turnover 只是 proxy。

### 12.4 `提交更多同类 Alpha 一定更好`

不对。  
官方 `Meta Score` 明确看组合相关性与池子质量。

### 12.5 `OS 只是 IS 的重复显示`

不对。  
OS 是提交之后逐步积累出来的样本外表现。

---

## 13. 建议怎样配合其他文档使用

- 想理解平台在做什么：
  看 [01_beginner_guide.md](01_beginner_guide.md)
- 想理解失败项和优化动作：
  看 [02_optimization_guide.md](02_optimization_guide.md)
- 想理解这些术语在页面和状态里是什么意思：
  看这篇
- 想把平台逻辑落到本仓库：
  看 [03_repo_practice_guide.md](03_repo_practice_guide.md)

---

## 14. 官方来源

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
