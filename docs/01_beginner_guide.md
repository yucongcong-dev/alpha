# WorldQuant BRAIN 入门篇

> 目标：先建立对平台、指标、设置和基本表达式的正确直觉。

---

## 1. 先理解 Alpha 是什么

官方把 `Alpha` 定义为一种“预测未来价格变动的数学模型”。

这意味着：

- 字段不是 Alpha
- 算子不是 Alpha
- 单个公式只有在能稳定生成交易信号时，才算有研究价值

对本仓库来说，真正要优化的不是“公式字符串”，而是：

- 有没有信息量
- 能不能稳定
- 能不能通过平台检查
- 是否足够独特

---

## 2. 平台主流程

最少先分清三步：

1. `Simulate`
   看历史仿真结果，判断有没有基本质量。
2. `Check submission / OS checks`
   检查是否满足提交条件，包括性能和相关性。
3. `Submit`
   进入正式提交路径，不是简单保存。

所以“跑出结果”不等于“这条 Alpha 值得提交”。

如果把官方时间语义补完整，更准确的生命周期其实是：

1. `Simulate`
   看到的是 5 年 `IS` 回测结果。
2. `Check submission`
   平台先看这条 Alpha 是否达到提交门槛。
3. `Submit`
   只有真正提交，才会进入后续样本外跟踪。
4. `Semi-OS`
   这是 `IS` 结束到你实际提交之间的一段过渡区间。
5. `OS`
   这是提交之后继续滚动积累出来的表现。

这条链路对本仓库特别重要，因为：

- 本地大部分探索都停在 `Simulate` 和 `Check submission`
- 真正决定“能不能长期留下来”的，还要看后续相关性和 OS 表现

### 2.1 官网 Starter Pack 和 10 Steps 的学习顺序

官网新手材料不是让你一开始就堆公式，而是按下面顺序建立直觉：

1. 先知道 BRAIN 是一个历史回测工具，输入表达式，输出一组每日持仓和 PnL
2. 再理解 Alpha 是把 price-volume、fundamental、news、sentiment 等数据转成股票权重
3. 然后学会区分 long、short、volume、open/close price、PnL、Return 等基础金融词
4. 最后才进入 Fast Expression、operator、data field 和 simulation settings

对本仓库来说，这个顺序可以压成一句话：

- 先解释假设，再写表达式；先理解字段，再调模板。

如果你还不能用自然语言说清楚“这条表达式为什么应该预测收益”，通常不该进入大规模
broad search。

---

## 3. 新手先会看结果

先盯住 4 个指标：

- `Sharpe`
- `Fitness`
- `Turnover`
- `Drawdown`

可以先这么理解：

- `Sharpe`：稳定不稳定
- `Fitness`：综合质量
- `Turnover`：交易频率和成本压力
- `Drawdown`：回撤风险

新手最常见误区是只看 `Returns`。  
官方并不鼓励这种看法，因为高收益但高波动的 Alpha 往往并不好。

---

## 4. 最重要的一个公式

官方公式：

`Fitness = Sharpe * sqrt(abs(Returns) / max(Turnover, 0.125))`

这条公式有两个很重要的结论：

- 想提升 Fitness，核心杠杆只有 `Sharpe`、`Returns`、`Turnover`
- 当 Turnover 已经很低时，再继续压它，收益会越来越小

所以很多时候：

- 继续降低 Turnover
  不如
- 回头提高信号质量，拉高 Sharpe

---

## 5. 常用设置先建立直觉

### 5.1 Delay

`Delay` 的含义是“数据进入可实现持仓之前相隔的交易日数”。

最常见的两种：

- `Delay=1`
  - 第 `t` 日可用的数据决定第 `t+1` 日实现的持仓
  - 等价地说，今天交易只能使用前一交易日已经可用的数据
- `Delay=0`
  - 第 `t` 日数据可以决定第 `t` 日实现的持仓
  - 平台假设在收盘前完成相应交易

需要特别注意：

- 平台会按 simulation setting 自动应用 Delay；不要因为设置了 `Delay=1` 就机械地再包一层 `ts_delay(x, 1)`
- `ts_delay` 是表达式中的研究算子，额外加入会真的改变信号时间结构
- Delay 不是只有 `0/1` 的语法开关，但实操里最常见、最重要的仍然是 `0` 和 `1`

### 5.2 Decay

可以把 simulation setting 里的 `Decay` 理解成“组合层平滑旋钮”。

