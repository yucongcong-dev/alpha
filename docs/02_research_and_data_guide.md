# WorldQuant BRAIN 数据研究与仓库实践

> 目标：把官网 examples、字段研究方法与本仓库的模板实践收口成一条可执行的研究路径。

---

## 1. 这篇文档适合什么时候看

当你遇到下面这些问题时，优先看这篇：

- 我需要一个官方认可的 Alpha 原型，从哪类表达式起步？
- 新字段太多，应该先怎么理解它们？
- `MATRIX / VECTOR / GROUP` 分别是什么，研究方式有何不同？
- `Data Explorer` 到底该怎么搜字段和数据集？
- `Option6` 这类专题数据集应该从哪些字段族开始做？

这篇不负责讲提交流程和失败项诊断；那部分主要放在 `03` 和 `04`。

---

## 2. 官网 Alpha 示例三层路径

官网 examples 最适合当“表达式原型库”，而不是直接当提交答案。

### 2.1 Beginners

对应页面：

- `19-alpha-examples`

官方重点：

- 用最短表达式把一个直观假设翻译出来
- 典型动作包括：
  - `ts_rank`
  - 负号反转
  - 比率化
  - `group_rank`
  - `ts_std_dev`

最值得学的不是具体公式，而是这套顺序：

1. 写 `Hypothesis`
2. 写 `Implementation`
3. 先给一个最小表达式
4. 再围绕窗口、分组、比率、平滑做优化

### 2.2 Bronze

对应页面：

- `sample-alpha-concepts`
- 页面标题实际是 `Alpha Examples for Bronze Users`

相比 Beginners，多了几类关键动作：

- `ts_zscore`
- `ts_corr`
- 更明确的估值比率和波动率比率
- 行业内比较

Bronze 的实质，是从“会写信号”走向“会做结构化表达式”。

### 2.3 Silver

对应页面：

- `example-expression-alphas`
- 页面标题实际是 `Alpha Examples for Silver Users`

Silver 比 Bronze 再进一步，引入：

- `trade_when`
- `ts_backfill`
- `ts_regression(..., rettype=2)`
- `ts_decay_linear`
- `winsorize`
- 多行表达式和中间变量

最实用的理解：

- Bronze 更像“会搭表达式”
- Silver 更像“会把表达式写得更接近可提交研究”

---

## 3. 从 examples 提炼出的通用表达式骨架

官网 examples 可以抽象成几类常用骨架：

### 3.1 时间序列位置

```text
ts_rank(field, 252)
ts_zscore(field, 60)
```

适合：

- 慢频基本面
- 平滑后的估值或质量指标

### 3.2 行业内比较

```text
group_rank(signal, industry)
group_zscore(signal, subindustry)
```

适合：

- 基本面
- 分析师
- Earnings

### 3.3 事件门控

```text
trade_when(condition, signal, -1)
```

适合：

- D0
- 事件型新闻 / 期权 / 财报逻辑
- 高换手软信号加置信度过滤

### 3.4 平滑与稳健化

```text
winsorize(ts_backfill(field, 60), std=4)
ts_decay_linear(signal, 20)
```

适合：

- 缺值较多或尖峰较多的字段
- turnover 偏高但逻辑还在的信号

---

## 4. Understanding Data：先理解字段，再研究字段

对应页面：

- `understanding-data/data`

官网对字段最重要的区分是：

- `Data Field`：有固定类型和业务含义的最小数据单元
- `Dataset`：一组 Data Field

同时一定要分清三种字段类型：

- `MATRIX`
- `VECTOR`
- `GROUP`

这是后续模板分流的起点。

---

## 5. MATRIX、VECTOR、GROUP 的研究分工

### 5.1 MATRIX

每个 `date × instrument` 只有一个值。

特点：

- 最适合直接进入普通表达式模板
- 大多数 `rank / ts_* / group_*` 算子默认都围绕这类字段

### 5.2 VECTOR

每个 `date × instrument` 有多个值，而且数量不固定。

特点：

- 不能直接和普通 matrix 字段混用
- 必须先通过 `vec_*` 算子聚合成单值

常见聚合：

- `vec_count`
- `vec_avg`
- `vec_max`
- `vec_stddev`
- `vec_skewness`

研究重点不在“先套模板”，而在：

- 我到底想提取事件数量、平均水平、极值冲击，还是离散程度

### 5.3 GROUP

