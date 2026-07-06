# WorldQuant BRAIN 平台知识手册

> 整理自 WorldQuant Brain 官方 API 文档（FAQ/Tutorial/Operators），供量化 Alpha 探索参考。
> 数据来源：`api.worldquantbrain.com/faqs`、`api.worldquantbrain.com/tutorial-pages`、`api.worldquantbrain.com/operators`

---

## 一、核心性能指标

> **官方 Tutorial 来源** (`parameters-simulation-results`)

| 指标 | 定义 | 平台检查 |
|------|------|----------|
| **Sharpe** | `sqrt(252) × IR ≈ 15.8 × IR`；其中 `IR = mean(PnL) / stdev(PnL)` | `LOW_SHARPE` 低于截止值失败；另有 `LOW_2Y_SHARPE` 单独检查 |
| **Fitness** | `Sharpe × sqrt(abs(Returns) / max(Turnover, 0.125))` | `LOW_FITNESS` 低于截止值失败；高 Fitness = 高 Sharpe + 低 Turnover |
| **Turnover** | 交易金额 / 持仓金额 | 双向：`LOW_TURNOVER`（过低）和 `HIGH_TURNOVER`（过高） |
| **Returns** | `annualized PnL / (0.5 × booksize)` | `LOW_RETURNS` 三级：FAIL / WARNING / PASS |
| **IR** | `mean(PnL) / stdev(PnL)`（信息比率） | Sharpe 的日频版本 |
| **Margin** | PnL / 总交易金额 | 每交易美元的平均损益 |
| **Drawdown** | 回撤 | 标准指标 |

> **官方提示**: High Sharpe (or IR) is more desirable than just high return. Improving one factor normally has an adverse impact on the other factor. An improvement in fitness is an indication that your changes are having a positive impact.

---

## 二、模拟设置参考

| 设置 | 默认值 | 选项 | 说明 |
|------|--------|------|------|
| **Delay** | 1 | 0, 1, 2, 3... | Delay=1 用昨日数据上午交易；Delay=0 用当日数据晚间交易 |
| **Decay** | 4 | 0, 4, 6, 8, 10... | 过去 N 天线性递减加权平均；0=无衰减 |
| **Neutralization** | SUBINDUSTRY | SUBINDUSTRY, MARKET, SECTOR, INDUSTRY, NONE | 调整权重使每组内总和为零 |
| **Truncation** | 0.08 | 0.0~1.0 | 每个工具最大日权重 |
| **Pasteurization** | ON | ON / OFF | 不在 universe 中的工具输入值替换为 NaN |
| **NaN Handling** | OFF | ON / OFF | 允许聚合算子在输入为 NaN 时输出数值 |
| **Unit Handling** | VERIFY | VERIFY / OFF | 不兼容单位时发出警告 |
| **Universe** | TOP3000 | TOP3000, TOP2000, TOP1000, TOP500, ALL | 基于流动性的区域子集 |
| **Region** | USA | USA, CHN, JPN, EUR, GBR... | 地区 |
| **Language** | FASTEXPR | FASTEXPR, EXPRESSION, PYTHON | 表达式语言 |

---

## 三、提交检查规则（完整列表）

### 3.1 核心检查

| 检查项 | 含义 | 常见修复 |
|--------|------|----------|
| `LOW_FITNESS` | Fitness 低于截止值 | 提升信号质量、降低 Turnover |
| `LOW_SHARPE` | Sharpe 低于截止值 | 改进信号逻辑、调整 Neutralization |
| `LOW_RETURNS` | 收益率不足 | 同上 |
| `LOW_TURNOVER` | 换手率过低 | 使用 `trade_when`、避免纯截面操作 |
| `HIGH_TURNOVER` | 换手率过高 | 使用 `rank()`/`ts_decay_linear` 平滑 |
| `CONCENTRATED_WEIGHT` | 权重过于集中 | 添加 Neutralization、使用 `rank()` 标准化 |
| `IMBALANCE` | 不平衡超限 | 检查 Neutralization 设置 |

### 3.2 相关性检查