- 更高的 Decay：更平滑，通常换手更低，但更滞后
- 更低的 Decay：更敏感，通常更激进，但换手更高

它和表达式里的 `ts_decay_linear(x, d)` 不是同一个位置：

- `Decay` setting：平台在表达式输出之后应用的组合层处理
- `ts_decay_linear(...)`：表达式内部显式构造的时间序列信号

两者同时使用会形成双重平滑。除非 A/B 对照证明有必要，不要因为“平滑能降换手”就默认叠加。

### 5.3 Neutralization

这是最重要的稳健化开关之一。

直觉理解：

- 不做 neutralization：更容易带上市场/行业方向暴露
- 做 neutralization：更像是在同类股票里做强弱比较

这里最容易混淆的一点是：

- `neutralization` 设置
- `group_neutralize(...)` 算子

它们不是一回事。

可以先这样记：

- `group_neutralize(...)`
  - 是表达式内部自己显式做组内相对化
- `neutralization` 设置
  - 是平台在组合层面对整条 Alpha 再做一层中性化

所以很多时候：

- 先用 `group_neutralize(...)` 决定信号结构
- 再由 `neutralization` 设置决定最终组合暴露

> `neutralization` 设置与 `group_neutralize(...)` 算子的完整区分和实际选择见
> [03 的 Neutralization 最终决策](03_optimization_and_submission.md)和
> [04 的 Neutralization 页面语义](04_platform_reference.md)。

### 5.4 Truncation

它的本质不是格式设置，而是组合风险控制。

- 更严格：更分散，更稳
- 更宽松：更容易放大信号，也更容易集中
- 官方入门材料给出的常用建议区间是 `0.05–0.10`；它是起点，不是所有 Region、Universe 和 Alpha 类型的永久最优值

这里也要分清两个东西：

- `truncate(...)` 算子
- `truncation` 设置

更实用的理解是：

- `truncate(...)`
  - 更像表达式内部主动裁极值
- `truncation` 设置
  - 更像平台在最终组合权重层做上限控制

所以如果你的问题是：

- 原始信号本身极端值太尖

更该先想：

- `rank`
- `zscore`
- `scale`
- `truncate(...)`

如果你的问题是：

- 最终组合权重太集中

更该先想：

- 更严格的 `truncation`

### 5.5 Universe