不是方向信号本身，而是分组标签。

典型字段：

- `sector`
- `industry`
- `subindustry`
- `exchange`

用途：

- 给 `group_rank / group_zscore / group_neutralize` 提供分组依据

也可以用 `bucket()` 自造 group，然后配合 `densify()` 使用。

---

## 6. 字段体检六步法

对应页面：

- `understanding-data/data`

官网给了一套非常实用的新字段体检法，建议在：

- `Neutralization=None`
- `Decay=0`

下小批量模拟。

### 6.1 看粗 coverage

```text
field
```

用途：

- 用 `Long Count + Short Count` 粗估字段覆盖率

### 6.2 看非零 coverage

```text
field != 0 ? 1 : 0
```

用途：

- 看每天实际有多少非零有效值

### 6.3 看更新频率

```text
ts_std_dev(field, N) != 0 ? 1 : 0
```

用途：

- 判断是日频、周频、月频还是季频更新

### 6.4 看边界和极值

```text
abs(field) > X
```

用途：

- 看量纲、边界、是否有大尖峰

### 6.5 看长期中心位置

```text
ts_median(field, 1000) > X
```

用途：

- 判断长期中位数大概落在哪

### 6.6 看分布

```text
X < scale_down(field) && scale_down(field) < Y
```

用途：

- 判断分布是否偏斜、是否大量堆在边界附近

---

## 7. Data Explorer：先缩小范围，再开始研究

对应页面：

- `understanding-data/how-use-data-explorer`

官网建议在搜索前先固定：

- `Region`
- `Delay`
- `Universe`

因为同一字段不一定在所有区域和 Delay 下都可用。

### 7.1 搜索策略

官方推荐 `3S`：

- `short`
- `simple`
- `straightforward`

也就是说：

- 搜索词尽量短、简、直
- 如果不确定标准术语，可以先用自己的话解释它

### 7.2 同时搜全称和缩写

例如：

- `earnings per share` / `EPS`
- `implied volatility` / `IV`

### 7.3 官方建议看的筛选维度

- `coverage`
- 字段类型
- `alphaCount`
- `userCount`
- `crowdedness`
- `Dataset Value Score`

更适合的顺序通常是：

1. 按 idea 搜
2. 先定 dataset 或 field 范围
3. 按 coverage 过滤
4. 按 type 分流
5. 再用 `alphaCount / userCount` 看拥挤度

---

## 8. Dataset Value Score 的正确位置

官网定义：

- 它衡量数据集是否“未被充分使用”

更适合把它理解成：

- 一个研究优先级参考
- 不是“高分就一定好做”的保证

因此更合理的顺序是：

1. 先看逻辑和字段可解释性
2. 再看 coverage 和更新频率
3. 最后用 `Value Score` 和拥挤度辅助排序

---

## 9. Option6 Implied Volatility：专题数据集怎么拆

对应页面：

- `understanding-data/getting-started-option6-implied-volatility-iv`

官网给出的画像非常清楚：

- `MATRIX only`
- D0 / D1 都有
- USA 覆盖率很高
- 更适合研究“波动率结构”和“预测置信度”

### 9.1 六个字段家族

官网把 Option6 拆成：

1. `Constant-Maturity Implied Volatility`
2. `Volatility Surface Shape`
3. `Forecast Family`
4. `Earnings-Effect Series`
5. `Dividend Cluster`
6. `Cross-Asset Ratios`

### 9.2 哪些最值得优先研究

官网和实战都更推荐优先看：

- `slope / deriv / vired`
- `fcst*` 置信度字段
- `dividend cluster`
- `ivspyratio / ivetfratio`

而不是只盯“原始 IV 水平”。

### 9.3 Option6 的几个官方使用建议

- 长 backfill 要克制；通常 `ts_backfill(5)` 足够
- 原始 vol-surface 字段优先试 `Sector neutralization`
- 已比值化的 ratio 字段更适合 `Market neutralization`
- 很多字段已经自带平滑，避免再叠过多 `ts_mean`
- 两个 Option6 字段之间直接做 `ts_corr` 要很谨慎
- `fcstr2imp` 这类置信度字段很适合做 `trade_when` gate

---

## 10. 对这个仓库的直接落地建议

把这些官网 data 文档翻译成仓库动作，最实用的版本是：