| 检查项 | 含义 | 常见修复 |
|--------|------|----------|
| `SELF_CORRELATION` | 与自己已提交 Alpha 相关性过高 | 除非 Sharpe 提升 ≥10%，否则需降低相关性 |
| `PROD_CORRELATION` | 与全平台 Alpha 相关性过高 | 使用新颖想法、尝试未用过的算子、换数据集 |

### 3.3 稳健性检查

| 检查项 | 含义 |
|--------|------|
| `SUB_UNIVERSE_SHARPE` | 子宇宙 Sharpe 不足 |
| `LOW_ROBUST_UNIVERSE_SHARPE/RETURNS` | 稳健宇宙指标不足 |
| `IS_LADDER_SHARPE` | IS 阶梯 Sharpe 不足 |
| `LOW_2Y_SHARPE` | 2 年 Sharpe 不足 |
| `LOW_DURATION` | 模拟期过短 |
| `LOW_COVERAGE` | 零覆盖期过长 |

### 3.4 其他检查

| 检查项 | 含义 |
|--------|------|
| `NEUTRALIZATION` | Universe 与 Neutralization 不兼容 |
| `D0_SUBMISSION` | D0 提交达到配额（限 5 个） |
| `RISK_PRECISE` | Risk 中性化必须为 "Precise" |

### 3.5 高换手率专项检查（HT_ 系列）

包含扣费后 Sharpe、流动性 TOP200/TOPDIV3000 Sharpe、正交中性化等 12 项检查。

---

## 四、模拟提示精华

> 来源：官方 FAQ + Tutorial + 平台提示

### 4.1 Turnover 优化

- 提交较低 Turnover 的 Alpha
- 使用 `trade_when` 算子降低 Turnover
- 使用 `rank()` 降低非流动部分的 Turnover（以 adv20 为流动性代理）
- 使用 `ts_decay_linear` 获得合理 Margin
- **注意**: `hump`/`hump_decay`/`ts_decay_exp_window`/`vector_neut` 在 FASTEXPR 模式下不可用，会导致模拟失败
- > **官方 FAQ 来源** (`turnover-reduction-methods`): 高 Sharpe 但高 Turnover 的 Alpha，应使用 `ts_decay_linear`、`trade_when`、`rank()` 等方法降低 Turnover

### 4.2 参数选择

- **参数搜索限制在简单合理值：5, 20, 60, 120, 252（天数）**，而非 37, 14 等
- **专注改进想法，而非拟合参数** — 不要靠添加参数/因子/回归元素
- 新颖想法降低相关性，尝试未用过的算子和设置
- > **官方 FAQ 来源** (`debt-liabilities-past-value`): "You could use ts_delay(fundamental data, 60) to get last quarter's value since we could have 20 as work day for one month." / "You could keep simple parameter like 20/60/250 to save your time rather than fit for parameter like 20 to 22."

### 4.3 Neutralization

- 实验不同 Neutralization 设置（Country 和 Sector 通常都有效）
- 使用 `bucket()` 算子进行自定义组 Neutralization
- 使用 `group_neutralize()` 中性化指定分组
- > **官方 FAQ 来源** (`neutralization-reduces-standard-deviation-of-return`): Neutralization 不一定总是降低收益标准差，取决于 Alpha 逻辑
- > **官方 FAQ 来源** (`alpha-with-no-neutralization`): 不使用 Neutralization 也可以开发好的 Alpha，但通常需要 rank() 等截面标准化
- > **官方 FAQ 来源** (`difference-between-neutralization-groups`): SUBINDUSTRY 最细粒度，MARKET 最粗；选择取决于 Alpha 逻辑

### 4.4 信号构建

- 使用 `days_from_last_change()` 捕捉快速衰减信号
- 提交在 Sub-Universe 或 Super-Universe 中保留至少 70% Sharpe 的 Alpha
- > **官方 FAQ 来源** (`delay1-delay0-implication`): Delay=1 更保守稳定，Delay=0 利用当日数据但可能有前瞻偏差
- > **官方 FAQ 来源** (`delay-decay`): `ts_delay(close, 5)` = 5天前的收盘价；`ts_decay_linear(close, 5)` = 过去5天的线性加权均值
- > **官方 FAQ 来源** (`decay-usage`): 较短的 decay 通常导致较高 Turnover，较长的 decay 更稳定但信号更滞后

