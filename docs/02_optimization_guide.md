# WorldQuant BRAIN 优化篇

> 目标：把 `Sharpe / Fitness / Turnover / Correlation` 的问题拆开看，而不是遇到失败项就盲跑更多模板。

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

---

## 2. 先分清 IS、OS 和状态

官方语义里：

- `IS`：历史回测阶段，也就是你在 `Simulate` 时直接看到的结果
- `OS`：提交之后、随时间滚动形成的“真实世界”表现

几个最常见状态至少要分清：

- `IS-FAIL`
  连基础 Sharpe 门槛都没过，不进入 OS
- `OSTEST-PENDING`
  进入了 OS，但部分测试或统计还没完成
- `OSTEST-PASS`
  OS 测试通过
- `OSTEST-FAIL`
  OS 测试失败
- `OSTEST-DECM`
  官方说明这是已经失败且不再继续测试的状态

还要知道一件事：

- OS 页面出现 `N/A` 不一定是异常
- 很多统计项要等足够多交易日过去才会逐步填满

比如官方明确说，像 `Sharpe125` 这种字段要等 125 个交易日之后才会有值。

---

## 3. 当 `LOW_SHARPE` 出现时

优先怀疑：

- 信号本身信息量弱
- 市场/行业暴露过重
- 表达式过于尖锐
- 缺少平滑或标准化

优先尝试：

- `rank()` / `zscore()` 做标准化
- `group_rank()` / `group_neutralize()` 做分组稳健化
- `ts_decay_linear()` 做平滑
- 回到研究假设，看它是否真有经济含义

---

## 4. 当 `LOW_FITNESS` 出现时

不要把 `LOW_FITNESS` 当成独立问题。

永远先回到公式：

`Fitness = Sharpe * sqrt(abs(Returns) / max(Turnover, 0.125))`

然后拆成 3 个方向：

- `Sharpe` 太低？
- `Returns` 太低？
- `Turnover` 太高？

如果不先拆原因，继续跑更多模板通常只会增加噪声。

这里最好再记住官方的一个优化顺序：

1. 先让 `Sharpe` 过基础线
2. 再控制过高 `Turnover`
3. 最后再追求更高 `Returns`

因为：

- `Sharpe` 太差时，`Returns` 再高也很难稳
- `Turnover` 太高时，`Fitness` 会受到公式分母惩罚，实际交易成本压力也更大

---

## 5. 当 `HIGH_TURNOVER` 出现时

官方常见建议包括：

- 增大 `Decay`
- 使用 `trade_when`
- 使用 `rank()`
- 让信号变化更平滑

实战里要有两个直觉：

- 高频跳变通常要先平滑
- 不是所有高 Turnover 都该靠缩窗口解决

很多时候更有效的是：

- `Decay`
- `trade_when`
- `ts_backfill`
- 更稳定的截面整形

还要额外理解一点：

- `trade_when` 不只是“高换手补丁”
- 它本身就是一类适合事件驱动和低换手 alpha 的结构

如果一条 Alpha 的问题主要就是：

- 信号只在少数时点有效
- 非事件期频繁乱跳

那优先考虑事件化和延持，通常比继续揉窗口更合理。

如果再往前走一步，可以把 `trade_when` 分成三类用法来理解：

1. 事件触发后开仓
2. 非事件期保持旧值
3. 配合 `hump` 或其他阈值逻辑，直接把换手控制写进结构

这比把它理解成“简单降换手开关”更接近官方社区里的用法。

还可以继续区分几种工具的职责：

- `hump / hump_decay`：过滤幅度很小的日常抖动
- `ts_decay_linear / ts_decay_exp_window`：平滑持续变化的信号
- `days_from_last_change`：识别快速衰减或长时间未更新的字段
- `trade_when` 的退出条件：在止损、事件结束或信号失效时主动退出，而不是无限延持

如果高换手主要来自低流动性股票，不要只给全 Universe 增加同一个 Decay。
更合理的是用 `cap` 或平均成交量划分流动性层，并给低流动性组更长的持有周期。

---

## 5.5 D0 Alpha 应该单独研究

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

---

## 6. 当相关性问题出现时

### 6.1 `SELF_CORRELATION`

说明你现在这条 Alpha 和你自己已有 Alpha 太像。

### 6.2 `PROD_CORRELATION`

说明它和平台已有 Alpha 太像。

### 6.3 这类问题最容易被误处理

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

## 7. 当权重或集中度问题出现时

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

---

## 7.5 当 `LOW_SUB_UNIVERSE_SHARPE` 出现时

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

---

## 8. 交易成本要怎么理解

官方这里给了两个非常容易被忽略的点：

- 普通模拟结果展示的 Returns **不直接扣除** 真实交易成本
- `Turnover` 是判断交易成本压力的一个好 proxy
- 部分提交检查会另外计算 `after-cost Sharpe`

所以优化时不要误以为：

- 回测里的 Returns 已经自动扣掉了真实交易成本

更接近官方的理解是：

- Turnover 越高，真实交易成本压力通常越大
- 因此高 Turnover Alpha 要更谨慎地看待

---

## 9. 提升 Sharpe 的更合理方向

官方口径可以浓缩成两件事：

- 提高收益
- 降低波动

常见抓手：

- neutralization
- grouping operators
- 更好的标准化
- 更平滑的数据处理

换句话说，Sharpe 的提升通常不是靠“更花的表达式”，而是靠“更稳的结构”。