1. 先用 Data Explorer 缩小字段范围
2. 再做字段体检六步法
3. 根据类型把字段分流：
   - `MATRIX` 进主模板
   - `VECTOR` 进专项聚合分支
   - `GROUP` 进分组与中性化分支
4. 对专题数据集先按官方字段家族拆，不要一上来把全字段混扫

特别是：

- `VECTOR` 不应和 `MATRIX` 一锅炖
- `GROUP` 不应被当成普通方向信号字段
- `Option6` 不应只当“另一套价格波动率字段”

---

## 11. 仓库研究流程

官网方法落到本仓库后，建议把研究分成两个阶段。

### 11.1 Broad search

适合新数据集和未知字段族。开始前先完成字段体检，不要直接根据 Data Explorer
元信息批量生成模板。Broad search 的目标是找到有信息量的结构方向，而不是覆盖
所有窗口组合。

### 11.2 Local refine

出现 near-pass、明确的主失败项或有希望的字段分支后，再做定向 refine：

- 优先替换结构：`raw -> rank/zscore`
- 尝试组内比较：`group_rank/group_neutralize`
- 根据缺失和更新频率决定是否 backfill
- 根据变化频率决定 decay、hump 或 `trade_when`
- 最后才做小范围窗口扰动

不要把 `20 -> 22 -> 24` 这类密集近邻当作研究多样性。真正的多样性主要来自：

- 假设差异
- 字段族差异
- 表达式结构差异
- grouping / neutralization 差异
- 事件型与连续型信号差异

### 11.3 推荐节奏

1. 写清假设
2. 选择少量结构不同的原型
3. 查看 `Sharpe / Fitness / Turnover / failed checks`
4. 找出主失败项
5. 做定向 refine
6. 做 Rank/Binary、Train/Test、Universe 和参数扰动
7. 主失败项长期不变时，换字段或换假设

### 11.4 算子顺序就是研究语义

以下表达式不是可互换的排列：

```text
rank(ts_delta(x, 20))
ts_delta(rank(x), 20)
group_rank(ts_zscore(x, 252), industry)
ts_zscore(group_rank(x, industry), 252)
```

它们分别回答“自身变化后的截面位置”“截面位置的时间变化”“历史异常后的行业位置”
和“行业位置的历史异常”。模板名称和实验记录应体现这种语义差异。

### 11.5 仓库知识边界

- `results/`：运行产物，不承担长期知识库职责
- `templates/<dataset_id>/`：可复用模板和数据集经验
- `docs/`：跨数据集的方法论和平台知识
- 根 `README.md`：工程结构、安装与运行入口

成熟结论应从结果文件沉淀回模板或文档，避免决策长期藏在 JSON 和文件名中。

### 11.6 候选池视角

本地研究不只追求单条最优，还应观察候选池在以下维度的覆盖与相关性：

- Region / Universe / Delay
- Dataset category 与字段族
- 研究假设与模板族
- Neutralization
- 平均 Turnover 与组合相关性

模板库应优先保证结构和假设差异，不应依靠大量相邻窗口制造表面多样性。

---

## 12. 最后压成一句话

官网这些 examples 和 understanding-data 文档合在一起，其实是在教同一件事：

- `examples` 教你怎么把假设翻成表达式原型
- `data` 文档教你怎么先理解字段结构，再决定该用哪类原型

如果跳过中间这层字段理解，后面的模板扩展和 submit-oriented refine 会很容易白跑。

---

## 13. 官方入口

- [Alpha Examples for Beginners](https://platform.worldquantbrain.com/learn/documentation/create-alphas/19-alpha-examples)
- [Alpha Examples for Bronze Users](https://platform.worldquantbrain.com/learn/documentation/examples/sample-alpha-concepts)
- [Alpha Examples for Silver Users](https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas)
- [Understanding Data in BRAIN: Key Concepts and Tips](https://platform.worldquantbrain.com/learn/documentation/understanding-data/data)
- [How to use the Data Explorer](https://platform.worldquantbrain.com/learn/documentation/understanding-data/how-use-data-explorer)
- [Vector Data Fields](https://platform.worldquantbrain.com/learn/documentation/understanding-data/vector-datafields)
- [Group Data Fields](https://platform.worldquantbrain.com/learn/documentation/understanding-data/group-data-fields)
- [Getting Started with Option6 Implied volatility (IV)](https://platform.worldquantbrain.com/learn/documentation/understanding-data/getting-started-option6-implied-volatility-iv)