### 4.5 多样化

- 更大 Universe、不同 Region（特别是非美国）
- 不同 Delay（尝试 delay=0）
- 尝试高 Dataset Value Score 的数据集（Earnings/Macro/Insider）降低 Prod Correlation

### 4.6 提交策略

- 每天提交 4 个 Alpha + 1 个 SuperAlpha 提升 Quantity Factor
- 经验法则：5~10 个 Alpha 在 5+ 不同日期提交（单日最多 2,000 积分）

---

## 五、关键算子速查

### 5.1 平台推荐算子

| 算子 | 用途 | 示例 |
|------|------|------|
| `ts_decay_linear(expr, window)` | 线性衰减加权 | `ts_decay_linear(expr, 20)` |
| `days_from_last_change(expr)` | 距上次变化的天数 | `days_from_last_change(field)` |
| `trade_when(condition, expr, default)` | 条件交易 | `trade_when(volume > threshold, expr, -1)` |
| `bucket(expr, range)` | 自定义分桶 | `bucket(rank(cap), range='0.1, 1, 0.1')` |
| `rank(expr)` | 截面排名标准化 | `rank(expr)` |
| `group_rank(expr, group)` | 组内排名 | `group_rank(expr, subindustry)` |
| `group_neutralize(expr, group)` | 组内中性化 | `group_neutralize(expr, market)` |
| `ts_zscore(expr, window)` | 时序 Z-Score | `ts_zscore(field, 60)` |
| `ts_rank(expr, window)` | 时序排名 | `ts_rank(field, 60)` |
| `ts_quantile(expr, window)` | 时序分位数 | `ts_quantile(expr, 60)` |
| `normalize(expr, useStd, limit)` | 截面标准化 | `normalize(expr, useStd=true, limit=3.0)` |
| `ts_regression(y, x, window, rettype)` | 时序回归残差 | `ts_regression(field, market, 60, rettype=2)` |
| `adv20` | 20 日平均成交量（流动性代理） | `rank(expr / rank(adv20))` |

> **不可用算子**: `hump`（仅接受1个参数，2参数形式报错）、`hump_decay`（不存在）、`ts_decay_exp_window`（不存在）、`vector_neut`（不存在）。使用这些算子会导致模拟创建失败。

### 5.2 FASTEXPR 全部算子（66个）

> 来源：`api.worldquantbrain.com/operators?language=FASTEXPR`

| 类别 | 算子 |
|------|------|
| **算术** | add, sqrt |
| **时序统计** | ts_sum, ts_mean, ts_std_dev, ts_zscore, ts_rank, ts_quantile, ts_scale, ts_arg_min, ts_arg_max, ts_product, ts_av_diff, ts_delta, ts_delay, ts_step, ts_count_nans, ts_corr, ts_covariance, ts_regression, ts_decay_linear, ts_backfill, ts_std_dev |
| **截面操作** | rank, zscore, scale, normalize |
| **分组操作** | group_rank, group_neutralize, group_zscore |
| **条件/事件** | trade_when, days_from_last_change, bucket |
| **其他** | adv20, kth_element, ts_percentage, ts_entropy |

### 5.3 标准窗口参数

> **官方视频来源** (`how-to-avoid-overfitting`): "You can also use 20 days, which is a month or 60 days for a quarter, 120 for half a year, 250 for a year, and so on."
>
> **官方 FAQ 来源** (`debt-liabilities-past-value`): "You could use ts_delay(fundamental data, 60) to get last quarter's value since we could have 20 as work day for one month." / "You could keep simple parameter like 20/60/250 to save your time rather than fit for parameter like 20 to 22."
>
> **官方视频来源** (`group_neutralize-operator`): "60 days roughly represents the number of trading days in a quarter."
>
> **官方视频来源** (`simulation-results`): "The 252 parameter represents the estimated number of trading days in a year."
>
> **官方视频来源** (`sentiment-strength`): "254 days represent the number of trading days in a year."
>
> **官方 FAQ 来源** (`example-quarterly-statements`): "Quarterly data means the data is released approximately once a quarter. The consecutive releases are not exactly equal to a quarter of a year as the release dates are not fixed."

