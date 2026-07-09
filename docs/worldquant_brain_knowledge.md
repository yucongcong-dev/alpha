# WorldQuant BRAIN 学习地图

> 这份文件现在只负责做“总导航”。
> 详细内容已拆成 `入门篇 / 优化篇 / 仓库实战篇`，避免所有知识继续堆在一个文档里。

---

## 推荐阅读顺序

如果你是第一次系统学习 BRAIN，建议按下面顺序阅读：

1. [01_beginner_guide.md](01_beginner_guide.md)
   先理解 Alpha 是什么、平台主流程是什么、结果怎么看、常用设置和基本算子怎么理解。
2. [02_optimization_guide.md](02_optimization_guide.md)
   再理解 `Sharpe / Fitness / Turnover / Correlation` 的诊断逻辑，以及常见失败项该怎么优化。
3. [03_repo_practice_guide.md](03_repo_practice_guide.md)
   最后把官网知识映射回本仓库，形成稳定的研究和迭代习惯。

如果你已经在跑这个仓库，建议直接从第 2 篇开始，再补第 3 篇。

---

## 三份文档分别解决什么问题

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

---

## 和其他文档的关系

- 工程结构与运行方式：看 [README.md](../README.md)
- 数据集策略说明：
  - [templates/model51/README.md](../templates/model51/README.md)
  - [templates/model16/README.md](../templates/model16/README.md)
  - [templates/fundamental6/README.md](../templates/fundamental6/README.md)

这里的边界要尽量清晰：

- `docs/` 负责通用学习路径
- `README.md` 负责工程和使用说明
- `templates/<dataset_id>/README.md` 负责数据集策略和本地经验

---

## 官方资料入口

这次整理时重点参考并核对过这些官方资料：

- [What are the characteristics of a good Alpha?](https://api.worldquantbrain.com/faqs/characteristics-good-alphas)
- [I have felt a lack of information on the fitness of an Alpha](https://api.worldquantbrain.com/faqs/fitness-alphas)
- [Please explain Decay and Delay in detail](https://api.worldquantbrain.com/faqs/decay-delay)
- [Is the delay days in trading days or calendar days?](https://api.worldquantbrain.com/faqs/delay-is-in-trading-days)
- [Is there a scenario where delay-1 can be more useful than delay-0?](https://api.worldquantbrain.com/faqs/delay1-delay0-implication)
- [Difference between delay and decay in terms of no of days?](https://api.worldquantbrain.com/faqs/delay-decay)
- [What’s the difference between the three market neutralization methods?](https://api.worldquantbrain.com/faqs/difference-between-neutralization-groups)
- [Will good Alpha be developed without neutralization?](https://api.worldquantbrain.com/faqs/alpha-with-no-neutralization)
- [Does neutralization always reduce standard deviation of returns?](https://api.worldquantbrain.com/faqs/neutralization-reduces-standard-deviation-of-return)
- [I have made some Alphas ... turnover tends to close to 90%](https://api.worldquantbrain.com/faqs/turnover-reduction-methods)
- [If I change the value of decay from 1 to 5 ... over-fit?](https://api.worldquantbrain.com/faqs/decay_overfit)
- [Can a user check correlation among his own Alphas?](https://api.worldquantbrain.com/faqs/self-correlation)
- [How is correlation tested?](https://api.worldquantbrain.com/faqs/how-is-correlation-tested)
- [First ... how to get the past values of some data?](https://api.worldquantbrain.com/faqs/debt-liabilities-past-value)
- [FASTEXPR operators](https://api.worldquantbrain.com/operators?language=FASTEXPR)
- [Running your first Alpha](https://platform.worldquantbrain.com/learn/documentation/create-alphas/running-your-first-alpha)
- [19 Alpha Examples for Beginners](https://platform.worldquantbrain.com/learn/documentation/create-alphas/19-alpha-examples)

---

## 当前建议

后续维护时，尽量遵守这条规则：

- 新增“学习路径”内容，放到这三篇主文档里
- 新增“数据集经验”内容，放到 `templates/<dataset_id>/README.md`
- 新增“大量 FAQ 摘录”或“失败案例库”，单独再开专题文档

这样文档体系才不会再次回到“信息很多，但阅读顺序混乱”的状态。
