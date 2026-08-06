# analyst4

## 当前状态

`analyst4` 是当前现役 explore 数据集。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1 下
将其显示为 `Analyst Estimate Data for Equity`：共 1324 个字段，数据集 Coverage 约 `73%`，
Date Coverage `100%`，最近字段更新于 2026-03。

季度 reported EPS surprise 的两条结构已经明显失败并关闭，结果见
[research_history.md](research_history.md)。当前默认入口是
[eps_revision_seed](presets/eps_revision_seed/)，只测试事件级 EPS 当前预期相对上次预期的
两条结构，共 2 次 simulation，不扫描完整字段池。

## 官网筛选依据

| 字段 | 含义 | Coverage | Date Coverage | Alpha Count |
|---|---|---:|---:|---:|
| `anl4_fs_basic_splt_v4_nd_eps_estimate` | 当前事件级 EPS 预期 | 96.8% | 100% | 14 |
| `anl4_fs_basic_splt_v4_nd_eps_previosestimate` | 最近修正前 EPS 预期 | 96.3% | 100% | 13 |
| `anl4_fs_detail_estimates_basic_af_v4_nd_eps_high` | 年度 EPS 预期上界 | 99% | 100% | 86 |
| `anl4_fs_detail_estimates_basic_af_v4_nd_eps_low` | 年度 EPS 预期下界 | 99% | 100% | 45 |

## 运行入口

默认 revision 计划：

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id analyst4 \
  --strategy-profile explore \
  --max-total-simulations 2 \
  --run-name analyst4-eps-revision-seed \
  --dry-run-plan
```

首次没有本地字段缓存时，离线计划会提示先执行认证运行。确认计划后移除
`--dry-run-plan`。程序只做 simulation 和 Check Submission，正式提交由人工决定。

revision 两条结构都明显失败后，再显式运行独立 dispersion 验证：

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id analyst4 \
  --template-library-file datasets/analyst4/presets/eps_dispersion_seed/template.json \
  --include-fields-file datasets/analyst4/presets/eps_dispersion_seed/fields.txt \
  --include-templates-file datasets/analyst4/presets/eps_dispersion_seed/templates.txt \
  --strategy-profile explore \
  --max-total-simulations 2 \
  --run-name analyst4-eps-dispersion-seed \
  --dry-run-plan
```

## 停止与扩展规则

- revision 至少一条形成正向基线时，只围绕该结构做 4–6 个局部变体，不运行 dispersion。
- revision 两条结构都明显失败时，只运行 `eps_dispersion_seed` 的 2 次独立验证。
- dispersion 两条结构也失败时，暂停 `analyst4`，不搜索指导区间、股息或净利润邻近字段。
- 不做符号、相邻窗口、Decay 或 Truncation sweep 来延长失败方向。
- 当前 revision 阶段最多 2 次 simulation；包含后续 dispersion 在内总计最多 4 次。
- 不扩大到完整 1324 字段池。
