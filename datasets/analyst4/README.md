# analyst4

## 当前状态

`analyst4` 当前已暂停。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1 下
将其显示为 `Analyst Estimate Data for Equity`：共 1324 个字段，数据集 Coverage 约 `73%`，
Date Coverage `100%`，最近字段更新于 2026-03。

EPS surprise、revision、dispersion，以及两个独立的销售方向均未形成正向基线，结果见
[research_history.md](research_history.md)。销售指引和销售预期修正完成后，已经满足该数据集的
停止规则，因此当前没有默认运行入口，也不扫描完整字段池。

## 官网筛选依据

| 字段 | 含义 | Coverage | Date Coverage | Alpha Count |
|---|---|---:|---:|---:|
| `anl4_fs_guidances_basic_af_nd_sales_maxguidance` | 公司年度销售指引上界 | 100% | 100% | 1 |
| `anl4_fs_guidances_basic_af_nd_sales_minguidance` | 公司年度销售指引下界 | 100% | 100% | 17 |
| `sales_estimate_value` | 当前事件级销售预期 | 99.3% | 100% | 59 |
| `sales_previous_estimate_value` | 上次事件级销售预期 | 98.7% | 100% | 39 |

## 当前边界

- 暂停 `analyst4`，不再运行已完成的销售 preset。
- 不研究 recommendation 邻域，不做符号、相邻窗口、Decay 或 Truncation sweep。
- 不扩大到完整 1324 字段池。
- 只有出现新的独立经济假设或平台字段发生实质更新时，才重新建立小范围 preset。
