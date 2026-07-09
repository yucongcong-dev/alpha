# Docs Index

这份索引页是 `docs/` 的唯一主入口：既负责学习顺序，也负责按问题快速定位文档。

## 推荐阅读顺序

第一次系统看这个仓库，建议按下面顺序读：

1. [01_beginner_guide.md](01_beginner_guide.md)
2. [02_optimization_guide.md](02_optimization_guide.md)
3. [03_repo_practice_guide.md](03_repo_practice_guide.md)
4. [04_platform_terms_and_states.md](04_platform_terms_and_states.md)

如果你已经在跑实验，通常直接从第 2 篇开始更合适，再补第 3 篇。

## 快速入口

### 我是第一次接触这个仓库

按“推荐阅读顺序”直接往下看。

### 我现在卡在某个结果，不知道怎么解释

优先看：

1. [02_optimization_guide.md](02_optimization_guide.md)
2. [04_platform_terms_and_states.md](04_platform_terms_and_states.md)

### 我想知道平台页面上的术语和状态是什么意思

直接看：

- [04_platform_terms_and_states.md](04_platform_terms_and_states.md)

### 我想知道这个仓库现在建议怎么跑

优先看：

1. [03_repo_practice_guide.md](03_repo_practice_guide.md)
2. 数据集说明：
- [../templates/model16/README.md](../templates/model16/README.md)
- [../templates/model51/README.md](../templates/model51/README.md)
- [../templates/fundamental6/README.md](../templates/fundamental6/README.md)

## 按问题找文档

| 你的问题 | 最该看 |
|---|---|
| Alpha 是什么？ | [01_beginner_guide.md](01_beginner_guide.md) |
| Delay / Decay / Neutralization 是什么？ | [01_beginner_guide.md](01_beginner_guide.md) |
| 为什么不能只看 Returns？ | [01_beginner_guide.md](01_beginner_guide.md) |
| `LOW_SHARPE` / `LOW_FITNESS` 怎么拆？ | [02_optimization_guide.md](02_optimization_guide.md) |
| 什么时候该调参数，什么时候该换结构？ | [02_optimization_guide.md](02_optimization_guide.md) |
| `IS / OS / OSTEST-PENDING / N/A` 是什么意思？ | [04_platform_terms_and_states.md](04_platform_terms_and_states.md) |
| `Meta Score / Universe / Weight / NaN / Pasteurize` 是什么？ | [04_platform_terms_and_states.md](04_platform_terms_and_states.md) |
| 官网方法论怎么落到这个仓库？ | [03_repo_practice_guide.md](03_repo_practice_guide.md) |
| 当前某个数据集该怎么跑？ | `templates/<dataset_id>/README.md` |

## 按角色找文档

### 新手

- [01_beginner_guide.md](01_beginner_guide.md)
- [02_optimization_guide.md](02_optimization_guide.md)

### 研究者

- [02_optimization_guide.md](02_optimization_guide.md)
- [03_repo_practice_guide.md](03_repo_practice_guide.md)

### 排障 / 查表

- [04_platform_terms_and_states.md](04_platform_terms_and_states.md)

### 数据集维护者

- [../templates/model16/README.md](../templates/model16/README.md)
- [../templates/model51/README.md](../templates/model51/README.md)
- [../templates/fundamental6/README.md](../templates/fundamental6/README.md)

## 文档边界

- `docs/`：通用学习路径、平台概念、查表文档
- `README.md`：工程入口、运行方式、项目结构
- `templates/<dataset_id>/README.md`：数据集策略与本地经验

如果后面继续扩文档，优先先判断内容属于哪一层，再决定写到哪里。
