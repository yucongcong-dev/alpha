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

### 2.4 Learn/Courses 课程地图

Learn 页课程主要适合作为研究地图，不适合直接转成模板全文。当前课程可以按用途分成几类：

| 课程 | 用途 |
|---|---|
| `Quantcepts` | 快速建立量化金融概念，例如 alpha、factor risk、market neutrality、options、sentiment、fundamentals |
| `Introduction to Quantitative Finance` | 理解 quant research ecosystem、Alpha 创建和质量评估 |
| `Introduction to WorldQuant BRAIN` | 了解 BRAIN 顾问路径和平台定位 |
| `Introduction to Alphas` | 学习创建、分析和改进 Alpha 的基础流程 |
| `Basic Operators` | 学习基础 operator 和 neutralization |
| `Alpha Examples by Data Category` | 按数据类别理解 idea 到结果的转换 |
| `Alpha Examples by Idea type and Delay` | 按 idea 类型和 D0/D1 延迟差异理解 Alpha |
| `Combining Alphas and Risk Management` | 从 Alpha 池多样性和风险管理角度理解组合 |
| `Implementing Advanced Ideas on Brain` | 了解更高级数据和深度学习方向 |
| `International Quant Championship 2026` | 竞赛规则与赛程，和普通研究方法保持边界 |

截至 `2026-07-31`，当前官网课程目录共 `10` 门课程、`46` 个视频课时。本次审阅覆盖课程页和课时主题，
但没有把未播放、未转录的视频内容写成“官方逐字知识”。课程数量和赛季课程会变化，引用时应保留日期。

Operators 页当前账号可见 `7` 类算子：Arithmetic、Logical、Time Series、Cross Sectional、Vector、
Transformational、Group，共解析到 `66` 个 `base` 算子。平台说明更高等级可能解锁更多算子，
因此本地知识库记录的是带日期的账号可见快照，不把 `66` 当成全平台永久总数。

本地已保存 `2026-08-03` 的官方 Operators API 快照：
[worldquant_operators_2026-08-03](source_snapshots/worldquant_operators_2026-08-03/README.md)。
`2026-08-04` 通过官网再次复核，当前仍为 `7` 类、`66` 个 `base` 算子，签名和说明未变化；
增量记录见 [worldquant_review_2026-08-04](source_snapshots/worldquant_review_2026-08-04/README.md)。
研究时不需要把它当成一篇从头读到尾的教程，而应该把分类当成表达式设计的积木：

- Arithmetic：做符号、安全变换和基础比例关系，例如 `log`、`signed_power`、`divide`
- Logical：做条件判断和事件门控，例如 `if_else`、比较运算、`is_nan`
- Time Series：做历史窗口里的平滑、排名、缺失修复和变化检测，例如 `ts_rank`、`ts_zscore`、`ts_backfill`
- Cross Sectional：做同一天同 Universe 内的排序、标准化和极值处理，例如 `rank`、`zscore`、`winsorize`
- Group：做组内比较、组内中性化和组内缺失修复，例如 `group_rank`、`group_neutralize`、`group_backfill`
- Vector：先把向量字段聚合成可进入普通模板的标量，例如 `vec_avg`、`vec_sum`
- Transformational：控制分桶和持仓触发，例如 `bucket`、`trade_when`

本仓库吸收课程内容时只保留两类东西：

- 能改变研究流程的概念，例如多样性、风险管理、data category、Delay 匹配
- 能落到模板和检查逻辑的结构，例如 event gate、group relative、operator sequencing

纯视频课时、竞赛报名、团队和顾问权益信息不进入模板文档。

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

> 字段类型的完整定义和平台语义见 [04 §10](04_platform_reference.md)。

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

> Coverage 的完整定义和平台语义见 [04 §12.1](04_platform_reference.md)。

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

本地自动探索遵循同一原则。新数据集默认先过滤低覆盖、验证样本过少和极度拥挤的字段，再使用固定尺度综合评分。`alphaCount / userCount` 不是越低越好：少量使用用于证明字段可运行，超过拥挤起点后才逐步降权。

