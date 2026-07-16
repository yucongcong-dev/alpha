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

`Delay` 的含义是“交易日延迟天数”。

最常见的两种：

- `Delay=1`
  开盘前交易，只能使用前一交易日数据
- `Delay=0`
  收盘前交易，可以使用当日数据

需要特别注意：

- 它不是只有 `0/1` 的二值开关
- 但实操里最常见、最重要的仍然是 `0` 和 `1`

### 5.2 Decay

可以把 `Decay` 理解成“平滑旋钮”。

- 更高的 Decay：更平滑，通常换手更低，但更滞后
- 更低的 Decay：更敏感，通常更激进，但换手更高

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

### 5.4 Truncation

它的本质不是格式设置，而是组合风险控制。

- 更严格：更分散，更稳
- 更宽松：更容易放大信号，也更容易集中

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

官方把 Universe 定义为“市场中最具流动性的一篮子股票”。

可以先这样理解：

- `TOP500`：最液态的 500 只
- `TOP1000`：最液态的 1000 只
- `TOP2000`：最液态的 2000 只
- `TOP3000`：最液态的 3000 只

而且它们是包含关系：

- `TOP500` 是 `TOP1000` 的子集
- `TOP1000` 是 `TOP2000` 的子集

这意味着 Universe 不只是“股票数量设置”，它本身也在改变策略面对的流动性环境。

### 5.6 Test Period

`Test Period` 可以理解为：

- 在同一段 5 年 IS 内
- 再额外切出一段尾部区间
- 用来做 Train/Test 视角的验证

官方强调的关键点是：

- 它主要影响统计和图表展示
- 不会把提交检查改成“只看 Test 段”
- 平台的 submission tests 仍然跑完整 5 年 IS

所以更实用的理解是：

- `Test Period` 是防止过拟合的研究辅助工具
- 不是提交门槛的“切换开关”

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

---

## 7. Alpha 值怎样变成最终持仓

官方给出的顺序可以简化成：

1. 先用表达式为每只股票生成 Alpha value
2. 再按设置应用 `neutralization`、`decay` 等处理
3. 最后把这些结果按 `booksize` 缩放成组合资金分配

所以表达式输出不是“最后的美元仓位”，而是仓位分配的起点。

这里还要补一个官方口径：

- 平台使用固定 `booksize = $20 million`
- 模拟利润不会自动复投
- 模拟亏损会被现金注入补回

这意味着：

- PnL、回撤、资金分配都是在统一固定资金底座上计算
- 不要把它想成“策略赚了以后下一天本金自动变大”

这也是为什么：

- 原始表达式值的分布
- 是否有极端值
- 是否有大量 NaN

都会直接影响最终权重结构。

---

## 8. NaN 和 0 不是一回事

官方这里讲得很重要：

- `NaN`：表示这个股票不持仓
- `0`：不是“不持仓”，因为经过 `decay`、`neutralization` 等处理后仍可能变成非零

因此在 BRAIN 里：

- `Alpha = NaN`
  和
- `Alpha = 0`

绝对不能混为一谈。

这是很多新手第一次设计表达式时最容易忽略的底层语义。

### 8.1 `NaNHandling` 和手动缺失值处理

平台设置中的 `NaNHandling` 与表达式里的 `ts_backfill / is_nan` 不是一回事：

- `OFF`：保留 NaN，由表达式显式处理；这是平台默认值
- `ON`：平台按算子类型自动处理部分 NaN

开启后可能出现：

- 时间序列窗口全部是 NaN 时返回 `0`
- 某些 Group 算子在单只股票输入为 NaN 时返回组统计值

这样可以增加 Coverage，但会把“没有数据”和“真实值为 0”混在一起。因此本仓库
默认使用 `OFF`，需要补值时优先写出明确的业务逻辑：

```text
is_nan(primary_signal) ? fallback_signal : primary_signal
```

Arithmetic 算子的 `filter=true` 又是第三种行为：它只在该次加减乘运算中把 NaN
当作 `0`，不会改变全局 `NaNHandling`。

---

## 9. Pasteurize 到底在做什么

官方给了两个关键作用：

1. 把 `INF` 变成 `NaN`
2. 把不在当前 Universe 里的 instrument 也设成 `NaN`

所以它不只是“修异常值”，还会影响 Universe 边界和 group operator 的输入集合。

对实战最有用的理解是：

- 当你的表达式可能出现极端值或非法值时，`pasteurize` 是安全阀
- 当你在用 group operators 时，它也能帮助避免 Universe 外股票混进计算

再补一个很实用的直觉：

- `pasteurize` 不只是清洗脏值
- 它也会改变“哪些股票还能继续参与后续运算”

所以当你发现：

- 开启 `pasteurize` 后
- coverage、group 输入集合、甚至最终权重结构都有变化

这不是异常，而是它的正常语义。

### 9.1 `Unit Handling`

`Unit Handling=VERIFY` 会在不兼容量纲参与算术运算时给出警告，例如：

```text
close + adv20
```

这里一个是价格，一个是成交股数。该警告本身不会阻止提交，但通常说明表达式
缺少经济解释。如果确实只想组合相对位置，可以先分别标准化：

```text
rank(close) + rank(adv20)
```

不要为了消除警告机械地加 `rank()`；先确认两个量纲为什么应该被组合。

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
