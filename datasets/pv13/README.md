# pv13

## 当前状态

`pv13` 当前已暂停。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1 下将其
显示为 `Relationship Data for Equity`：数据集 Coverage `79.77%`、Date Coverage `100%`，
共 165 个字段，最近更新于 2025-11。

客户收益传播和客户网络中心性两个独立假设均未形成正向基线，结果见
[research_history.md](research_history.md)。既定停止条件已满足，因此当前没有默认运行入口，
也不遍历完整字段池。

## 官网筛选依据

字段元数据于 2026-08-06 从 WorldQuant BRAIN 官方接口读取。

| 字段 | 含义 | Coverage | Alpha Count | User Count |
|---|---|---:|---:|---:|
| `rel_ret_cust` | 客户公司平均一日收益 | 49.21% | 809 | 370 |
| `pv13_ustomergraphrank_auth_rank` | 客户网络 HITS authority score | 79.06% | 826 | 583 |

`rel_ret_cust` 用于验证供应链收益传播；`pv13_ustomergraphrank_auth_rank` 用于验证客户网络
中心性。两者 Alpha Count 接近且经济含义独立，适合各运行一个简单种子。

## 当前边界

- 暂停 `pv13`，不再运行已完成的 relationship seed。
- 不扩大到其他关系字段，不扫描完整 165 字段池。
- 不做符号、相邻窗口、Decay 或 Truncation sweep。
- 只有出现新的独立经济假设或平台字段发生实质更新时，才重新建立小范围 preset。