Universe 是按流动性划分的可投资股票集合；`TOP500`、`TOP1000`、`TOP2000`、`TOP3000`
不仅数量不同，也代表不同的流动性环境。精确定义见
[04 的 Universe 词典](04_platform_reference.md#71-universe)；D0/D1 的选择见
[03 的 D0 研究章节](03_optimization_and_submission.md#6-d0-alpha-应该单独研究)。

### 5.6 Test Period

`Test Period` 是 5 年 IS 内的 Train/Test 验证工具，用于观察候选是否过拟合；它不会把
submission tests 改成只看 Test 段。完整时间边界见
[04 的 Test Period 词典](04_platform_reference.md#25-test-period)。

---

## 6. 新手最该先掌握的算子

建议优先掌握这 8 个：

- `rank`
- `ts_rank`
- `ts_zscore`
- `ts_delta`
- `ts_decay_linear`
- `group_rank`
- `group_neutralize`
- `trade_when`

它们基本覆盖：

- 截面排序
- 时序比较
- 分组比较
- 交易频率控制

### 6.1 Fast Expression 的最小语法

Fast Expression 支持用变量拆分复杂表达式，每条中间语句以分号结束，最后一条
表达式作为最终 Alpha 输出：

```text
raw = ts_backfill(cashflow_op, 120);
stable = winsorize(raw, std=4);
group_rank(ts_zscore(stable / cap, 252), industry)
```

还可以用 `/* ... */` 写块注释。需要注意：

- 最后一条语句不需要分号
- 中间变量只是提高可读性，不是新的数据字段
- Fast Expression 没有类、对象、指针或自定义函数
- 多行写法不会自动改善 Alpha，仍要保证每个算子都有明确作用

官网 Expression Language 的关键不是“语法很像代码”，而是它始终在做两层变换：

- 时间维度：每只股票自己和自己的历史比较，例如 `ts_rank / ts_zscore / ts_delta`
- 截面维度：同一天不同股票之间比较，例如 `rank / group_rank / zscore`

看一条表达式时，先问它每一步是在做“历史比较”还是“横截面比较”。这比死记单个算子更重要。

### 6.2 算子顺序和 backfill 窗口不要望文生义

下面两条表达式控制的对象不同：

```text
winsorize(x, std=4) / y
winsorize(x / y, std=4)
```

- 第一条只限制分子 `x` 的极端值，除数 `y` 很小造成的极端比率仍可能保留
- 第二条限制最终比率的极端值；“ratio 后 winsorize”指的就是这种实验顺序
- 两者没有脱离数据分布的通用优劣，应当一次只改一个顺序做 A/B 对照

`ts_backfill(x, 252)` 中的 `252` 是“向前搜索最近有效值的最大 lookback”，不是把 `x` 截断或 cap 在 `252`：

- 如果最近就有有效值，函数直接使用它
- 如果 `x` 本来几乎没有缺失，把 `504` 改成 `252` 可能完全不改变结果
- 所以修改 backfill 窗口前，应先确认字段的缺失和更新频率

---

## 7. Alpha 值怎样变成最终持仓

表达式先为每只股票生成 Alpha value，平台再应用 neutralization、decay 等设置，最后按
booksize 缩放为组合资金分配。因此表达式输出是持仓计算的起点，不是最终美元仓位。

平台使用固定 `booksize = $20 million`：模拟利润不自动复投，亏损会由现金补回。
这保证不同 Alpha 在统一资金口径下比较；完整页面定义见
[04 的 Universe、Weight、Booksize 词典](04_platform_reference.md)。

---

## 8. NaN 和 0 不是一回事

- `NaN` 表示该股票没有仓位。
- `0` 是原始 Alpha value 为零，经过 decay 或 neutralization 后仍可能变成非零。

所以不要用 `0` 机械替代缺失数据，否则会改变持仓和覆盖语义。

### 8.1 `NaNHandling`

本仓库默认使用 `NaNHandling=OFF`，让缺失处理通过 `ts_backfill()`、`is_nan()` 或有业务
含义的 fallback 显式表达。开启自动处理可能提高 Coverage，也可能混淆真实零值与补值结果。

完整边界见 [04 的 NaN 与 Pasteurize 词典](04_platform_reference.md)。

---

## 9. Pasteurize 与 Unit Handling

`Pasteurize` 会处理非法值和 Universe 外的 instrument，因此可能改变 group operator 的输入
集合与 Coverage；精确行为统一查 [04 的 Pasteurize 词典](04_platform_reference.md#84-pasteurize)。

`Unit Handling=VERIFY` 用于发现不兼容量纲的算术组合，例如：

```text
close + adv20
```

单位警告通常说明表达式缺少经济解释，但不会单独阻止提交。若研究的是相对位置，可以在有
明确假设时分别标准化：

```text
rank(close) + rank(adv20)
```

不要为了消除警告机械加 `rank()`。完整定义见
[04 的 NaN 与 Pasteurize 词典](04_platform_reference.md)。

---

## 10. 看表达式时要问自己的 4 个问题

1. 这个信号到底在比较什么？
2. 它是截面逻辑，还是时序逻辑？
3. 它有没有平滑？
4. 它有没有控制行业或风格暴露？

例如：

- `rank(field)`：纯截面排序
- `ts_rank(field, 60)`：当前值和过去 60 天比
- `group_rank(field, subindustry)`：只跟同组股票比
- `ts_decay_linear(expr, 20)`：对输出做平滑

---

## 11. 官方更鼓励什么样的改进

官方更鼓励：

- 把裸值改成比率
- 把原始值改成排序或标准化
- 换合理窗口
- 换 grouping / neutralization
- 改缺失值处理

官方不鼓励把主要精力放在：

- `20 -> 22`
- `60 -> 63`

这种近邻微调上。

---

## 12. 标准窗口直觉

官方最常见窗口大致是：

- `20`：1 个月
- `60`：1 个季度
- `120`：半年
- `250/252`：1 年

这套窗口的意义不是“绝对最优”，而是：

- 简单
- 好解释
- 不容易过拟合

---

## 13. 入门阶段最该记住的几句话

- 先会看 `Sharpe / Fitness / Turnover / Drawdown`
- 先分清 `NaN` 和 `0`
- 先知道 Universe 会改变流动性环境
- 先理解设置，再调参数
- 先理解结构，再扩模板
- 先让 Alpha 有质量，再考虑更高收益
- 不要把高 Returns 误当成高质量
- 官网课程和 Starter Pack 适合建立地图；真正研究时仍要回到假设、字段和失败项
