# WorldQuant BRAIN 仓库实战篇

> 目标：把官网方法论落到这个仓库里，形成更稳定的研究和文档边界。

---

## 1. 这个仓库里最容易混淆的三类文档

要尽量分清：

- `docs/`
  通用学习路径
- `README.md`
  工程结构与运行说明
- `templates/<dataset_id>/README.md`
  数据集策略与本地经验

如果这三类内容混在一起，文档很快又会重新变杂。

---

## 2. 官网方法论落到仓库里的第一条

不要把“多跑模板”当默认答案。

更符合官方思路的做法是：

- 先围绕一个假设组织模板族
- 再用 `rank / group / neutralize / decay / trade_when` 做稳健化
- 最后才做小范围局部扩展

这里可以把官方建议再翻译得更具体一点：

- `trade_when` 应该被看成独立模板族，不只是 near-pass 时临时补一层
- `rank / zscore / group_rank / group_neutralize` 优先承担“稳结构”的职责
- `ts_backfill` 只在确实存在 coverage / missing 模式时使用，不要无脑铺满

---

## 3. Broad search 什么时候有意义

Broad search 更适合：

- 新数据集刚开始探索
- 还不知道什么结构有基本信号
- 需要快速摸清字段类型和大方向

但一旦已经知道某些结构长期弱，继续做大范围广搜往往价值不高。

### Broad search 前先做字段体检

官网对新字段给了一套很实用的诊断方法。不要只看 Data Explorer
里的元信息就直接生成模板，先在 `Neutralization=None`、`Decay=0`
下用小批量模拟回答下面的问题：

| 诊断表达式 | 主要回答什么 |
|---|---|
| `{field}` | 用 Long Count + Short Count 粗估实际覆盖率 |
| `{field} != 0 ? 1 : 0` | 每天有多少非零有效值 |
| `ts_std_dev({field}, N) != 0 ? 1 : 0` | 字段按日、周、月还是季度更新 |
| `abs({field}) > X` | 取值边界和异常大值 |
| `ts_median({field}, 1000) > X` | 长期中位数和中心位置 |
| `X < scale_down({field}) && scale_down({field}) < Y` | 原始分布是否集中、偏斜或离散 |

这里最重要的不是把六条表达式加入默认模板库，而是用它们决定：

- 应该用什么窗口
- 是否真的需要 backfill
- 是否需要 winsorize / rank
- 字段更适合连续信号还是事件触发
- 它是否值得进入 broad search

### Data Explorer 的筛选顺序

官网建议先固定 `Region / Delay / Universe`，再搜索字段，因为同一字段不一定
在所有区域和 Delay 下可用。随后综合看：

- `coverage`
- 字段类型
- Dataset Value Score
- `alphaCount / userCount`
- 数据集和字段的拥挤度

搜索词遵循 3S：short、simple、straightforward。对于常见概念，同时搜索全称
和缩写，例如 `earnings per share / EPS`、`implied volatility / IV`。

---

## 4. Local refine 什么时候更合适

当出现这些情况时，更适合 local refine：

- 已经出现 near-pass
- 已经知道某个字段分支最有希望
- 已经知道大范围 broad search 只是在重复失败

这时更应该做的是：

- 小范围结构邻居扩展
- 有意识地调 decay / grouping / neutralization
- 针对主失败项做定向优化

---

## 5. 什么叫“结构替换优先”

结构替换优先，指的是优先考虑这些变化：

- `raw -> rank/zscore`
- `plain -> group_rank/group_neutralize`
- `un-smoothed -> decay/backfill`
- `single-view -> ratio/spread`
- `one field family -> another field family`

官方对降相关的建议，本质上也支持这一点：

- 先换等价字段
- 再换相近算子
- 再换 grouping / neutralization

而不是主要靠窗口微调。

而不是主要靠：

- `20 -> 22`
- `60 -> 63`
- `120 -> 126`