| 窗口 | 含义 | 官方推荐 | 官方来源 | 适用场景 |
|------|------|----------|----------|----------|
| 5 | 1 周 | - | - | 超短期信号、快速衰减 |
| 20 | 1 月 | ✅ | FAQ + Video | 短期信号、月度动量 |
| 60 | 1 季 | ✅ | FAQ + Video | 中期信号、季度趋势 |
| 120 | 半年 | ✅ | Video | 中长期信号 |
| 250 | 1 年 | ✅ | FAQ + Video | 长期信号、年度趋势 |
| 252 | 1 年(精确) | - | Video | Sharpe 年化因子（252交易日/年） |

> **注意**: 官方在不同场合使用了 250、252、254 作为"1年交易日数"。FAQ 推荐"简单参数 20/60/250"，视频说"252 = 一年交易日数"，另有视频用"254天"。实践中 252 是最常用的年化基准，250 是 FAQ 推荐的简单参数值。
>
> **官方 FAQ 来源** (`decay_overfit`): "Changing the decay from 1 to 5 is okay, but not say, changing it from 5 to 6. There is no 'exact' definition, but you should keep in mind that it is not over-fitting if it makes sense to you."
>
> **官方视频来源** (`how-to-avoid-overfitting`): 避免过拟合的核心原则——使用简单合理的参数值，不要拟合到非标准值。

---

## 六、常见失败模式与修复

| 失败检查 | 典型原因 | 修复方案 |
|----------|----------|----------|
| `LOW_SHARPE` | 信号质量差、缺乏经济学含义 | 改进信号逻辑、添加 group_neutralize |
| `LOW_FITNESS` | Sharpe 低或 Turnover 异常 | 同 LOW_SHARPE + 调整 Turnover |
| `LOW_TURNOVER` | 纯截面操作、无时序变化 | 添加 `trade_when`、使用时序算子 |
| `HIGH_TURNOVER` | 短窗口 delta、无平滑 | 使用 `rank()`/`ts_decay_linear` |
| `CONCENTRATED_WEIGHT` | 无中性化、裸除法 | 添加 `group_neutralize`/`rank()` |
| `SELF_CORRELATION` | 同族模板高度相关 | 减少同族变体、尝试不同算子组合 |
| `PROD_CORRELATION` | 与全平台 Alpha 高相关 | 使用新颖算子、换数据集/Region |
| `SUB_UNIVERSE_SHARPE` | 信号在子宇宙不稳定 | 添加 Neutralization、使用 `rank()` |

---

## 七、官方 Alpha 示例思路

> 来源：官方 Tutorial `19-alpha-examples`、`sample-alpha-concepts`

| 假设 | 实现方式 | 改进提示 |
|------|----------|----------|
| 公司经营收入高于过去1年历史 → 买入 | `ts_rank(operating_income, 252)` | 计算包含股价走势的比率可能改善信号 |
| 负债公允价值增加 → 做空 | `ts_delta(liabilities_fair_value, 252)` | 观察更短期间的变化可能提高准确性 |
| 高负债资产比（排除财务健康差的）→ 买入 | `liabilities / assets` | 考虑不同行业差异，尝试替代 Neutralization |
| 盈利收益率高频偏高 → 买入 | EPS/price 比率，用 `ts_rank` + `group_rank` | 使用 NaN Handling 预处理数据提升表现 |
| EV/CF 较低 → 公司相对便宜 | `ts_zscore` 标准化比率变化，`group_rank` 控制 Turnover | 尝试不同类型的现金流 |
| 分析师目标价与自由现金流高相关 → 信号已充分定价 | `ts_corr(est_ptp, est_fcf, 20)` | 1年窗口可能太长，尝试更短窗口 |
| 隐含波动率 > 历史波动率 → 看涨情绪 | IV 与 Parkinson 波动率比较 | 使用 `ts_backfill` 避免缺失数据 |

