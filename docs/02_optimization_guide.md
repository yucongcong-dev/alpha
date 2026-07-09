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

---

## 8. 交易成本要怎么理解

官方这里给了两个非常容易被忽略的点：

- 模拟结果本身 **不直接包含** 交易成本
- `Turnover` 是判断交易成本压力的一个好 proxy

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
- `rank()`
- `ts_backfill`
- `Truncation`

把它们放在一起理解，比孤立看任何一个都更有效。

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
