# WorldQuant BRAIN 平台知识手册

> 整理自 WorldQuant Brain 官方文档、课程与平台提示，供量化 Alpha 探索参考。

---

## 一、核心性能指标

| 指标 | 定义 | 平台检查 |
|------|------|----------|
| **Sharpe** | 年化平均收益 / 年化收益标准差 | `LOW_SHARPE` 低于截止值失败；另有 `LOW_2Y_SHARPE` 单独检查 |
| **Fitness** | `Sharpe × Sqrt(Abs(Returns) / Max(Turnover, 0.125))` | `LOW_FITNESS` 低于截止值失败 |
| **Turnover** | 交易金额 / 持仓金额 | 双向：`LOW_TURNOVER`（过低）和 `HIGH_TURNOVER`（过高） |
| **Returns** | 年化平均损益 / 投资金额 | `LOW_RETURNS` 三级：FAIL / WARNING / PASS |
| **Margin** | PnL / 总交易金额 | 每交易美元的平均损益 |
| **Drawdown** | 回撤 | 标准指标 |

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
| `LOW_TURNOVER` | 换手率过低 | 使用 `hump`/`trade_when`、避免纯截面操作 |
| `HIGH_TURNOVER` | 换手率过高 | 使用 `rank()`/`hump()`/`ts_decay_linear` 平滑 |
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

## 四、44 条模拟提示精华

### 4.1 Turnover 优化

- 提交较低 Turnover 的 Alpha
- 使用 `trade_when` 算子降低 Turnover
- 使用 `rank()` 降低非流动部分的 Turnover（以 adv20 为流动性代理）
- 使用 `ts_decay_linear` 获得合理 Margin
- **注意**: `hump`/`hump_decay`/`ts_decay_exp_window`/`vector_neut` 在 FASTEXPR 模式下不可用，会导致模拟失败

### 4.2 参数选择

- **参数搜索限制在简单合理值：5, 20, 60, 120, 252（天数）**，而非 37, 14 等
- **专注改进想法，而非拟合参数** — 不要靠添加参数/因子/回归元素
- 新颖想法降低相关性，尝试未用过的算子和设置

### 4.3 Neutralization

- 实验不同 Neutralization 设置（Country 和 Sector 通常都有效）
- 使用 `bucket()` 算子进行自定义组 Neutralization
- 使用 `group_neutralize()` 中性化指定分组

### 4.4 信号构建

- 使用 `days_from_last_change()` 捕捉快速衰减信号
- 提交在 Sub-Universe 或 Super-Universe 中保留至少 70% Sharpe 的 Alpha

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

### 5.2 标准窗口参数

| 窗口 | 含义 | 适用场景 |
|------|------|----------|
| 5 | 1 周 | 超短期信号、快速衰减 |
| 20 | 1 月 | 短期信号、月度动量 |
| 60 | 1 季 | 中期信号、季度趋势 |
| 120 | 半年 | 中长期信号 |
| 252 | 1 年 | 长期信号、年度趋势 |

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

## 七、顾问资格

- 需 10,000 积分，通过提交满足阈值的 Alpha 获得
- 经验法则：5~10 个 Alpha 在 5+ 不同日期提交（单日最多 2,000 积分）
- 顾问可访问更多区域、数据字段、多模拟、SuperAlpha、Brain API