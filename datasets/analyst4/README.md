# analyst4

## 当前状态

`analyst4` 是当前现役 explore 数据集。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1 下
将其显示为 `Analyst Estimate Data for Equity`：共 1324 个字段，数据集 Coverage 约 `73%`，
Date Coverage `100%`，最近字段更新于 2026-03。

EPS surprise、revision 和 dispersion 均已失败并关闭，结果见
[research_history.md](research_history.md)。这些实验不能代表非 EPS 字段。当前默认入口是
[sales_guidance_seed](presets/sales_guidance_seed/)，只测试公司年度销售指引上下界差异的
两条结构，共 2 次 simulation，不扫描完整字段池。

## 官网筛选依据

| 字段 | 含义 | Coverage | Date Coverage | Alpha Count |
|---|---|---:|---:|---:|
| `anl4_fs_guidances_basic_af_nd_sales_maxguidance` | 公司年度销售指引上界 | 100% | 100% | 1 |
| `anl4_fs_guidances_basic_af_nd_sales_minguidance` | 公司年度销售指引下界 | 100% | 100% | 17 |
| `sales_estimate_value` | 当前事件级销售预期 | 99.3% | 100% | 59 |
| `sales_previous_estimate_value` | 上次事件级销售预期 | 98.7% | 100% | 39 |

## 运行入口

默认 sales guidance 计划：

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id analyst4 \
  --strategy-profile explore \
  --max-total-simulations 2 \
  --run-name analyst4-sales-guidance-seed \
  --dry-run-plan
```

首次没有本地字段缓存时，离线计划会提示先执行认证运行。确认计划后移除
`--dry-run-plan`。程序只做 simulation 和 Check Submission，正式提交由人工决定。

## 停止与扩展规则

- sales guidance 至少一条形成正向基线时，只围绕该结构做 4–6 个局部变体。
- sales guidance 两条都失败时，只运行 `sales_revision_seed` 的 2 次独立验证。
- sales revision 两条也失败时，暂停 `analyst4`，不研究 recommendation 邻域。
- 不做符号、相邻窗口、Decay 或 Truncation sweep 来延长失败方向。
- 当前 sales guidance 阶段最多 2 次 simulation；包含条件 sales revision 在内最多 4 次。
- 不扩大到完整 1324 字段池。
