# news12

## 当前状态

`news12` 当前已暂停。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1 下
将其显示为 `US News Data`：数据集 Coverage `82.28%`、Date Coverage `100%`，
共 875 个字段，最近更新于 2026-03。

新闻后 30 分钟价格反应明显失败；首发新闻新颖度的水平种子虽获得
Sharpe `0.87`、Fitness `0.23`，但后续 4 个有效结构均未形成 near-pass。既定停止条件
已满足，因此当前没有默认运行入口，也不遍历完整字段池。完整结果见
[research_history.md](research_history.md)。

## 官网筛选依据

字段元数据于 2026-08-07 从 WorldQuant BRAIN 官方接口读取。

| 字段 | 含义 | Coverage | Alpha Count | User Count |
|---|---|---:|---:|---:|
| `nws12_mainz_30_min` | 新闻发布后 30 分钟价格变化 | 96.87% | 37 | 28 |
| `nws12_mainz_newrecord` | 新闻是否为首次出现而非重复记录 | 97.41% | 53 | 45 |

两者都是 VECTOR 字段，必须先用 `vec_avg` 转为 MATRIX。前者验证短期反应后的
延续或反转，后者验证首发新闻相对重复新闻的信息差异。不使用依赖事后最高价、
最低价或有利仓位标签的字段。

## 当前边界

- 暂停 `news12`，不再运行已完成的 newrecord refine。
- 不扩大到其他价格反应别名字段，不扫描完整 875 字段池。
- 不使用 `LS`、`advantageous_position` 等事后有利仓位标签。
- 不做符号、相邻窗口、Decay 或 Truncation sweep。
- 只有出现新的独立经济假设或平台字段发生实质更新时，才重新建立小范围 preset。