应用 `--limit` 时还会做两层预算保护：

- 将 `_10 / _30 / _60 / _180_days` 等期限片段折叠为同一字段族，即使后面还有 `_spy` 等标的后缀也会归并；每个字段族默认先取不超过 2 个代表字段
- 在已有历史反馈时，默认保留约 40% 名额给未探索字段；其余名额只分给已证明优质的反馈，普通失败历史不会挤占探索预算
- 已通过 submission 检查的 Alpha 立即构成强正反馈；其他历史反馈仍受最小尝试次数和结果时间半衰期约束，避免单次偶然高分或过期结果长期占优

人工传入 `--include-fields-file` 时视为明确研究选择，不再执行字段族配额与探索比例，但仍保留基础质量检查。运行 `--dry-run-plan` 可以直接查看字段分数、原始排名、字段族、入选原因、不可执行字段数和过滤统计。全局模板剪枝不会让未探索字段整体空跑：在结构和人工过滤均通过时，系统最多保留一个种子模板作探索验证。

字段元数据缺失时会保留候选并记录 `unknown_*` 计数，同时对评分施加轻微惩罚；这与真实低覆盖、低验证样本的过滤原因分开统计。

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

> Dataset Value Score 和 Alpha list 的平台语义见 [04 §12.2.3](04_platform_reference.md)。

### 8.1 Dataset Usage Management 的研究含义

FAQ 里的 Dataset Usage Management 主要是平台对部分数据集类别访问和使用的管理机制。
它不应该被理解成“某个数据集质量变差”，更接近：

- 平台会对特定数据集类别设置使用阈值或约束
- 约束可能影响能否继续使用某一类 dataset
- 恢复访问通常取决于平台规则和用户后续研究表现

对本仓库最实用的结论是：

- 不要把研究流程绑死在单一数据集类别上
- `datasets/<dataset_id>/README.md` 应记录替代字段族和替代数据集方向
- 模板库应优先沉淀可迁移结构，而不是只记住某个字段名
- dry-run 计划和缓存缺失要能清楚提示“本地没有资源”，不要误判成字段质量差

如果某类数据集访问受限，优先动作不是删掉相关模板，而是：

1. 保留历史结论
2. 将该数据集标记为暂不可用或降优先级
3. 用同类 idea 在其他 dataset category 上找替代字段

> Dataset Usage Management 的平台定义见 [04 §12.2.4](04_platform_reference.md)。

### 8.2 数据访问、外部工具与数据集退役

本轮逐篇复核 Research FAQ 后，下面几条应作为硬边界记住：

- BRAIN 的底层数据属于专有信息；研究者可以查看模拟结果，但不能下载每个 instrument 的逐日底层数据。
- BRAIN 平台当前用于编写 Alpha 的入口是 Fast Expressions。FAQ 同时说明，顾问可获得 Python API 文档，低强度的程序化 API 访问目前不被禁止；这不等于可以绕过平台读取原始数据，也不等于所有账号都自动拥有相同 API 权限。
- 因此，Python / R / MATLAB 更适合做研究记录、参数管理和结果分析；Alpha 本身仍应按平台允许的 Fast Expressions / API 流程提交，不能把“外部算出一个向量后上传”理解成官方支持的原始数据工作流。
- 如果 Dataset XYZ 从 Data Explorer 消失，官方解释通常是数据集被 decommission：供应方停止发布，或 WorldQuant 暂停访问。依赖它的 Alpha 可能被标记为 `DECOMMISSIONED`；数据集未来恢复时，相关 Alpha 可能重新激活。

对仓库的落地方式：

1. 数据集 README 记录状态、替代字段族和最后核对日期。
2. 不把底层数据下载写入自动化设计，也不把 API 低强度访问当成无限速率权限。
3. 运行器遇到数据集消失时，区分“本地缓存缺失”和“平台数据集退役”，不要自动改写研究假设。

