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

结合 `2026-07-24` 的第一轮真实运行，当前默认入口又收窄了一次：

- 默认首发模板先不再把 `group/sector zscore` 当主入口
- 首轮字段白名单先聚焦 `mean_skew / mean`
- `historical / parkinson` 暂时降级到第二轮验证

## 第一轮优先字段

当前最建议先从以下家族开小样本，而不是全库混扫：

- `implied_volatility_mean_skew_*`
- `implied_volatility_mean_*`

当前不建议第一轮就把预算主力放到：

- `implied_volatility_call_*`
- `implied_volatility_put_*`
- `historical_volatility_*`
- `parkinson_volatility_*`

原因：

- call/put level 本身更拥挤
- `historical / parkinson` 首轮实盘验证里先暴露出弱信号和拥堵问题
- 先用 `mean` / `mean_skew` 家族，更容易看出结构差异

## 2026-07-24 首轮真实验证

首次真实运行命令：

```bash
cd /Users/boyaa/Downloads/alpha
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id option8 \
  --neutralization MARKET \
  --limit 8 \
  --max-templates-per-field 3 \
  --max-templates-per-family 1 \
  --include-fields-file templates/option8/refine/fields/phase1_core_fields.txt \
  --output results/option8/phase1entryvalidation.json \
  --feedback-output results/option8/phase1entryvalidation.json \
  --no-auto-update-blacklist
```

当前已落地结果摘要：

- 结果文件：`results/option8/phase1entryvalidation_results.jsonl`
- 已落地总数：`3`
- `submittable = 0`
- 当前通过率：`0%`
- `simulated but failed checks = 2 / 3 = 66.7%`
- `runtime error = 1 / 3 = 33.3%`

当前暴露出的失败模式非常集中：

- 质量失败：
  - `LOW_SHARPE = 2`
  - `LOW_FITNESS = 2`
- 流程失败：
  - `CONCURRENT_SIMULATION_LIMIT_EXCEEDED = 1`

已确认的弱组合：

- `parkinson_volatility_30 + option8_sector_zscore_20`
  - 两次都失败
  - `Sharpe = 0.22`
  - `Fitness = 0.05`

这说明首轮主要不是“差一点点”，而是：

- `parkinson_* + sector_zscore` 这条默认入口明显偏弱
- 平台并发配额对 `option8` 首发也比较敏感

所以当前动作已经同步收口为：

- 从默认模板库移除 `option8_sector_zscore_20`
- 第一轮白名单字段回收到 `mean_skew / mean`
- 后续若继续跑真实验证，优先先看 `mean_skew_*` 是否能出现 near-pass

## 推荐命令

先做 dry-run：

```bash
cd /Users/boyaa/Downloads/alpha
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id option8 \
  --neutralization MARKET \
  --limit 8 \
  --include-fields-file templates/option8/refine/fields/phase1_core_fields.txt \
  --dry-run-plan \
  --no-auto-update-blacklist
```

再做收窄后的真实小验证：

```bash
cd /Users/boyaa/Downloads/alpha
PYTHONPATH=src python3.10 -m alpha \
  --dataset-id option8 \
  --neutralization MARKET \
  --limit 8 \
  --max-templates-per-field 3 \
  --max-templates-per-family 1 \
  --include-fields-file templates/option8/refine/fields/phase1_core_fields.txt \
  --output results/option8/phase1entryvalidation.json \
  --feedback-output results/option8/phase1entryvalidation.json \
  --no-auto-update-blacklist
```

## 当前结论

`option8` 现在最适合作为：

- 新主线候选
- 新模板入口
- 新文档/流程验证对象

但它当前还没有完成“主线晋级”。

截至 `2026-07-24`，它更准确的状态是：

- 值得继续探索
- 但必须在更窄字段、更窄模板下继续
- 不适合立刻做大规模 full-run

正确顺序应该是：

1. 先用 `mean_skew / mean` 白名单继续跑小样本
2. 看哪一支先出 near-pass
3. 再决定是否把 `historical / parkinson` 放回第二轮
4. 最后再考虑是否扩到 call/put level 或更长 tenor