---

## 10. 提升 Fitness 的更合理顺序

经验顺序更推荐这样：

1. 先让 `Sharpe` 过基础线
2. 再看 `Turnover` 是否过高
3. 最后再追更高 `Returns`

原因是：

- Sharpe 太差时，Returns 再高也很难稳
- Turnover 太高时，Fitness 容易被交易成本和惩罚拖垮

---

## 11. 提升 Returns 时要保持克制

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

---

## 11.5 `Robust universe` 应该怎么直觉理解

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

## 11.6 最不流动 50% 的 after-cost 检查

官网说明里还有一项容易遗漏的提交检查：

- 平台会看原 Universe 中最不流动的 50% 股票
- 计算该部分的 after-cost Sharpe
- 其表现需要达到原 Universe after-cost Sharpe 的一定比例；官方示例约为 `52.5%`

失败时不应该简单删除低流动性股票。优先考虑：

- 按流动性设置不同的 Decay
- 使用 `cap`、平均成交量等构造流动性分组
- 用 `group_neutralize()` 降低 size / liquidity 风险暴露
- 在有明确风险向量时使用 `vector_neut()`

## 11.7 一套可执行的抗过拟合测试

官方社区明确建议把 disciplined research 放在“找到最高 IS 数字”之前。
进入最终候选池前至少做：

1. Rank test：把最终 Alpha 转成 rank，检查相对排序是否仍有效
2. Binary test：只保留 `-1/+1` 方向，检查是否过度依赖精确幅度
3. Sub/Super Universe test：检查不同股票池下是否仍成立
4. Train/Test：研发阶段不查看 Test 结果，最后一次性验证
5. 参数稳定性：自然窗口附近不应只剩一个孤立最优点
6. 因子暴露检查：避免表现主要来自波动率、规模或常见风格因子

几个很实用的官方社区经验：

- 不要总选数字最高的参数，稳定的次优点通常更可信
- `4` 天和 `6` 天都可用时，可以选 `5`，或简单平均两个版本
- 不要为了通过某项测试反向拟合该测试
- 不要陷入“IS 表现越优秀越好”的陷阱，重点是表现能否保持

---

## 12. PnL 曲线突然跳变时先查什么

官方给出的常见原因有 3 类：

1. `NaN` 和非 `NaN` 频繁切换
2. Alpha 值本身变化过快
3. 单只股票权重过高

因此常见修法也比较明确：

- 用 `backfill` 减少 NaN 跳变
- 用 `decay` 或平均化处理做平滑
- 用更严格的 `truncation` 控制单股权重

这一块很实用，因为它把“PnL 不平滑”从抽象问题变成了可检查的结构问题。

---

## 13. 降低 Turnover 的一组工具

可以把下面这组东西当成“稳健化工具组”：

- `Decay`
- `trade_when`
- `hump / hump_decay`
- `ts_decay_linear / ts_decay_exp_window`
- `rank()`
- `ts_backfill`

把它们放在一起理解，比孤立看任何一个都更有效。

`Truncation` 主要控制单股权重和集中度，不应被当作首要降换手工具。

---

## 14. ISLadder 应该怎么理解

官方把它描述为一种显著性检验思路：

- 用来降低“随机噪声看起来像有效 Alpha”的假阳性

实战上最重要的理解不是它的统计细节，而是：

- 有些 Alpha 看上去回测不错
- 但未必真的显著
- Ladder 一类测试就是在拦这种“像信号但可能只是噪声”的结果

所以别把 Ladder 失败简单理解成“平台太苛刻”，它本质上是在做反噪声筛查。

---

## 15. 优化时最容易犯的错

- 把“多跑”当优化
- 把“调参数”当研究
- 把“收益高”当“质量高”
- 在同一模板族里做过密近邻搜索
- 不分 `Simulate` 和 `Check submission`

---

## 16. 优化阶段最该记住的几句话

- 先分清 IS 和 OS
- 先拆原因，再做动作
- 先改结构，再调参数
- 相关性优先靠结构替换解决
- Fitness 先回公式，不要当黑盒
- 模板数量不是研究质量

---

## 17. 官方来源

- [Understanding Data in BRAIN: Key Concepts and Tips](https://platform.worldquantbrain.com/learn/documentation/understanding-data/data)
- [How to use the Data Explorer](https://platform.worldquantbrain.com/learn/documentation/understanding-data/how-use-data-explorer)
- [Must-read posts: How to improve your Alphas](https://platform.worldquantbrain.com/learn/documentation/advanced-topics/list-must-read-posts-how-improve-your-alphas-are-submitted)
- [Neutralization](https://platform.worldquantbrain.com/learn/documentation/advanced-topics/neut-cons)
- [D0](https://platform.worldquantbrain.com/learn/documentation/advanced-topics/getting-started-d0)
- [How can you avoid overfitting?](https://support.worldquantbrain.com/hc/en-us/community/posts/8209806533015-How-can-you-avoid-overfitting-)
- [Most illiquid 50% instruments after-cost test](https://support.worldquantbrain.com/hc/en-us/articles/19083525654551-Error-message-Most-illiquid-50-instruments-after-cost-Sharpe-is-above-cutoff-of-original-universe)
- [Alpha better suited for Delay 1](https://support.worldquantbrain.com/hc/en-us/articles/19083452017559-Error-Message-Alpha-better-suited-for-Delay-1)
