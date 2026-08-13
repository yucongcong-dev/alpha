# WorldQuant BRAIN 优化与提交篇

> 目标：把 `Sharpe / Fitness / Turnover / Correlation` 的问题拆开，并把研究、稳健性验证和最终提交串成一条流程。

---

## 1. 优化前先做一件事

不要直接进入“多跑一些模板”。

先问：

- 是想法不对？
- 是表达式翻译错了？
- 是设置不匹配？
- 还是只是参数还没调好？

更好的顺序通常是：

1. 假设
2. 结构
3. 设置
4. 参数

### 1.1 Research FAQ 的诊断矩阵

FAQ 里大多数优化建议可以归成下面这张表。它比逐篇记 FAQ 更适合本仓库落地：

| 症状 | 先问什么 | 优先动作 |
|---|---|---|
| Sharpe 低 | 收益低，还是收益波动太大？ | 增强信号、分组比较、neutralization、标准化和平滑 |
| Returns 低 | 信号方向弱，还是交易太少？ | 换数据类别/字段关系，必要时降低 decay 或放宽事件条件 |
| Turnover 高 | 是信号抖动、NaN 跳变，还是低流动性股票贡献太多？ | decay、trade_when、hump、backfill、流动性分层 |
| Fitness 低 | Sharpe、Returns、Turnover 哪个拖累公式？ | 先拆公式，不把 Fitness 当独立黑盒 |
| Margin 低 | 每交易一美元是否赚得太少？ | 提高 returns 或降低无效换手 |
| PnL 突跳 | NaN、权重集中、Alpha 值突变哪个在驱动？ | backfill、decay、truncation、rank/normalize |
| Weight Coverage 失败 | 覆盖低还是权重过度集中？ | 检查缺失、极值、long/short 是否失衡 |
| Correlation 高 | 是同字段近邻，还是同一研究假设重复？ | 换字段族、算子族、grouping、neutralization 或假设 |

这张表也定义了本仓库的 refine 优先级：先定位主失败项，再做少量有语义的结构替换。
不要把 FAQ 理解成“每篇文章对应一个模板补丁”。

---

## 2. 优化前确认结果阶段

开始处理失败项前，先确认当前看到的是 simulation 的 IS 结果、Check Submission 状态，
还是提交后逐步积累的 OS 指标。OS 页面上的 `N/A` 可能只是样本尚未积累完成，不应当作
表达式失败直接进入 refine。

IS、Semi-OS、OS、OSTEST 生命周期和 N/A 条件统一见
[04 平台术语与状态 Reference](04_platform_reference.md)。下文默认讨论已经取得明确
simulation 或 Check Submission 结果的候选。

---

## 3. 当 `LOW_SHARPE` 出现时

先判断主要原因属于哪一类：

- 字段或研究假设本身信息量弱
- 市场、行业或其他分组暴露过重
- 表达式噪声大，缺少合理的标准化或平滑
- 结果只依赖某个孤立窗口，存在参数过拟合风险

