# analyst4

## 当前状态

`analyst4` 是当前现役 explore 数据集。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1 下
将其显示为 `Analyst Estimate Data for Equity`：共 1324 个字段，数据集 Coverage 约 `73%`，
Date Coverage `100%`，最近字段更新于 2026-03。

季度 reported EPS surprise 与事件级 EPS revision 均已明显失败并关闭，结果见
[research_history.md](research_history.md)。当前默认入口是最后一个独立假设
[eps_dispersion_seed](presets/eps_dispersion_seed/)，只测试年度 EPS 预期上下界差异的两条
结构，共 2 次 simulation，不扫描完整字段池。

## 官网筛选依据

| 字段 | 含义 | Coverage | Date Coverage | Alpha Count |
|---|---|---:|---:|---:|
| `anl4_fs_detail_estimates_basic_af_v4_nd_eps_high` | 年度 EPS 预期上界 | 99% | 100% | 86 |
| `anl4_fs_detail_estimates_basic_af_v4_nd_eps_low` | 年度 EPS 预期下界 | 99% | 100% | 45 |

## 运行入口

默认 dispersion 计划：

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id analyst4 \
  --strategy-profile explore \
  --max-total-simulations 2 \
  --run-name analyst4-eps-dispersion-seed \
  --dry-run-plan
```

首次没有本地字段缓存时，离线计划会提示先执行认证运行。确认计划后移除
`--dry-run-plan`。程序只做 simulation 和 Check Submission，正式提交由人工决定。

## 停止与扩展规则

- dispersion 至少一条形成正向基线时，只围绕该结构做 4–6 个局部变体。
- dispersion 两条结构都失败时，暂停 `analyst4`，不搜索指导区间、股息或净利润邻近字段。
- 不做符号、相邻窗口、Decay 或 Truncation sweep 来延长失败方向。
- 当前 dispersion 阶段最多 2 次 simulation。
- 不扩大到完整 1324 字段池。