---

## 八、顾问资格

- 需 10,000 积分，通过提交满足阈值的 Alpha 获得
- 经验法则：5~10 个 Alpha 在 5+ 不同日期提交（单日最多 2,000 积分）
- 顾问可访问更多区域、数据字段、多模拟、SuperAlpha、Brain API

---

## 九、2026-07 官网补充学习笔记

> 本节基于我通过本地 Chrome 会话直接阅读的 WorldQuant BRAIN 官方文档与支持中心页面补充整理。
>
> 主要页面：
> - [Alpha Examples for Beginners](https://platform.worldquantbrain.com/learn/documentation/create-alphas/19-alpha-examples)
> - [Simulate your first Alpha](https://platform.worldquantbrain.com/learn/documentation/create-alphas/running-your-first-alpha)
> - [Click here for a list of terms and their definitions](https://support.worldquantbrain.com/hc/en-us/articles/4902349883927-Click-here-for-a-list-of-terms-and-their-definitions)
> - [How to increase fitness of alphas](https://support.worldquantbrain.com/hc/en-us/articles/20251386376471-How-to-increase-fitness-of-alphas)
> - [How to improve Sharpe?](https://support.worldquantbrain.com/hc/en-us/articles/20251383456663-How-to-improve-Sharpe)
> - [How to improve returns?](https://support.worldquantbrain.com/hc/en-us/articles/20251364149655-How-to-improve-returns)
> - [How to improve Turnover?](https://support.worldquantbrain.com/hc/en-us/articles/20251419309719-How-to-improve-Turnover)

### 9.1 官方对 Alpha 学习路径的强调

- 官方入门路径不是先“调参数”，而是先有一个可解释的假设，再把假设翻译成表达式。
- `Alpha Examples for Beginners` 的结构基本固定为：`Hypothesis -> Implementation -> Hint to improve`。
- 官方示例反复鼓励的改进方向不是暴力网格搜索，而是：
  - 改成比率而不是直接比值
  - 换更合理的观察窗口
  - 尝试更合适的 neutralization
  - 做更好的缺失值处理

### 9.2 官方对“好 Alpha”的最低共识

> 来源：`Simulate your first Alpha`

- PnL 曲线应持续增长，不能只有高收益但伴随很大波动。
- Turnover 要低，但不能低于 `1%`。
- Drawdown 应低于 `10%`。
- Delay 1 的 Sharpe 应高于 `1.25`；Delay 0 的 Sharpe 应高于 `2.0`。
- 官方特别强调：即使年化收益高，如果 PnL 波动很大，Alpha 仍不算“足够好”。

这点很重要，因为它解释了为什么很多看起来收益不错的表达式，最终仍会被平台标成 `Needs Improvement`。

### 9.3 官方指标口径

> 来源：术语表 + 支持文章

- `Fitness = Sharpe * sqrt(abs(Returns) / Max(Turnover, 0.125))`
- `Sharpe = IR * sqrt(252)`，其中 `IR = Avg(PnL) / Std_dev(PnL)`
- `Returns = Annualized PnL / Half of Book Size`
- `Turnover = Dollar trading volume / Booksize`
- `Margin = PnL / Total dollars traded`
- `Drawdown = 最大 PnL 峰谷回撤 / 半个 booksize`

对实战最有用的结论：

- 提高 Fitness 的三个杠杆只有三个：`提高 Sharpe`、`提高 Returns`、`降低 Turnover`。
- 但由于公式里对 Turnover 有 `Max(Turnover, 0.125)` 下限，Turnover 低于 `12.5%` 后，再继续压低对 Fitness 的帮助会明显变弱。
- 所以如果一个 Alpha 已经是低换手，再继续压 Turnover 往往不如直接提升 Sharpe 或 Returns。

### 9.4 官方对 Sharpe / Returns / Turnover 的建议

> 来源：`How to improve Sharpe?`、`How to improve returns?`、`How to improve Turnover?`

#### Sharpe

- 提高 Sharpe 的核心是两条：
  - 提高收益
  - 降低波动
- 官方明确建议可通过 `neutralization settings` 和 `grouping operators` 来降低波动。
- 官方也明确反对“为了提 Sharpe 而无意义微调参数”，要求表达式在数学和经济含义上都讲得通。

#### Returns

- 官方给的提高 Returns 方向包括：
  - 提高 Turnover
  - 使用更低的 Decay
  - 使用更小、更流动的 universe
  - 适度提高 Alpha 波动以换取更高收益
  - 尝试 news / analyst 类数据集

这说明：

- `Returns` 和 `Turnover` 往往是正相关的。
- 所以提高 Returns 很多时候会伤害 Fitness，需要结合公式一起判断，不能只盯收益。

#### Turnover

- 官方建议尽量把 Turnover 保持在 `40%` 以下，至少应低于 `70%`。
- 官方列出的常见降 Turnover 方法：
  - 使用 `Decay` 设置
  - 使用 `rank()`
  - 使用 `trade_when`
  - 使用 `hump`
  - 用更小的时间窗口
  - 使用更新更频繁的数据类别

这里有一个需要带着脑子读的地方：

- 文中同时出现了“用 Decay 降 Turnover”和“用更低的 Decay 值”两种说法。
- 结合平台通常行为，更可信的理解是：
  - **更高的 decay 更容易压低 turnover**
  - **更低的 decay 更容易提高 returns**

所以实战里应把 `decay` 当成 `returns <-> turnover` 的平衡旋钮，而不是单向万能开关。

### 9.5 官方对相关性与提交的说明

> 来源：术语表 + `Simulate your first Alpha`

- `Submit` 按钮会启动 OS 测试，而不是简单“存档”。
- 提交前平台会先检查性能阈值与相关性阈值。
- `SELF_CORRELATION`：
  - 比较的是你当前 Alpha 与你自己已提交 Alpha 的最大 Pearson 相关性。
  - 如果一组 Alpha 高度相关，通常只会让其中一个通过。
- `PROD_CORRELATION`：
  - 比较的是与全平台已提交 Alpha 的相关性。
- 官方对 `Correlation` 的定位非常明确：它衡量的是 Alpha 的**独特性**，不是收益高低。

这也解释了为什么“同一想法的小修小补”很容易卡在提交阶段，即使 IS 看起来不错。

### 9.6 官方对仿真设置的直接启发

> 来源：`Simulate your first Alpha` 与术语表

- Neutralization 是官方最常提的稳健化手段之一。
- Pasteurization = `On` 时，Universe 外的输入会被转成 NaN。
- 平台用 Alpha 生成每天的股票权重向量，再根据 neutralization 设置决定是否对 `market / industry / subindustry / none` 做中性化。
- Booksize 在平台中固定为 `$20 million`，因此很多收益率、回撤、margin 的定义都围绕这个常数展开。

### 9.7 对后续学习最值得记住的几句话

- 官方更重视“有逻辑的改进”，而不是“把参数从 20 调到 22”。
- 先让 Alpha 过最小质量线，再追求更高收益；不要为了某个指标单独过拟合。
- `neutralization`、`group operators`、`rank()`、`trade_when`、`decay` 是官方最常反复提到的实战杠杆。
- 当 Fitness 不够时，永远先回到公式：到底是 `Sharpe` 不够、`Returns` 不够，还是 `Turnover` 太高。

### 9.8 对本仓库使用者的直接映射

把这些官网知识映射到本仓库，最实用的操作习惯是：

- 先用模板生成“有解释的表达式”，不要一开始就做无约束广搜。
- 在本地结果里先看 `Sharpe / Fitness / Turnover / Drawdown` 的组合，不要只看 `Returns`。
- 当 `Fitness < 1` 时，优先按公式拆原因，而不是盲目新增更多模板。
- 当 `SELF_CORRELATION` 或 `PROD_CORRELATION` 成为主失败原因时，应该换想法或换结构，而不是只调窗口。