确认原因后，再按[提升 Sharpe 的更合理方向](#11-提升-sharpe-的更合理方向)选择动作，
不要在原因尚未确定时同时修改字段、窗口和 neutralization。

> LOW_SHARPE 的平台语义见 [04 的提交检查词典](04_platform_reference.md#13-提交检查词典)。

---

## 4. 当 `LOW_FITNESS` 出现时

不要把 `LOW_FITNESS` 当成独立问题。
先按 Fitness 公式拆成 3 个方向：

- `Sharpe` 太低？
- `Returns` 太低？
- `Turnover` 太高？

如果不先拆原因，继续跑更多模板通常只会增加噪声。

具体优化顺序见[提升 Fitness 的更合理顺序](#12-提升-fitness-的更合理顺序)，
不要把三个分量同时调参。

公式、当前门槛和页面舍入风险统一见
[04 的提交检查词典](04_platform_reference.md#13-提交检查词典)。优化时不要围绕页面显示的
临界值做密集微调，应给候选保留稳定余量。

---

## 5. 当 `HIGH_TURNOVER` 出现时

先定位换手来源，而不是直接增大 `Decay`：

- 日常小幅抖动
- 缺失值导致的跳变
- 只在少数日期有效的事件信号
- 低流动性股票贡献过多

不同来源对应不同工具。完整判断和工具职责见
[降低 Turnover 的一组工具](#19-降低-turnover-的一组工具)。

> HIGH_TURNOVER 的平台语义见 [04 的提交检查词典](04_platform_reference.md#13-提交检查词典)。

---

## 6. D0 Alpha 应该单独研究

`Delay=0` 不是简单把 D1 Alpha 的设置改成 0。官网对 D0 的定位是：

- 使用当日最新可用信息
- 更快响应业绩、并购、回购、产品发布和宏观新闻等事件
- 通常比 D1 有更高 Turnover 和交易成本压力

D0 研究建议按下面的顺序进行：

1. 先确认字段真的支持 D0，并检查适用 Region
2. 优先使用事件逻辑和 `trade_when`
3. 使用流动性更好的 Universe；USA 通常从 `TOP1000` 或更核心 Universe 起步
4. 同一个想法同时跑 D0 和 D1，保留 D1 作为对照
5. 检查 Sub-Universe、Robust Universe 和 after-cost 表现

如果同一表达式在 D1 的 Sharpe 高于 D0，官网建议直接考虑提交 D1，因为它通常
同时具有更高表现和更低交易成本，而不是为了 D0 标签继续强行优化。

如果你想系统看官网对：

- `Simulation Results`
- `Alpha Submission`
- `Neutralization`
- `D0`

这些高级主题的原始口径和统一收口，优先继续看：

- 本文后半部分的提交前检查与高级设置章节

> D0/D1 Fitness 评级和 OS 页面 N/A 含义见 [04 平台 Reference](04_platform_reference.md)。

---

## 7. 当相关性问题出现时

### 7.1 `SELF_CORRELATION`

说明你现在这条 Alpha 和你自己已有 Alpha 太像。

官网 FAQ 给出的典型提交语义是：

- Self-Correlation cutoff 为 `0.7`
- 当相关性高于 cutoff，且新 Alpha 的表现没有提高至少 `10%` 时，检查失败

因此超过 `0.7` 不等于只靠抬高一点 Sharpe 就一定能解决。平台仍然更鼓励换数据集、
换算子集合和换研究想法，而不是围绕旧 Alpha 做参数化复制。

> SELF_CORRELATION 的平台语义见 [04 的提交检查词典](04_platform_reference.md#13-提交检查词典)。

### 7.2 `PROD_CORRELATION`

说明它和平台已有 Alpha 太像。

> PROD_CORRELATION 的平台语义见 [04 的提交检查词典](04_platform_reference.md#13-提交检查词典)。

### 7.3 这类问题最容易被误处理

官方更推荐的是结构替换，而不是窗口微调：

- 换字段
- 换字段关系
- 换算子
- 换 grouping
- 换 neutralization
- 直接换研究假设

因此：

- `20 -> 22`
- `60 -> 63`

不该成为降低相关性的主手段。

更符合官方建议的替换顺序通常是：

- 先换等价字段
- 再换相近算子
- 再换 grouping / neutralization
- 最后直接换研究假设

---

## 8. 当权重或集中度问题出现时

如果遇到：

- `CONCENTRATED_WEIGHT`
- weight coverage / concentrated exposure 一类问题

优先检查：

- 有没有极端值直接驱动权重
- 是否缺少 rank/normalize/group 处理
- truncation 是否太松
- 是否有大量 NaN 或覆盖不平衡

这类问题的本质通常不是平台太严格，而是组合过于集中。

官方对这类问题的经验也很明确：

- coverage 太低时，先判断是不是缺值问题
- 如果是 infrequent update，可考虑 `ts_backfill`
- 如果是分布太尖、极值太多，优先考虑 `rank / group_rank / zscore / scale`

不要把 `backfill` 当万能修法。

如果需要大量 backfill 才能勉强通过，通常更该回头怀疑字段或假设本身。

> 权重集中和覆盖的平台语义见 [04 的提交检查词典](04_platform_reference.md#13-提交检查词典)。

---

## 9. 当 `LOW_SUB_UNIVERSE_SHARPE` 出现时

这类失败项最容易被误解成：

- “主 Sharpe 已经够了，为什么还不过”

更接近平台语义的理解是：

- 你的 Alpha 在更小、更液态、更核心的子宇宙里不够稳
- 也就是它的泛化能力或稳健性还不够

所以更推荐优先检查：

- 信号是否过度依赖尾部股票
- 是否只在较宽 Universe 里勉强成立
- 是否暴露过重、分布过尖、coverage 不稳

更常见的修法通常不是：

- `20 -> 22`

而是：

- 更强的标准化
- 更稳的 grouping / neutralization
- 更好的缺失值处理
- 更弱化极端值和集中暴露

如果它同时还伴随：

- `HIGH_TURNOVER`
- `CONCENTRATED_WEIGHT`

那往往说明这条 Alpha 结构本身就不够稳。

官方给出的门槛公式是：

```text
subuniverse_sharpe
>= 0.75 * sqrt(subuniverse_size / alpha_universe_size) * alpha_sharpe
```

这个测试不是简单把原表达式改成较小 Universe 重跑。平台会：

1. Pasteurize 到目标 Sub-Universe
2. 对剩余股票执行 Market Neutralization
3. 将 Alpha 重新缩放到原始规模
4. 用得到的 PnL 计算 Sub-Universe Sharpe

例如 USA `TOP3000` 通常会检查更液态的 `TOP1000`。如果结果主要来自 TOP1000
以外的低流动性股票，Sub-Universe 表现会明显下降。

> LOW_SUB_UNIVERSE_SHARPE 的平台语义和缩放公式见
> [04 的提交检查词典](04_platform_reference.md#13-提交检查词典)。

---

## 10. 交易成本与 Margin 如何影响优化

交易成本、Turnover、Margin 的平台定义和带日期门槛统一见
[04 的交易成本章节](04_platform_reference.md#9-交易成本turnovermargin)与
[提交检查词典](04_platform_reference.md#13-提交检查词典)。优化阶段只需抓住这些动作：

- 不要把普通模拟 Returns 当成已经扣除真实交易成本的结果
- Turnover 较高时，同时检查 Margin、after-cost 表现和信号质量
- Margin 较低时，优先提高有效 PnL，或减少没有信息增量的交易
- 区分经验目标与平台硬检查，不要把某个 Turnover 建议值当成永久统一门槛

---

## 11. 提升 Sharpe 的更合理方向

官方口径可以浓缩成两件事：

- 提高收益
- 降低波动

常见抓手：

- neutralization
- grouping operators
- 更好的标准化
- 更平滑的数据处理

换句话说，Sharpe 的提升通常不是靠“更花的表达式”，而是靠“更稳的结构”。

FAQ 里还特别提醒：不要为了提高 Sharpe 只反复调参数。更好的改进通常来自：

- 更有解释力的数据字段
- 更低噪声的表达式结构
- 合理的 group/neutralization
- 对缺失、极值和更新频率的处理

如果一条 Alpha 的 Sharpe 只能靠某个孤立窗口撑住，优先把它当作过拟合风险，而不是
“终于调到最优参数”。

---

## 12. 提升 Fitness 的更合理顺序

经验顺序更推荐这样：

1. 先让 `Sharpe` 过基础线
2. 再看 `Turnover` 是否过高
3. 最后再追更高 `Returns`

原因是：

- Sharpe 太差时，Returns 再高也很难稳
- Turnover 太高时，Fitness 容易被交易成本和惩罚拖垮

---

## 13. 提升 Returns 时要保持克制

官方承认提高 Returns 往往会伴随：

- 更高 Turnover
- 更高波动
- 更强噪声暴露

所以提高 Returns 不能脱离 Fitness 公式单独看。

如果一个 Alpha 已经低换手但质量一般，很多时候最该做的不是继续压 Turnover，而是：

- 提高信号质量
- 改善结构
- 拉高 Sharpe

还有一条官方经验值得记住：

- 数据类别本身也是收益杠杆

所以当价量类模板长期弱时，更合理的动作通常不是继续堆局部变体，而是：

- 换字段族
- 换事件源
- 换关系结构

FAQ 里给过几类提高 Returns 的常见方向，但都要和风险一起看：

- 降低过强的 Decay，允许信号更快反应
- 在更液态或更合适的 Universe 中验证想法
- 让 long/short 两侧更均衡，避免收益来自单侧市场暴露
- 用数据类别差异寻找更强信息源，而不是只压榨同一价量字段

这些动作可能同时推高 Turnover 或波动，因此必须回到 Fitness、Drawdown 和 after-cost
检查一起判断。

---

## 14. `Robust universe` 应该怎么直觉理解

官方社区里围绕 `robust universe sharpe / returns` 的讨论很多，说明这是常见痛点。

够用的直觉是：

- 普通 IS 结果回答“这条 Alpha 在当前 Universe 里表现如何”
- robust universe 更像在问“换到更核心、更稳的流动性子集后，它还成立吗”

所以如果一条 Alpha：

- 主回测不差
- 但 robust universe / sub-universe 表现长期弱

那通常更说明：

- 它对边缘样本依赖太强
- 或结构稳健性还不够

## 15. 最不流动 50% 的 after-cost 检查

平台定义和带日期阈值见
[04 的 after-cost Sharpe 词典](04_platform_reference.md#138-最不流动-50-的-after-cost-sharpe)。
这里重点只记录失败后的研究动作。

失败时不应该简单删除低流动性股票。优先考虑：

- 按流动性设置不同的 Decay
- 使用 `cap`、平均成交量等构造流动性分组
- 用 `group_neutralize()` 降低 size / liquidity 风险暴露
- 在有明确风险向量时使用 `vector_neut()`

## 16. 一套可执行的抗过拟合测试

官方社区明确建议把 disciplined research 放在“找到最高 IS 数字”之前。
进入最终候选池前至少做：

1. Rank test：把最终 Alpha 转成 rank，检查相对排序是否仍有效
2. Binary test：只保留 `-1/+1` 方向，检查是否过度依赖精确幅度
3. Sub/Super Universe test：检查不同股票池下是否仍成立
4. Train/Test：研发阶段不查看 Test 结果，最后一次性验证
5. 参数稳定性：自然窗口附近不应只剩一个孤立最优点
6. 因子暴露检查：避免表现主要来自波动率、规模或常见风格因子
7. Max Trade test：在 `Max Trade=ON` 下做可交易性压力测试，观察表现是否断崖下降

`Max Trade` 是社区常用稳健性压力测试，不是这里描述的固定提交门槛。它更适合在
最终候选阶段使用，而不是默认开启后替代普通 broad search。

几个很实用的官方社区经验：

- 不要总选数字最高的参数，稳定的次优点通常更可信
- `4` 天和 `6` 天都可用时，可以选 `5`，或简单平均两个版本
- 不要为了通过某项测试反向拟合该测试
- 不要陷入“IS 表现越优秀越好”的陷阱，重点是表现能否保持

Test Period 可以更具体地按下面方式使用：

- 五年 IS 先用约 `80/20` 划分，常见做法是隐藏最后一年
- 只用前四年研发，满意后再显示 Test Period
- Test Sharpe / Fitness 等下降超过约 `50%`，通常是明显的过拟合警报
- 进一步用 `20% / 30% / 40%` 的不同 Test Period 做时间稳定性检查

### 16.1 Decay 改动与过拟合边界

官方 FAQ 的区分很实用：同一表达式把 Decay 从 `1` 改到 `5`，如果变化有合理的平滑假设并通过参数敏感性检查，通常不应直接称为过拟合；在 `5` 和 `6` 之间继续追逐一次回测中的最高值，则更接近对噪声调参。

本地记录应至少保留自然窗口附近的 A/B 结果，优先选择稳定平台而不是单点最优。不要把“Decay 1→5”写成自动有效，也不要把“Decay 5→6”写成自动失败。

官方来源：[Does changing the decay value from 1 to 5 for the same expression mean overfitting?](https://support.worldquantbrain.com/hc/en-us/articles/5970380583191-Does-changing-the-decay-value-from-1-to-5-for-the-same-expression-mean-overfitting)

## 17. 算子改动的 A/B 与线性组合

算子顺序的基础含义见 [01 的入门例子](01_beginner_guide.md#62-算子顺序和-backfill-窗口不要望文生义)，
时序、截面和分组顺序对应的研究语义见
[02 的模板设计说明](02_research_and_data_guide.md#114-算子顺序就是研究语义)。本节只说明优化阶段怎样验证改动。

设置层 `Decay` 与表达式层 `ts_decay_linear(...)` 会叠加。为了让结果可解释，推荐按下面顺序做干净 A/B：

1. 原始版本
2. 只修改一个算子顺序
3. 回到原始或当前最佳版本，只实验 simulation setting 的 `Decay`
4. 有字段缺失或明确平滑假设时，再分别实验 backfill 窗口或表达式层 decay

官网社区更建议保持外层算子简单，让原始研究假设仍然可辨认。不要通过不断套
`rank / quantile / zscore` 来追逐单次 IS 提升。

把多个弱表达式直接线性相加也存在三个风险：

- 两个子表达式尺度不同，较小者几乎不起作用
- 无法单独观察子表达式之间的相关性
- 为系数和组合方式调参，很容易形成 IS 过拟合

如果确实需要组合，先分别标准化和验证每个子表达式；不要用组合掩盖单个假设本身偏弱。官方 FAQ 不建议在单个 Alpha 内混合多个 signal 来追求 Sharpe 或 Returns；更适合先独立验证，再在 Alpha 组合层或平台组合工具层处理。

官方来源：[Is it ok to mix signals inside an Alpha to improve the Sharpe ratio and return?](https://support.worldquantbrain.com/hc/en-us/articles/5970027840791-Is-it-ok-to-mix-signals-inside-an-Alpha-to-improve-the-Sharpe-ratio-and-return)

---

## 18. PnL 曲线突然跳变时先查什么

官方给出的常见原因有 3 类：

1. `NaN` 和非 `NaN` 频繁切换
2. Alpha 值本身变化过快
3. 单只股票权重过高

因此常见修法也比较明确：

- 用 `backfill` 减少 NaN 跳变
- 用 `decay` 或平均化处理做平滑
- 用更严格的 `truncation` 控制单股权重

这一块很实用，因为它把“PnL 不平滑”从抽象问题变成了可检查的结构问题。

如果最大回撤集中在回测初始年份，官方建议先检查市场方向暴露，并优先验证合理的 Neutralization；如果处理后仍异常，应回到 idea 或实现方式本身，而不是继续盲目调参。

官方来源：[How do I resolve max drawdowns in initial years of the backtest?](https://support.worldquantbrain.com/hc/en-us/articles/5969512978199-How-do-I-resolve-max-drawdowns-in-initial-years-of-the-backtest)

---

## 19. 降低 Turnover 的一组工具

可以把下面这组东西当成“稳健化工具组”：

- `Decay`
- `trade_when`
- `hump / hump_decay`
- `ts_decay_linear / ts_decay_exp_window`
- `rank()`
- `ts_backfill`

把它们放在一起理解，比孤立看任何一个都更有效。

`Truncation` 主要控制单股权重和集中度，不应被当作首要降换手工具。

其中几类工具的职责不同：

- `hump / hump_decay`：过滤幅度很小的日常抖动
- `ts_decay_linear / ts_decay_exp_window`：平滑持续变化的信号
- `days_from_last_change`：识别快速衰减或长时间未更新的字段
- `trade_when`：围绕事件条件开仓、非事件期延持，并在事件结束或信号失效时退出

因此 `trade_when` 不只是高换手补丁，它本身就是事件驱动 Alpha 的结构。

降低 Turnover 时要避免两个极端：

- 只把 Decay 一路调大，导致信号被抹平
- 只用 `trade_when` 延持旧值，却不检查事件条件是否真的有经济含义

更合理的是先判断 turnover 来源：

- 日常小幅抖动：优先 `hump / decay`
- 缺失值频繁出现：优先 `ts_backfill / group_backfill`
- 事件只在少数日期有效：优先 `trade_when`
- 低流动性股票贡献过多：优先流动性分层或更核心 Universe

如果高换手主要来自低流动性股票，不要给整个 Universe 统一增加 Decay；可以按 `cap`
或平均成交量分层，并让低流动性组采用更长的持有周期。

---

## 20. ISLadder 应该怎么理解

官方把它描述为一种显著性检验思路：

- 用来降低“随机噪声看起来像有效 Alpha”的假阳性

实战上最重要的理解不是它的统计细节，而是：

- 有些 Alpha 看上去回测不错
- 但未必真的显著
- Ladder 一类测试就是在拦这种“像信号但可能只是噪声”的结果

所以别把 Ladder 失败简单理解成“平台太苛刻”，它本质上是在做反噪声筛查。

---

## 21. 优化纪律速查

| 错误倾向 | 正确原则 |
|---|---|
| 把“多跑”或模板数量当成优化 | 先写清假设和主失败项，再决定是否增加实验 |
| 把调参数和同模板族的密集近邻搜索当成研究 | 先改字段、结构或 grouping，再做小范围参数扰动 |
| 把高 Returns 当成高质量 | 同时检查 Sharpe、Fitness、Turnover、Drawdown 和稳健性 |
| 把 Fitness 当成独立黑盒 | 回到公式拆分 Sharpe、Returns 和 Turnover |
| 用窗口微调解决相关性 | 优先替换字段族、算子族、grouping 或研究假设 |
| 混淆 IS、OS、Simulate 和 Check Submission | 先确认结果阶段，再解释失败项和采取动作 |

---

## 22. 提交前统一收口

优化结束不等于可以提交。最终候选应按固定顺序复查：

1. `Sharpe` 是否达到基础质量要求
2. `Fitness` 的问题来自收益、稳定性还是换手
3. `Turnover` 与 `Margin` 是否匹配
4. `PnL / Drawdown` 是否依赖少数日期或股票
5. Neutralization 是否与数据类别、表达式结构匹配
6. Sub/Super Universe、Train/Test 和参数扰动是否稳定
7. `SELF_CORRELATION / PROD_CORRELATION` 是否可接受
8. 权重覆盖和集中度是否健康

提交判断可以压成两层：

- 第一层检查收益质量、成本和可实现性
- 第二层检查独特性、稳健性和是否值得加入现有 Alpha 池

### 22.1 Neutralization 的最终决策

表达式里的 `group_neutralize(x, group)` 与回测设置的 Neutralization 都会改变持仓结构，但作用范围不同：前者只处理表达式中传入的局部值，Simulation Settings 的 Neutralization 则在平台操作链最后对整个 Alpha 起作用。

> `group_neutralize(...)` 算子与 `neutralization` 设置的逐项边界见
> [04 的 8.5 小节](04_platform_reference.md#85-truncate-truncation-group_neutralize-neutralization)。

`Neutralization=None` 适合用于分析数据集、验证表达式或做研究对照；正式提交时，如果没有最后一层 `group_neutralize`、`group_normalize` 等平衡处理，可能造成 long/short 失衡和市场风险暴露，不能把 `None` 当成默认提交方案。是否保留双层处理，应通过对照实验和风险暴露检查决定。

官方来源：[Why is it not recommended to submit Neutralization None alphas](https://support.worldquantbrain.com/hc/en-us/articles/13306223024151-Why-is-it-not-recommended-to-submit-Neutralization-None-alphas)；[Difference between group neutralize and Neutralization setting](https://support.worldquantbrain.com/hc/en-us/articles/6425949726487-Difference-between-group-neutralize-and-Neutralization-setting)

常见起点：

- Fundamental / Analysts / Earnings：`Industry`
- News / Social / Sentiment：`Subindustry`
- Option：`Market` 或 `Sector`
- Price Volume / Macro：`Market`、`Sector`，必要时再试 `Industry`

### 22.2 D0 的提交判断

D0 应当作为独立研究分支。除更高换手和成本压力外，还要验证同一逻辑在 D1 上
是否保留合理表现。如果 D1 明显更强，不应为了 D0 标签继续强行调参。

### 22.3 社区压力测试与平台硬门槛要分开

Rank/Binary、Train/Test、参数扰动、Sub/Super Universe 和 Max Trade 挑战用于提高
研究置信度；它们不应被描述成平台统一硬门槛。文档和结果记录中应明确区分：

- 平台 submission check
- 本仓库主动增加的稳健性检查

---

## 23. 官方来源

- [Understanding Data in BRAIN: Key Concepts and Tips](https://platform.worldquantbrain.com/learn/documentation/understanding-data/data)
- [How to use the Data Explorer](https://platform.worldquantbrain.com/learn/documentation/understanding-data/how-use-data-explorer)
- [Must-read posts: How to improve your Alphas](https://platform.worldquantbrain.com/learn/documentation/advanced-topics/list-must-read-posts-how-improve-your-alphas-are-submitted)
- [Neutralization](https://platform.worldquantbrain.com/learn/documentation/advanced-topics/neut-cons)
- [D0](https://platform.worldquantbrain.com/learn/documentation/advanced-topics/getting-started-d0)
- [How can you avoid overfitting?](https://support.worldquantbrain.com/hc/en-us/community/posts/8209806533015-How-can-you-avoid-overfitting-)
- [How do you get a higher Sharpe?](https://support.worldquantbrain.com/hc/en-us/community/posts/8123350778391-How-do-you-get-a-higher-Sharpe-)
- [5 ways to potentially increase returns](https://support.worldquantbrain.com/hc/en-us/community/posts/8833033953559--BRAIN-TIPS-5-ways-to-potentially-increase-returns-of-an-alpha)
- [How do you reduce correlation of a good Alpha?](https://support.worldquantbrain.com/hc/en-us/community/posts/8046468280727--BRAIN-TIPS-How-do-you-reduce-correlation-of-a-good-alpha-)
- [Using trade_when for Event Alphas and Low Turnover Alphas](https://support.worldquantbrain.com/hc/en-us/community/posts/8360363631127--BRAIN-TIPS-Using-trade-when-for-Event-Alphas-and-Low-Turnover-Alphas)
- [Most illiquid 50% instruments after-cost test](https://support.worldquantbrain.com/hc/en-us/articles/19083525654551-Error-message-Most-illiquid-50-instruments-after-cost-Sharpe-is-above-cutoff-of-original-universe)
- [Alpha better suited for Delay 1](https://support.worldquantbrain.com/hc/en-us/articles/19083452017559-Error-Message-Alpha-better-suited-for-Delay-1)
- [Sub-universe Sharpe cutoff and calculation](https://support.worldquantbrain.com/hc/en-us/articles/6568644868375-How-do-I-resolve-this-error-Sub-universe-Sharpe-NaN-is-not-above-cutoff)
- [Self-correlation cutoff and performance exception](https://support.worldquantbrain.com/hc/en-us/articles/6726867827991-Ideas-to-clear-the-submission-test-Self-correlation-0-9588-is-above-cutoff-of-0-7-and-performance-not-better-by-10-0-or-more)
- [How to improve Sharpe](https://support.worldquantbrain.com/hc/en-us/articles/20251383456663-How-to-improve-Sharpe)
- [How to improve returns](https://support.worldquantbrain.com/hc/en-us/articles/20251364149655-How-to-improve-returns)
- [How to improve Turnover](https://support.worldquantbrain.com/hc/en-us/articles/20251419309719-How-to-improve-Turnover)
- [How to increase fitness of alphas](https://support.worldquantbrain.com/hc/en-us/articles/20251386376471-How-to-increase-fitness-of-alphas)
- [Weight Coverage common issues and advice](https://support.worldquantbrain.com/hc/en-us/articles/19248385997719-Weight-Coverage-common-issues-and-advice)
- [How to smooth the PnL curve to minimize sudden fluctuations](https://support.worldquantbrain.com/hc/en-us/articles/20251420634135-How-to-smooth-the-PnL-curve-to-minimize-sudden-fluctuations)
- [Using Test Period to improve OS robustness](https://support.worldquantbrain.com/hc/en-us/community/posts/22205077935895--BRAIN-TIPS-How-can-I-use-the-test-period-to-improve-the-OS-performance-of-my-Alpha)
- [Sequencing Multiple Operators](https://support.worldquantbrain.com/hc/en-us/community/posts/19344464221335--BRAIN-TIPS-Sequencing-Multiple-Operators-in-an-Expression)
- [Why linear combinations are discouraged](https://support.worldquantbrain.com/hc/en-us/community/posts/15238236356375--BRAIN-TIPS-Why-is-linear-combination-of-expressions-in-one-alpha-not-recommended-)