官方入口：

- [Can I download the underlying data used in making Alphas?](https://support.worldquantbrain.com/hc/en-us/articles/5971334165655-Can-I-download-the-underlying-data-used-in-making-Alphas)
- [Can we use API?](https://support.worldquantbrain.com/hc/en-us/articles/5970985302679-Can-we-use-API)
- [Can I use Python / R / MATLAB etc. for Alphas?](https://support.worldquantbrain.com/hc/en-us/articles/5971076730775-Can-I-use-Python-R-MATLAB-etc-for-Alphas)
- [I can no longer find Dataset XYZ on the platform. Where can I find it?](https://support.worldquantbrain.com/hc/en-us/articles/22468202055959-I-can-no-longer-find-Dataset-XYZ-on-the-platform-Where-can-I-find-it)

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

- `datasets/<dataset_id>/runs/`：运行产物，不承担长期知识库职责
- `datasets/<dataset_id>/feedback/<market_scope>/`：按 region、universe、instrument、delay 隔离的自动反馈仓，保存已尝试组合、near-pass 历史、增量 run 索引和只读模板统计
- `datasets/<dataset_id>/template.json`：默认模板库
- `datasets/<dataset_id>/presets/`：按研究目的组织的专项模板、字段与模板筛选清单
- `docs/`：跨数据集的方法论和平台知识
- 根 `README.md`：工程结构、安装与运行入口

feedback 目录用于机器自动复用历史，但仍属于可重建运行状态。成熟结论应从结果文件沉淀回模板或文档，避免人工决策长期藏在 JSON 和文件名中。

### 11.6 候选池视角

本地研究不只追求单条最优，还应观察候选池在以下维度的覆盖与相关性：

- Region / Universe / Delay
- Dataset category 与字段族
- 研究假设与模板族
- Neutralization
- 平均 Turnover 与组合相关性

模板库应优先保证结构和假设差异，不应依靠大量相邻窗口制造表面多样性。
仓库的 generate 阶段因此只保留基准 settings 预算；额外 settings 变体集中到 refine / resimulate 阶段。

---

## 12. 运行器操作与本地资产

这一节说明仓库如何把研究计划变成可恢复的本地运行。默认流程只执行
`simulation + Check Submission`，不会自动执行平台的正式 `submit`。

### 12.1 最小运行路径

```bash
# 需要登录：冒烟模式（1 字段/1 模板、并发 1）快速验证凭证、API 连通性和模拟创建
python -m alpha --smoke-test

# 离线只读：检查字段、模板和候选计划，不创建 simulation
python -m alpha --dry-run-plan

# fundamental6 广泛探索：首次会拉取字段缓存，且必须显式给出 simulation 硬预算
python -m alpha --dataset-id fundamental6 --full-run --max-total-simulations 100

# 聚焦历史上更有希望的字段
python -m alpha --top-fields-by-feedback 10 --max-templates-per-field 15
```

不传参数时，运行器采用内置默认搜索预算。`--full-run` 会枚举更大的字段和模板空间，
但仍保留 simulation 总预算。运行器先进入 Seed 阶段：历史上没有有效尝试的合格字段
每个最多调度一个候选；只有所有字段都已获得种子尝试或被判定为不可执行后，才进入正常
refine 轮次。默认最多调度 500 个 simulation；可用 `--max-total-simulations N` 调整，
显式传入 `0` 才会取消总预算。若预算低于剩余 Seed 字段数，运行日志和 dry-run 会明确
标记 partial seed coverage，并且本次不会提前进入 refine。全量模式只适合有足够时间、
且明确希望从零开始验证时使用。日常研究应从 `--dry-run-plan` 开始。

### 12.2 字段选择如何落地

首次真实运行会按 `dataset + region + universe + instrument_type + delay` 拉取字段，
并缓存到：

```text
datasets/<dataset>/cache/<region>_<universe>_<instrument>_d<delay>.json
```

例如 `usa_top3000_equity_d1.json`。同一市场范围会复用缓存；缓存缺失或结构失效时，
正常运行会重新拉取。`--dry-run-plan` 只使用本地缓存，不登录、不联网；没有匹配缓存时应先做一次正常运行。

有限 `--limit` 下的候选保护机制：

- 先按 `coverage`、`dateCoverage`、`alphaCount`、`userCount` 做质量与拥挤度筛选；字段指标缺失会降分并单独记录，不会误删。
- 数字窗口字段会归并成字段族，避免同一信号的 20/30/60 天版本占满预算。
- 默认约 40% 名额保留给未探索字段；其余名额只给历史优质字段，普通失败记录不会挤占探索预算。
- 任一通过 submission check 的 Alpha 会立即成为强正反馈；其他反馈还需满足最小样本量和时间衰减条件。
- 反馈只分为两段：新字段以一个低成本种子模板探索；达到明确门槛后才进入 resimulate/refine。全局模板历史不会硬性阻止新字段探索。

`--include-fields-file` 是人工明确指定的研究范围，因此跳过字段族配额和探索比例，但仍执行基础质量检查。

### 12.3 数据集资产与仓库边界

每个数据集的长期、可审阅资产：

| 路径 | 用途 | 是否提交 |
|---|---|---|
| `datasets/<id>/template.json` | 默认模板库 | 是 |
| `datasets/<id>/presets/` | 专项模板、字段或模板筛选清单 | 是 |
| `datasets/<id>/blacklist.json` | 长期排除规则 | 是 |
| `datasets/<id>/README.md` | 当前策略、验证结论与下一步 | 是 |
| `datasets/<id>/cache/` | 可重拉的字段缓存 | 否 |
| `datasets/<id>/runs/` | 单次运行 journal、state、分析与日志 | 否 |
| `datasets/<id>/feedback/<scope>/` | 跨 run 反馈、只读模板统计和去重索引 | 否 |

`blacklist.json` 是唯一模板排除入口：`learned_templates` 保存学习或人工维护的条目，
`expression_rules` 保存人工规则；规则可用 `target: expression` 匹配表达式，或用
`target: template_name` 匹配模板名称。自动学习默认关闭；显式使用
`--auto-update-blacklist` 时，达到学习门槛的条目会在事务锁内去重并直接写入
`blacklist.json`，随后立即参与当前进程和后续运行的模板过滤。

成熟结论必须从 `runs/` 或 `feedback/` 中沉淀到 `template.json`、`presets/` 或数据集 README；
不要把长期人工决策留在临时文件名或 JSON 结果里。一次性实验输入放 `tmp/`，外部对照材料或手工草稿放 `scratch/`。
模板的默认排序直接维护在 `template.json` 的 `priority`；不要再为单个历史模板名叠加 YAML 优先级惩罚。

### 12.4 续跑、反馈与结果

每次运行默认是增量模式：已完成的“字段 + 模板 + 表达式 + settings”组合不会重复创建；
中断时会保存 `state.json` 与 `interrupt_report.json`，再次运行自动恢复可轮询的远端 simulation。
如需独立实验，优先使用新的 `--run-name`。

运行结果目录：

| 文件 | 含义 |
|---|---|
| `runs/<run>/results.jsonl` | 权威结果 journal；其他分析视图可由它重建 |
| `runs/<run>/summary.json` | 当前 run 的轻量 summary 与 journal 指针 |
| `runs/<run>/analysis.json` | near-pass、失败分布、模板和字段表现 |
| `feedback/<scope>/results.jsonl` | 带来源和 revision 的跨 run 去重结果历史 |
| `feedback/<scope>/run_index.json` | 已聚合 run 的轻量索引 |

`submittable=true` 表示该 Alpha 通过本轮 submission check、具备人工提交价值；
`submitted=false` 表示运行器没有替你正式提交。`PENDING` 结果以 `submittable=null` 保存，
不会被当作通过、失败反馈或 near-pass，但会在后续启动时重新查询终态。

### 12.5 路径、配置与清理

工作区按以下优先级选择：`ALPHA_WORKSPACE_ROOT`、源码仓库（或当前含 `datasets/` 与 `config/` 的目录）、`~/.alpha/`。
相对路径参数按命令执行目录解析；`--output`、`--fields-cache-file`、`--include-fields-file` 和模板库路径都可显式覆盖默认值。

可编辑配置的唯一来源是根目录 `config/*.yaml`。日常运行参数主要在 `settings.yaml`，
运行策略 profile schema、数据集 profile、表达式策略、质量反馈和模板默认值分别按各自 YAML 维护；
`src/alpha/resources/config/*.yaml` 是安装包镜像，不应直接修改。

运行策略用 `global.runtime.strategy_profile` 或 `--strategy-profile` 显式标记，当前支持：

- `explore`：广覆盖探索，优先发现字段/模板是否有基本信息量
- `refine`：反馈邻域优化，优先围绕 near-pass 和已知有效结构做小范围变体
- `submit-focused`：提交导向收敛，优先控制风险、相关性和可提交数量

`config/strategy_profiles.yaml` 同时定义策略说明、常调参数边界和 `runtime_defaults`。
当前 `refine` 会收窄字段与模板预算，`submit-focused` 还会聚焦历史反馈字段并设置
`stop_after_submittable`；`explore` 不额外改写默认预算。显式 CLI 参数优先于 profile 默认值，
dataset profile 先于 strategy profile 合并，`--smoke-test` / `--full-run` 最后按运行模式归一化
搜索范围。具体生效值以 dry-run 输出和 run config snapshot 为准。

```bash
# YAML 改动后同步并检查
make sync-config
make check

# 仅预览 / 执行可重建运行产物清理（默认保留 .credentials）
python -m alpha clean --dry-run-clean
python -m alpha clean
```

`alpha clean` 处理数据集的 `cache/`、`runs/` 和遗留运行产物；`make clean-dev` 处理 Python
字节码、测试缓存、coverage 与开发安装元数据。只有明确传入 `--include-credentials` 才会清理本地加密凭证。

---

## 13. 最后压成一句话

官网这些 examples 和 understanding-data 文档合在一起，其实是在教同一件事：

- `examples` 教你怎么把假设翻成表达式原型
- `data` 文档教你怎么先理解字段结构，再决定该用哪类原型

如果跳过中间这层字段理解，后面的模板扩展和 submit-oriented refine 会很容易白跑。

---

## 14. 官方入口

- [Alpha Examples for Beginners](https://platform.worldquantbrain.com/learn/documentation/examples/19-alpha-examples)
- [Alpha Examples for Bronze Users](https://platform.worldquantbrain.com/learn/documentation/examples/sample-alpha-concepts)
- [Alpha Examples for Silver Users](https://platform.worldquantbrain.com/learn/documentation/examples/example-expression-alphas)
- [Courses](https://platform.worldquantbrain.com/learn/courses)
- [Operators](https://platform.worldquantbrain.com/learn/operators)
- [本地 Operators API 快照（2026-08-03）](source_snapshots/worldquant_operators_2026-08-03/README.md)
- [Understanding Data in BRAIN: Key Concepts and Tips](https://platform.worldquantbrain.com/learn/documentation/understanding-data/data)
- [How to use the Data Explorer](https://platform.worldquantbrain.com/learn/documentation/understanding-data/how-use-data-explorer)
- [Vector Data Fields](https://platform.worldquantbrain.com/learn/documentation/understanding-data/vector-datafields)
- [Group Data Fields](https://platform.worldquantbrain.com/learn/documentation/understanding-data/group-data-fields)
- [Getting Started with Option6 Implied volatility (IV)](https://platform.worldquantbrain.com/learn/documentation/understanding-data/getting-started-option6-implied-volatility-iv)
