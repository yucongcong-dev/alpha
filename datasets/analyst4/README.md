# analyst4

## 当前状态

`analyst4` 是当前现役 explore 数据集。WorldQuant BRAIN 在 USA / TOP3000 / Delay 1 下
将其显示为 `Analyst Estimate Data for Equity`：共 1324 个字段，数据集 Coverage 约 `73%`，
Date Coverage `100%`，最近字段更新于 2026-03。

首轮不做全字段扫描。默认入口是
[eps_surprise_seed](presets/eps_surprise_seed/)，只测试季度实际 EPS 相对分析师预期中位数的
两条结构，共 2 次 simulation。只有 surprise 形成正向基线后，才运行
[eps_dispersion_seed](presets/eps_dispersion_seed/) 检查年度 EPS 预期分歧。

## 官网筛选依据

| 字段 | 含义 | Coverage | Date Coverage | Alpha Count |
|---|---|---:|---:|---:|
| `anl4_fs_actual_1qf_v4_nd_epsr_value` | 季度实际 GAAP EPS | 96% | 100% | 34 |
| `anl4_fs_detail_estimate_1qf_v4_nd_epsr_median` | 季度 EPS 预期中位数 | 86% | 100% | 92 |
| `anl4_fs_detail_estimates_basic_af_v4_nd_eps_high` | 年度 EPS 预期上界 | 99% | 100% | 86 |
| `anl4_fs_detail_estimates_basic_af_v4_nd_eps_low` | 年度 EPS 预期下界 | 99% | 100% | 45 |

## 运行入口

默认 surprise 计划：

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id analyst4 \
  --strategy-profile explore \
  --max-total-simulations 2 \
  --run-name analyst4-eps-surprise-seed \
  --dry-run-plan
```

首次没有本地字段缓存时，离线计划会提示先执行认证运行。确认计划后移除
`--dry-run-plan`。程序只做 simulation 和 Check Submission，正式提交由人工决定。

surprise 出现正向基线后，再显式运行 dispersion：

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

- surprise 两条结构都明显失败 Sharpe/Fitness 时，暂停 `analyst4`，不运行 dispersion。
- 只有至少一条 surprise 结构形成正向基线时，才测试 dispersion。
- dispersion 两条结构都失败时，不继续搜索指导区间、股息或净利润邻近字段。
- 不做符号、相邻窗口、Decay 或 Truncation sweep 来延长失败方向。
- 首轮最多 4 次 simulation，不扩大到完整 1324 字段池。
