# WorldQuant BRAIN 学习地图

> 这份文件现在只负责做“学习路径导航”。
> 如果你想按问题或角色查文档，请直接看 [docs/README.md](README.md)。

---

## 推荐阅读顺序

如果你是第一次系统学习 BRAIN，建议按下面顺序阅读：

1. [01_beginner_guide.md](01_beginner_guide.md)
   先理解 Alpha 是什么、平台主流程是什么、结果怎么看、常用设置和基本算子怎么理解。
2. [02_optimization_guide.md](02_optimization_guide.md)
   再理解 `Sharpe / Fitness / Turnover / Correlation` 的诊断逻辑，以及常见失败项该怎么优化。
3. [03_repo_practice_guide.md](03_repo_practice_guide.md)
   最后把官网知识映射回本仓库，形成稳定的研究和迭代习惯。
4. [04_platform_terms_and_states.md](04_platform_terms_and_states.md)
   当你需要快速查术语、状态、评分、OS 页面字段含义时，直接查这篇。

如果你已经在跑这个仓库，建议直接从第 2 篇开始，再补第 3 篇。

---

## 学习路径说明

- `01_beginner_guide.md`
  负责建立基础直觉：Alpha、设置、指标、基本算子。
- `02_optimization_guide.md`
  负责解释失败项、优化顺序和调参边界。
- `03_repo_practice_guide.md`
  负责把官网方法论映射到这个仓库的工作流。
- `04_platform_terms_and_states.md`
  负责查术语、状态、评分、OS 页面语义。

这 4 篇里：

- 前 3 篇更偏“学习和方法”
- 第 4 篇更偏“查表和释义”

---

## 四份文档分别解决什么问题

### 入门篇

回答这些问题：

- Alpha 到底是什么？
- `Simulate / Check / Submit` 分别是什么？
- 为什么不能只看 Returns？
- `Delay / Decay / Neutralization / Truncation` 应该怎么理解？
- 新手最该先掌握哪些算子？

### 优化篇

回答这些问题：

- `LOW_SHARPE`、`LOW_FITNESS`、`HIGH_TURNOVER` 怎么拆？
- 什么时候该调参数，什么时候该换结构？
- 为什么相关性问题不能靠窗口微调解决？
- 提升 Sharpe、Fitness、Returns、Turnover 的更合理顺序是什么？

### 仓库实战篇

回答这些问题：

- 官网方法论落到这个仓库，应该怎么用？
- 什么情况下该 broad search，什么情况下该 local refine？
- 什么是“结构替换优先”，什么是“近邻参数过密”？
- 模板、结果、文档、数据集说明各自该承担什么角色？

### 术语与状态篇

回答这些问题：

- `IS / OS / OSTEST-PENDING / OSTEST-DECM` 是什么意思？
- 为什么 OS 页是 `N/A`？
- `Meta Score` 在看什么？
- `Universe / Weight / Booksize / NaN / Pasteurize` 怎么理解？
- 页面上的很多词到底是在说什么？

---

## 和其他文档的边界

- 工程结构与运行方式：看 [README.md](../README.md)
- 数据集策略说明：
  - [templates/model51/README.md](../templates/model51/README.md)
  - [templates/model16/README.md](../templates/model16/README.md)
  - [templates/fundamental6/README.md](../templates/fundamental6/README.md)

- `docs/` 负责通用学习路径
- `README.md` 负责工程和使用说明
- `templates/<dataset_id>/README.md` 负责数据集策略和本地经验

---

## 维护原则

- 新增“学习路径”内容，放到这 4 篇主文档里
- 新增“数据集经验”内容，放到 `templates/<dataset_id>/README.md`
- 新增“大量 FAQ 摘录”或“失败案例库”，单独再开专题文档