这种近邻窗口抖动。

---

## 6. 什么叫“近邻参数过密”

如果一个模板库里大量候选只是：

- 同一字段
- 同一结构
- 同一 neutralization
- 只差几个相邻窗口

那它们通常并没有提供足够新的研究价值。

这类“密集近邻”容易带来：

- 高相关性
- 假装多样化
- 浪费仿真预算
- 让结果分析失真

---

## 7. 在这个仓库里更推荐的研究节奏

更推荐的节奏：

1. 先做假设
2. 组织少量结构不同的模板
3. 看 `Sharpe / Fitness / Turnover / failed checks`
4. 找出主失败项
5. 做定向 refine
6. 如果主失败项长期不变，再考虑换字段或换假设

在进入 submit-oriented refine 前，再加一道稳健性门：

- Rank test：把最终信号改成截面 rank，观察逻辑是否仍成立
- Binary test：用 `sign` 或条件表达式只保留方向，检查是否过度依赖精确幅度
- Sub/Super Universe：检查结果是否只依赖某一段股票池
- Train/Test：只用 Train 研发，用 Test 做最终验证
- 参数扰动：优先使用 `5/20/60/120/252` 等自然窗口，避免挑中孤立最优点
- 设置扰动：轻微改变 Decay、Neutralization 或 Truncation 后不应立即崩溃

如果只有一个精确参数组合表现突出，不应直接把它当作最佳候选。官网社区更推荐
选择稳定的次优点，或把相邻参数做简单融合，而不是继续追逐尖锐峰值。

而不是：

1. 先生成大量邻近模板
2. 一轮轮多跑
3. 结果不好再继续加数量

---

## 8. 结果文件不应该承担知识库角色

`results/` 适合存运行产物，但不适合长期承担知识库角色。

更合理的边界是：

- 结果：放 `results/`
- 可复用模板：沉淀回 `templates/<dataset_id>/`
- 通用方法论：沉淀回 `docs/`
- 数据集经验：沉淀回 `templates/<dataset_id>/README.md`

否则久了会出现：

- 经验藏在结果文件名里
- 决策藏在历史 json 里
- 复盘只能靠人脑记忆

---

## 9. 仓库也要有“池子视角”

官方 `Meta Score` 的思路提醒了我们一件事：

- 平台不只看单条 Alpha
- 也看你整池 Alpha 的组合质量

官方强调的组合维度主要包括：

- 组合 Sharpe
- 平均 Turnover
- 相关性

这对仓库的直接启发是：

- 不要只做“单条最优”
- 还要避免大量高相关、同质化的候选长期堆积

换句话说：

- 本地研究如果只会不断复制同一想法的小变体
- 就算偶尔单条回测不错，整池价值也未必高

本地候选池至少应该按下面几个维度观察覆盖情况：

- Region
- Universe
- Delay
- Dataset category
- 字段族和研究假设
- 模板族和 Neutralization

这不是要求每个组合都跑一遍，而是避免所有预算长期集中在同一个
`Region × Delay × Dataset × idea family` 上。官网的 Dataset Usage Management
同样在鼓励研究者离开过度使用的数据类别，主动增加研究多样性。

