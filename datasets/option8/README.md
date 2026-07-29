# option8 说明

## 定位
`option8` 当前是最适合接到仓库下一阶段的新数据集入口。

这里的判断基于 `2026-07-24` 对官方 `data-sets` / `data-fields` 接口的实查：

- 数据集：`option8`
- 官方名称：`Volatility Data`
- 类别：`Option`
- USA / D1 / TOP3000：
  - `coverage = 0.9698`
  - `dateCoverage = 1.0`
  - `fieldCount = 64`
  - `userCount = 29420`
  - `alphaCount = 156394`

字段结构也很干净：

- `64 / 64` 全部是 `MATRIX`
- 没有 `VECTOR`
- 字段家族可直接分成：
  - `historical_volatility_*`
  - `parkinson_volatility_*`
  - `implied_volatility_call_*`
  - `implied_volatility_put_*`
  - `implied_volatility_mean_*`
  - `implied_volatility_mean_skew_*`

## 为什么先做它

和当前仓库已经验证过的几条线相比：

- 比 `model51` 更适合继续开新研究，因为它不是“已知方向多轮不抬升”的状态
- 比 `model16` 更适合开新入口，因为它当前不是“稳定不过线”的老天花板
- 比 `analyst4` 更适合先落仓库，因为它是纯 `MATRIX`，接入复杂度更低

更重要的是，它和本地已经同步的官方教程方向高度一致：

- Option/IV 教程强调高 coverage、`MATRIX only`
- 不要长 backfill
- 不要把原始 vol level 一股脑再做重平滑
- 更适合先看结构、skew、term shape，而不是只盯单一波动率水平

虽然本地教程文档引用的是 `Option6 Implied Volatility` 页面，但到 `2026-07-24`
你账号当前官方数据集列表里，真正可见、且与这套教程最贴近的候选是 `option8`。
这是基于官方 API 结果做出的映射判断。

## 当前策略

默认入口故意保持很窄：

- `backfill = 5`
- `winsorize(std=4)`
- 少量 `zscore / decay / spread / delta-over-std`
- 默认模板库闭合，不自动外扩 MATRIX 邻居

这套默认库不是最终答案，而是第一轮“研究入口”。

结合 `2026-07-24` 和 `2026-07-29` 的真实运行，当前策略已经从入口探索收敛为：

- 字段：`implied_volatility_mean_60`
- 结构：`group_rank(..., subindustry)`
- 时间窗口：`ts_zscore(..., 60)`
- 平台设置：继续使用 `Decay = 4`、`Neutralization = MARKET`

现役资产统一收口在 `presets/subindustry_refine/`，不再保留每轮实验的临时 preset。
弱实验结论写入本文，真实运行明细保留在本地 run/feedback 产物中。

## 当前优先字段

当前只保留一个主字段：

- `implied_volatility_mean_60`

`implied_volatility_mean_20` 降级为诊断对照，不再与主字段平分预算。

当前不建议第一轮就把预算主力放到：

- `implied_volatility_call_*`
- `implied_volatility_put_*`
- `implied_volatility_mean_skew_*`

原因：

- call/put level 本身更拥挤
- `mean_skew_*` 的 plain `ts_zscore` 多数为负 Sharpe，spread 虽能转正但仍远离门槛
- `mean_60` 在 subindustry + 60 日窗口下形成了当前唯一连续抬升的路径

## 2026-07-24 首轮真实验证

首次真实运行命令：

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id option8 \
  --neutralization MARKET \
  --limit 8 \
  --max-templates-per-field 3 \
  --max-templates-per-family 1 \
  --include-fields-file datasets/option8/presets/phase1_core/fields.txt \
  --run-name phase1entryvalidation \
  --no-auto-update-blacklist
