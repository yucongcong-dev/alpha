# 文档索引

`docs/` 只维护一条研究主线，以及平台和工程运行 reference。每个主题保留一个主要解释位置；
教程只保留完成当前流程所需的简短直觉，其余精确定义和操作步骤通过链接复用。

## 阅读顺序

1. [01 入门](01_beginner_guide.md)：先理解 Alpha、模拟设置、核心指标和 Fast Expression。
2. [02 数据研究与仓库实践](02_research_and_data_guide.md)：理解字段、设计模板并形成研究计划。
3. [03 优化与提交](03_optimization_and_submission.md)：诊断失败项、验证稳健性并完成提交前检查。

把研究计划交给本地运行器时，查
[Alpha Runner 运行与本地资产 Reference](runner_reference.md)。
遇到术语、页面状态或平台规则时查 [04 平台 Reference](04_platform_reference.md)；
遇到顾问申请、Workday、付款、Referral 或账号支持时查
[05 平台运营 Reference](05_platform_operations_reference.md)。

## 文档职责

| 文档 | 负责内容 | 不负责内容 |
|---|---|---|
| [01](01_beginner_guide.md) | 新手所需的概念、指标、设置与表达式基础 | 完整平台查表、仓库运行细节 |
| [02](02_research_and_data_guide.md) | 数据类型、字段研究、模板和仓库研究方法 | CLI、缓存、续跑和配置细节 |
| [03](03_optimization_and_submission.md) | 诊断顺序、改进动作、抗过拟合和提交清单 | 平台术语的完整定义 |
| [04](04_platform_reference.md) | IS/OS、页面字段、状态、公式、算子与带日期规则 | 具体 Alpha 优化方案 |
| [05](05_platform_operations_reference.md) | 顾问流程、账户、付款和平台支持 | Alpha 研究与 runner 逻辑 |
| [Runner](runner_reference.md) | CLI、字段调度、缓存、反馈、续跑、结果、配置和清理 | 字段研究方法、平台规则定义 |

根 [README](../README.md) 只提供项目入口和常用命令；
`datasets/<dataset_id>/README.md` 只记录该数据集当前有效证据、运行边界和下一步。

## 官方证据

`source_snapshots/` 保存官网原始证据和带日期的审阅记录，不属于日常维护文档：

- [2026-08-03 Documentation 快照](source_snapshots/worldquant_official_2026-08-03)
- [2026-08-03 Operators 快照](source_snapshots/worldquant_operators_2026-08-03/README.md)
- [2026-08-04 增量复核](source_snapshots/worldquant_review_2026-08-04/README.md)

### 当前同步范围

| 官网区域 | 本地覆盖 | 边界 |
|---|---|---|
| Learn Documentation | `24/24` 篇正文、元数据和官方 URL 已保存在 `2026-08-03` 快照；`2026-08-04` 登录官网复核未发现实质正文变化 | `01-05` 只整合会改变研究、平台判断或操作流程的内容；完整例子和基础材料仍以原始快照为证据，不在主文档重复全文 |
| Learn Courses | 已记录 `2026-07-31` 可见的 `10` 门课程、`46` 个视频课时及主题地图 | 未播放、未转录的视频不写成官方逐字知识；课程与赛事内容会动态变化 |
| Data | 五篇 Understanding Data 文档已整合到 `02/04`；数据集长期结论保存在 `datasets/<dataset_id>/` | 平台全部 dataset/data field 是动态账号数据，不做 Git 全量镜像；API 字段缓存属于可重建本地状态，不提交 |
| Operators | 已保存 `2026-08-03` 当前账号可见的 `7` 类、`66` 个 base operators 及签名说明 | 不是全平台永久全集；Learn 教程提到的算子也可能不在当前账号 Operators API 中，实际可用性以当前页面/API 和模拟结果为准 |

动态数量、阈值和平台规则必须附核对日期。Community 经验只能作为补充，不能覆盖官方正文
或实际 Check Submission 结果。

## 新知识归属

- 基础概念放 01；数据、示例、课程地图和仓库研究方法放 02。
- 诊断、稳健性和提交动作放 03；纯定义、状态和公式放 04。
- 顾问、付款、Referral 和账号支持放 05。
- CLI 行为、运行状态、缓存、结果文件和配置优先级放 Runner Reference。
- 数据集专属结论放对应 README、`template.json` 或 `presets/`。
- `runs/`、`feedback/` 和缓存是可重建运行状态，不作为长期知识库。

原则上不再新增与这些主文档平行的 FAQ 或专题摘录页；新增内容前先更新其唯一归属文档。