这里还有一个实际的平台约束：当某个 Region 的 Fundamental 使用占比过高时，相关字段可能暂时不能继续模拟或提交；占比降到 `15%` 以下后才恢复访问。应通过平台的 [Alpha distribution](https://platform.worldquantbrain.com/alphas/distribution) 页面观察分布，而不是等接口报错后才被动换数据集。

---

## 10. 对模板库的更健康要求

一个更健康的模板库，应该优先保证：

- 结构差异
- 研究假设差异
- grouping / neutralization 差异
- 稳健化开关差异

而不只是窗口数字不同。

如果把这条再往前推一步，本仓库默认模板库更应该长期偏向：

- 关系型模板优先于单字段平滑模板
- 事件型模板保留独立配额
- 少量强假设模板优先于大量相邻变体

因为官方几类建议合起来都在说明：

- 真正有价值的多样性，主要来自结构差异和假设差异
- 不是来自参数密度

把这条落到仓库动作上，可以更具体一点：

- 默认库里要给 `trade_when` 留独立位置
- 默认库里要区分“表达式内部稳健化”和“依赖平台设置稳健化”
- 高拥挤字段优先做关系化和组内化，不要默认做裸字段平滑

换句话说，模板库设计不只是“收哪些表达式”，还包括：

- 哪些结构值得默认出现
- 哪些结构只该在 refine 阶段出现
- 哪些问题更适合交给设置层，而不是表达式层

### 算子顺序必须表达研究语义

同一组算子换顺序后通常已经是不同假设。例如：

- `rank(ts_delta(x, 20))`：先观察每只股票自身的变化，再做当日截面比较
- `ts_delta(rank(x), 20)`：观察股票截面排名在 20 天内怎样变化
- `group_rank(ts_zscore(x, 252), industry)`：先衡量自身历史异常，再做行业内比较
- `ts_zscore(group_rank(x, industry), 252)`：衡量行业内排名自身的历史异常

模板库应显式命名这些语义差异，不能把算子排列当作无方向的排列组合。

### 不要用线性组合掩盖弱假设

直接写 `a * alpha1 + b * alpha2` 可能抬高某次回测，也可能只是让强分支掩盖弱分支，并引入难以解释的相关暴露。组合前应分别验证每个分支，并检查组合是否真的改善稳健性、相关性或覆盖，而不只是改善单次 Sharpe。

---

## 11. 对文档体系的更健康要求

更建议保持这套边界：

- 主学习路径：`docs/01~04`
- 总导航：`docs/README.md`
- 工程入口：`README.md`
- 数据集策略说明：`templates/<dataset_id>/README.md`

这样你后续继续做长期项目时，文档才不容易失控。

---

## 12. 这份仓库最值得长期坚持的原则

- 仿真通过不等于可提交
- 结果数量不等于研究进展
- 相邻模板不等于多样化
- 结构升级优先于参数微调
- 官方知识更适合并回主线文档，不要不断平行加专题页
- 文档边界清晰，比一次性写很多更重要
- 官方提交规则与社区压力测试必须分开记录；后者用于提高置信度，不能冒充平台硬门槛

最终候选除平台 `check submission` 外，建议再做一组社区压力测试：Rank/Binary、Train/Test、参数和设置扰动、Sub/Super Universe，以及显式开启 `Max Trade` 的集中度挑战。`Max Trade` 默认仍保持 `OFF`，只对少量候选使用，避免把实验开关误扩散到所有 broad search。

---

## 13. 下一步建议

如果继续往下整理，我更建议按这个顺序做：

1. 对齐 `README.md` 和四篇主文档的链接
2. 给 `templates/model16/README.md`、`templates/model51/README.md`、`templates/fundamental6/README.md` 保持统一结构
3. 新的官方知识继续合并进现有四篇主文档，不再单独增加 FAQ 摘录篇

这样整套知识体系会比现在更稳。

---

## 14. 官方来源

- [Understanding Data in BRAIN: Key Concepts and Tips](https://platform.worldquantbrain.com/learn/documentation/understanding-data/data)
- [How to use the Data Explorer](https://platform.worldquantbrain.com/learn/documentation/understanding-data/how-use-data-explorer)
- [Group Data Fields](https://platform.worldquantbrain.com/learn/documentation/understanding-data/group-data-fields)
- [How can you avoid overfitting?](https://support.worldquantbrain.com/hc/en-us/community/posts/8209806533015-How-can-you-avoid-overfitting-)
- [Dataset Usage Management](https://support.worldquantbrain.com/hc/en-us/sections/22696480006423-Dataset-Usage-Management)