```

当前完整结果摘要：

- 已落地总数：`38`
- `submittable = 0`
- `LOW_SHARPE + LOW_FITNESS = 36`
- 并发配额错误：`2`

当前暴露出的失败模式非常集中：

- 质量失败：
  - `LOW_SHARPE = 36`
  - `LOW_FITNESS = 36`
- 流程失败：
  - `CONCURRENT_SIMULATION_LIMIT_EXCEEDED = 2`

首轮最好组合：

- `parkinson_volatility_20 + option8_sector_zscore_20`
  - `Sharpe = 0.76`
  - `Fitness = 0.32`
- `parkinson_volatility_90 + option8_ts_zscore_20`
  - `Sharpe = 0.62`
  - `Fitness = 0.30`

这轮说明整体仍远离提交门槛，但不能根据 `parkinson_volatility_30` 的单点弱结果，
把整个 sector 分组结构判定为无效。对 `parkinson_volatility_20`，sector 版本反而是首轮最好结果。

## 2026-07-24 第二轮 mean focus 验证

`phase2_mean_focus` 共落地 `34` 条结果：

- `submittable = 0`
- `LOW_SHARPE = 34`
- `LOW_FITNESS = 34`
- `LOW_SUB_UNIVERSE_SHARPE = 26`

当前最好基线：

- `implied_volatility_mean_60 + option8_ts_zscore_20`
  - `Sharpe = 0.77`
  - `Fitness = 0.30`
- `implied_volatility_mean_20 + option8_ts_zscore_20`
  - `Sharpe = 0.74`
  - `Fitness = 0.27`

已经可以暂停的分支：

- `decay_zscore_20_5`：持续弱于 plain `ts_zscore_20`
- `zscore_spread_20_120`：在 mean level 上明显退化
- `mean_skew_*`：plain 版本多数为负 Sharpe，spread 版本虽转正但仍没有 near-pass

这轮结果随后触发了受控的分组层级验证，完整结论见下一节。

## 2026-07-29 subindustry 收敛验证

本轮通过 VSCode 的 `alpha` 项目终端完成了五组真实实验，共 `20` 条 simulation，
全部正常返回，`errors = 0`，但仍然 `submittable = 0`。

### 分组层级比较

固定 `ts_zscore(..., 20)` 后，分组越细，结果越强：

| 字段 | plain Sharpe/Fitness | sector | industry | subindustry |
| --- | --- | --- | --- | --- |
| `mean_20` | `0.74 / 0.27` | `1.04 / 0.40` | `1.19 / 0.45` | `1.39 / 0.51` |
| `mean_60` | `0.77 / 0.30` | `1.03 / 0.42` | `1.21 / 0.48` | `1.34 / 0.49` |

结论：subindustry 是有效结构，不再回退到 plain/sector/industry。

### 已否定的降换手方案

- 平台 `Decay 4 -> 10`
  - mean20：Sharpe `1.39 -> 0.98`，Fitness `0.51 -> 0.39`
  - mean60：Sharpe `1.34 -> 1.06`，Fitness `0.49 -> 0.44`
  - 换手虽从约 `0.41` 降到约 `0.26`，但收益和 Sharpe 同时下降
- `trade_when(abs(zscore) > 0.5/1.0, ...)`
  - 四条全部弱于无门控基线
  - 最好只有 Sharpe `1.23`、Fitness `0.47`

结论：当前信号依赖连续更新，不能靠全局平滑或事件门控直接解决 Fitness。

### zscore 窗口比较

延长时间窗口是本轮唯一持续有效的杠杆：

| 字段 | 窗口 | Sharpe | Fitness | Returns | Turnover |
| --- | ---: | ---: | ---: | ---: | ---: |
| `mean_60` | 20 | `1.34` | `0.49` | `5.39%` | `40.46%` |
| `mean_60` | 40 | `1.55` | `0.71` | `6.87%` | `32.81%` |
| `mean_60` | 60 | `1.58` | `0.78` | `7.46%` | `30.33%` |
| `mean_60` | 90 | 通过 `1.25` | `0.68` | - | - |
| `mean_60` | 120 | `1.07` | `0.50` | - | - |

当前最佳 Alpha：

- Alpha ID：`2rNW02YN`
- expression：`group_rank(ts_zscore(winsorize(ts_backfill(implied_volatility_mean_60, 5), std=4), 60), subindustry)`
- Sharpe：`1.58`
- Fitness：`0.78`
- Returns：`7.46%`
- Turnover：`30.33%`
- Sub-universe Sharpe：`0.91`，检查通过
- concentrated weight：检查通过

90/120 日结果已经回落，因此当前局部最优窗口固定为 `60`，不再继续向更长窗口外扩。

## 推荐命令

复查当前最佳策略资产：

```bash
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id option8 \
  --neutralization MARKET \
  --template-library-file datasets/option8/presets/subindustry_refine/template.json \
  --include-fields-file datasets/option8/presets/subindustry_refine/fields.txt \
  --max-templates-per-field 1 \
  --max-templates-per-family 1 \
  --dry-run-plan \
  --run-name option8_subindustry_refine \
  --no-auto-update-blacklist
```

该表达式已经完成真实验证，不应仅改名后重复消耗 simulation 配额。

## 当前结论

`option8` 已从 broad-search 候选收敛为一条明确的观察线，但还没有完成“主线晋级”。

截至 `2026-07-29`，它更准确的状态是：

- 当前最佳结构已确定为 `mean_60 + subindustry + zscore(60)`
- Sharpe、子市场 Sharpe 和权重检查已通过
- 唯一主要失败项仍是 `LOW_FITNESS = 0.78 < 1.0`
- 不适合立刻做大规模 full-run

正确顺序应该是：

1. 保留当前最佳 Alpha 和 `subindustry_refine` 作为基线
2. 停止 decay、trade_when、90/120 日长窗口和 broad-search
3. 下一轮只有引入新的经济信息时才继续，例如 term-structure/相对价值组合
4. 不再靠 50/70 等密集窗口微调追逐 Fitness，避免围绕单个样本过拟合
