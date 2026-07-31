# Docs Index

`docs/` 收敛为四篇研究主文档和一篇平台运营 reference。每个主题只保留一个主要解释位置，其他文档只做简短引用。
官网 Documentation、Courses、FAQ 和 Community 内容按主题吸收：研究相关内容进入 01-04，
平台运营内容进入 05；不做官网全文镜像，也不为每个 FAQ 分类新增平行摘录页。

## 推荐阅读顺序

1. [01_beginner_guide.md](01_beginner_guide.md)
2. [02_research_and_data_guide.md](02_research_and_data_guide.md)
3. [03_optimization_and_submission.md](03_optimization_and_submission.md)

阅读过程中遇到平台术语、页面字段或状态时，随时查：

- [04_platform_reference.md](04_platform_reference.md)

遇到顾问申请、Workday、银行账户、背景调查、Referral、账号支持等平台运营问题时，查：

- [05_platform_operations_reference.md](05_platform_operations_reference.md)

## 文档边界

### 01 入门

[01_beginner_guide.md](01_beginner_guide.md) 负责建立基础直觉：

- Alpha、Simulate、Check submission、Submit
- Sharpe、Fitness、Turnover、Drawdown
- Delay、Decay、Neutralization、Truncation、Universe
- Fast Expression 基础语法
- NaN、Pasteurize、Unit Handling
- Starter Pack / 10 Steps / Learn2Quant 里适合新手先建立的学习路径

这里只讲第一次学习所需的最小知识；平台状态的完整定义放在 Reference。

### 02 数据研究与仓库实践

[02_research_and_data_guide.md](02_research_and_data_guide.md) 负责从想法到实验：

- Beginners / Bronze / Silver 示例
- Learn/Courses 课程地图
- MATRIX、VECTOR、GROUP
- Data Explorer 和字段体检
- Dataset Usage Management 与数据集优先级
- 专题数据集研究方法
- Broad search、Local refine、模板库设计
- 本地运行、缓存、反馈、结果与配置资产管理
- 仓库知识边界和候选池视角

### 03 优化与提交

[03_optimization_and_submission.md](03_optimization_and_submission.md) 负责研究后半程：

- `LOW_SHARPE / LOW_FITNESS / HIGH_TURNOVER`
- 权重、Sub-Universe、相关性和成本问题
- Research FAQ 里的常见诊断顺序
- 抗过拟合与稳定性验证
- Neutralization 和 D0 的最终决策
- 提交前统一检查顺序

### 04 平台 Reference

[04_platform_reference.md](04_platform_reference.md) 是查表文档：

- IS、Semi-OS、OS 与状态生命周期
- 页面字段、评分、Universe、Weight、Booksize
- NaN、Pasteurize、Coverage、Correlation
- IQC / Challenge-Country / Dataset Usage Management 等平台状态边界
- submission check 名称和页面语义

Reference 主要回答“这个词是什么意思”；具体怎么优化，回到 03。

### 05 平台运营 Reference

[05_platform_operations_reference.md](05_platform_operations_reference.md) 负责平台运营类 FAQ：

- Research Consultant 机会和 onboarding
- Workday、背景调查、协议和 conditional consultant
- 银行账户、earnings、payment 和 referral
- Account、登录、技术支持和 submit request

这篇不参与 Alpha 研究方法和本地 runner 逻辑，只作为平台使用参考。

## 按问题快速定位

| 问题 | 文档 |
|---|---|
| Alpha、基础指标和设置是什么？ | [01](01_beginner_guide.md) |
| 如何理解 Fast Expression 和基本算子？ | [01](01_beginner_guide.md) |
| 官网 Alpha examples 应该怎么学？ | [02](02_research_and_data_guide.md) |
| Learn 页课程应该按什么地图理解？ | [02](02_research_and_data_guide.md) |
| MATRIX、VECTOR、GROUP 如何分流？ | [02](02_research_and_data_guide.md) |
| Data Explorer 怎么搜，字段怎么体检？ | [02](02_research_and_data_guide.md) |
| 仓库里 Broad search 和 Local refine 怎么安排？ | [02](02_research_and_data_guide.md) |
| 如何运行、续跑、清理缓存或理解本地结果？ | [02](02_research_and_data_guide.md) |
| LOW_SHARPE、LOW_FITNESS 怎么处理？ | [03](03_optimization_and_submission.md) |
| Turnover、Sub-Universe、相关性怎么优化？ | [03](03_optimization_and_submission.md) |
| D0、Neutralization、提交前检查怎么串起来？ | [03](03_optimization_and_submission.md) |
| IS、Semi-OS、OS、OSTEST 状态是什么意思？ | [04](04_platform_reference.md) |
| 页面上的 N/A、Booksize、Coverage 是什么？ | [04](04_platform_reference.md) |
| 某个 submission check 名称是什么意思？ | [04](04_platform_reference.md) |
| 顾问申请、Workday、银行、Referral 或账号问题看哪里？ | [05](05_platform_operations_reference.md) |

## 仓库文档分层

- `docs/`：通用学习路径、研究方法、优化流程、平台查表和运营参考
- 根 [README.md](../README.md)：快速启动、项目入口和文档导航
- `datasets/<dataset_id>/README.md`：具体数据集策略与本地经验
- `datasets/<dataset_id>/runs/`：运行产物，不作为长期知识库
- `datasets/<dataset_id>/feedback/<market_scope>/`：按市场范围隔离、跨 run 自动积累的本地反馈状态，可由运行结果重建，不进仓

新增知识前先判断归属：

- 基础概念放 01
- 数据、示例、课程地图和仓库研究方法放 02
- 诊断、稳健性和提交方法放 03
- 纯定义、状态和错误码放 04
- 顾问申请、Workday、银行、Referral、账号支持放 05
- 数据集专属经验放对应 dataset 的 README、template.json 或 presets

原则上不再新增与研究主线平行的 FAQ 或专题摘录页。顾问申请、Workday、银行信息、
账号支持、Referral、IQC 具体日期和付款规则这类内容，只进入 05，不进入 Alpha 研究主线。
