# Docs Index

`docs/` 现在收敛为四篇主文档。每个主题只保留一个主要解释位置，其他文档只做简短引用。

## 推荐阅读顺序

1. [01_beginner_guide.md](01_beginner_guide.md)
2. [03_research_and_data_guide.md](03_research_and_data_guide.md)
3. [02_optimization_and_submission.md](02_optimization_and_submission.md)

阅读过程中遇到平台术语、页面字段或状态时，随时查：

- [04_platform_reference.md](04_platform_reference.md)

## 四篇文档的边界

### 01 入门

[01_beginner_guide.md](01_beginner_guide.md) 负责建立基础直觉：

- Alpha、Simulate、Check submission、Submit
- Sharpe、Fitness、Turnover、Drawdown
- Delay、Decay、Neutralization、Truncation、Universe
- Fast Expression 基础语法
- NaN、Pasteurize、Unit Handling

这里只讲第一次学习所需的最小知识；平台状态的完整定义放在 Reference。

### 02 优化与提交

[02_optimization_and_submission.md](02_optimization_and_submission.md) 负责研究后半程：

- `LOW_SHARPE / LOW_FITNESS / HIGH_TURNOVER`
- 权重、Sub-Universe、相关性和成本问题
- 抗过拟合与稳定性验证
- Neutralization 和 D0 的最终决策
- 提交前统一检查顺序

### 03 数据研究与仓库实践

[03_research_and_data_guide.md](03_research_and_data_guide.md) 负责从想法到实验：

- Beginners / Bronze / Silver 示例
- MATRIX、VECTOR、GROUP
- Data Explorer 和字段体检
- 专题数据集研究方法
- Broad search、Local refine、模板库设计
- 仓库知识边界和候选池视角

### 04 平台 Reference

[04_platform_reference.md](04_platform_reference.md) 是查表文档：

- IS、Semi-OS、OS 与状态生命周期
- 页面字段、评分、Universe、Weight、Booksize
- NaN、Pasteurize、Coverage、Correlation
- submission check 名称和页面语义

Reference 主要回答“这个词是什么意思”；具体怎么优化，回到 02。

## 按问题快速定位

| 问题 | 文档 |
|---|---|
| Alpha、基础指标和设置是什么？ | [01](01_beginner_guide.md) |
| 如何理解 Fast Expression 和基本算子？ | [01](01_beginner_guide.md) |
| 官网 Alpha examples 应该怎么学？ | [03](03_research_and_data_guide.md) |
| MATRIX、VECTOR、GROUP 如何分流？ | [03](03_research_and_data_guide.md) |
| Data Explorer 怎么搜，字段怎么体检？ | [03](03_research_and_data_guide.md) |
| 仓库里 Broad search 和 Local refine 怎么安排？ | [03](03_research_and_data_guide.md) |
| LOW_SHARPE、LOW_FITNESS 怎么处理？ | [02](02_optimization_and_submission.md) |
| Turnover、Sub-Universe、相关性怎么优化？ | [02](02_optimization_and_submission.md) |
| D0、Neutralization、提交前检查怎么串起来？ | [02](02_optimization_and_submission.md) |
| IS、Semi-OS、OS、OSTEST 状态是什么意思？ | [04](04_platform_reference.md) |
| 页面上的 N/A、Booksize、Coverage 是什么？ | [04](04_platform_reference.md) |
| 某个 submission check 名称是什么意思？ | [04](04_platform_reference.md) |

## 仓库文档分层

- `docs/`：通用学习路径、研究方法、优化流程和平台查表
- 根 [README.md](../README.md)：安装、项目结构和运行方式
- `templates/<dataset_id>/README.md`：具体数据集策略与本地经验
- `results/`：运行产物，不作为长期知识库

新增知识前先判断归属：

- 基础概念放 01
- 诊断、稳健性和提交方法放 02
- 数据、示例和仓库研究方法放 03
- 纯定义、状态和错误码放 04
- 数据集专属经验放对应模板目录

原则上不再新增与四篇主线平行的 FAQ 或专题摘录页。
