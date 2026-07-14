# model51 说明

## 定位
`model51` 当前更适合被当作风险/系统性度量风格的数据集。

模板库主方向故意围绕以下特征展开：
- 持续性
- 长窗口归一化
- 市场/行业中性化
- 波动率/市值 bucket 分组
- 避免短窗方向性算子

## 官方口径
- 和 `model16` 一样，当前本地没有拿到 `model51` 的专属官方模板手册。
- 可直接依赖的官方信息，仍然是 BRAIN 通用文档里对 grouped、neutralized、structured expressions 的支持。

## Neutralization 与流动性建议

`model51` 属于 Model Dataset，官网建议根据子类别比较多种 Neutralization。结合其风险字段语义：

- `Market` 用来先移除全市场共同风险
- `Industry / Subindustry` 用来判断风险描述子是否只是行业结构
- `bucket(rank(cap), ...)` 可以构造 size 分层，bucket 使用前应 `densify()`
- 若最不流动 50% after-cost Sharpe 较弱，可按 `cap` 或平均成交量划分流动性组，并给低流动性组更长 Decay
- 有明确 size / liquidity 风险向量时，可在专项 refine 中尝试 `vector_neut()`

模板内中性化和 settings 层中性化不能无意识叠加。默认库应让每个候选明确属于
“表达式中性化”或“设置中性化”中的一种。

## 本地证据

结构性判断：
- 从字段命名和行为看，它更像风险或系统性描述子，而不是经典反应型 alpha 输入。
- 因此，短窗 `delta`、`mean_diff`、大范围 momentum 扫描，都不适合作为默认模板。

运行证据：
- 短窗和泛化 `delta` 家族已经弱到在策略中被显式禁用。
- 整理后的长窗口、带 market/industry neutralization 的模板，更符合这类数据的预期用法。
- 在 `checksubmit` 流程改成等待 `SELF_CORRELATION` 终态之后，当前风险字段分支已不再像可直接生产的候选：
  - 近期对 `unsystematic_risk_last_*` 和 `systematic_risk_last_*` 的重查里，self-correlation 都没能在轮询预算内进入终态
- 当前工作流会把这些结果保留为 `pending_self_correlation`，而不是伪装成普通 simulated failure，方便后续单独重查

公开脚本启发：
- bucket 分组值得吸收，因为它更适合做稳定的相对比较。
- 共享的预处理风格也说明：长 backfill 后再做 winsorize 是合理的。

## 当前模板方向

预处理：
- `504` 天 backfill，加 `winsorize(std=4)`。

当前默认库目标：
- 只保留少量、结构上真正不同的生产候选
- 避免把围绕同一条拥挤 risk 分支的近邻窗口变体塞满默认队列

默认主干形态：
- 一条一阶长窗口 `ts_zscore`
- 一条 `subindustry` 分组 zscore
- 一条 `cap-ratio` 模板，加一条 `bucket-cap-ratio` 模板
- 一条 mean-reversion spread，避免队列过度集中在纯 zscore/risk 变换上

已移除内容：
- 只做 `stddev` 的默认模板已移出主模板库，因为它们没有新的 bucket/risk-aware 结构有针对性。
- 大多数额外的 grouped/decay/window 邻居，现在应该被看作 refine 或诊断输入，而不是默认 broad-search 种子。
- `IR` 也不再留在最小默认队列中，而是下沉到 `refine/` 的 ratio 分支之后。

字段排序：
- 拥挤的 risk 字段，现在通过 `alphaCount/userCount` 的 crowding penalty 被显式降权，而不是因为“历史常见”就自动排到前面。

## 不建议做的事

- 不要因为风险字段“历史上常见”，就继续把 broad-search 预算砸在当前偏弱的 risk-field 家族上。
- 不要把额外 grouped/decay/window 邻居重新塞回默认队列，制造“伪多样性”。
- 不要因为过去相邻分支曾有 `submittable=true`，就在当前更严格的 self-correlation 门槛下继续高估它们。

## 推荐流程

Broad exploration：
- `model51` 已经展示出足够的结构性，因此大范围模板扫库应继续保持窄而精。
- 优先使用数据集专属模板库，而不是共享 base library。
- 在 self-correlation 行为没有理解清楚前，不要继续把 broad-search 预算浪费在当前风险字段家族上。
- 如果还需要做 broad sweep，也应该把它视为生成 `pending_self_correlation` backlog 的诊断动作，而不是主要的 alpha 挖掘动作。

Focused refine：
- 历史上的 focused fixtures 仍然保留在仓库中，方便审计，但目前更适合被视为诊断输入，而不是优先生产 refine 默认。
- [refine/local_refine_round7.json](/Users/boyaa/Downloads/alpha/templates/model51/refine/local_refine_round7.json) 保留了一小组围绕同一风险分支的已验证本地 refine 变体。
- [refine/local_refine_industry_decay_triplet_round9.json](/Users/boyaa/Downloads/alpha/templates/model51/refine/local_refine_industry_decay_triplet_round9.json) 和 [refine/local_refine_market_decay_triplet_round9.json](/Users/boyaa/Downloads/alpha/templates/model51/refine/local_refine_market_decay_triplet_round9.json) 保留了围绕 `ts_zscore(..., 63)` 分支的更紧凑 `10/15/20` decay 扫描。
- [refine/local_refine_decay_density_round10.json](/Users/boyaa/Downloads/alpha/templates/model51/refine/local_refine_decay_density_round10.json) 保留了同一分支上更密的 `8/12/18/24` decay 扫描。
- [refine/local_refine_window_sweep_round11.json](/Users/boyaa/Downloads/alpha/templates/model51/refine/local_refine_window_sweep_round11.json) 比较了同一 decay 分支上的邻近 `ts_zscore` 窗口 `56/63/70`。
- [refine/fields/unsystematic_group_branch_round12_fields.txt](/Users/boyaa/Downloads/alpha/templates/model51/refine/fields/unsystematic_group_branch_round12_fields.txt) 和 [refine/group_branch_round12_templates.txt](/Users/boyaa/Downloads/alpha/templates/model51/refine/group_branch_round12_templates.txt) 记录了 unsystematic 分支上的非 decay 重查。
- [refine/fields/systematic_branch_round13_fields.txt](/Users/boyaa/Downloads/alpha/templates/model51/refine/fields/systematic_branch_round13_fields.txt) 和 [refine/systematic_branch_round13_templates.txt](/Users/boyaa/Downloads/alpha/templates/model51/refine/systematic_branch_round13_templates.txt) 记录了对应的 systematic 分支重查。

Refine pack 约定：
- `library.json` 保持为默认、窄化后的生产模板库。
- 定向本地 sweep 保留在 `refine/` 下。
- 需要使用 refine pack 时，显式通过 `--template-library-file templates/model51/refine/<file>.json` 加载。
- 当前 broadening pack 是 `templates/model51/refine/broad_search_neighbors.json`
- 如果某个 focused experiment 需要稳定的手工字段缓存，把它放在 `refine/fields/`，而不是 `cache/`
- grouped `market` zscore 家族、额外 decay-window 家族，以及 bucket-volatility 变体，在失去默认队列资格后，都应放在这里
- refine pack 现在应该优先围绕新的默认主干展开：
  - `ts_zscore_120`
  - `group_zscore_subindustry_120`
  - `ratio_cap_zscore_60/120`
  - `bucket_cap_ratio_zscore_60/120`
  - `mean_reversion_60/120_252`

当前这轮更窄聚焦背后的证据：
- 历史运行中，某些风险字段分支曾经出现过 `submittable=true` 或 near-pass，但在 self-correlation 门槛收紧后，这些信号本身已不足以支撑继续扩预算。
- `beta_last_*_spy` 和 `correlation_last_*_spy` 在 broad 与 focused 运行里都持续偏弱，因此已移出默认 refine 白名单。
- 当前 `focused_fields.txt` / `focused_templates.txt` 因而只保留仍值得试探的 `systematic/unsystematic risk` 主分支，并把更弱的 `beta/correlation` spy 分支剔除。
- `window_sweep_round11_selfcorr_recheck` 重新验证了 `unsystematic_risk_last_360_days` 的 decay-window 分支（`market/industry`，窗口 `56/63/70`），全部 6 条候选都因 `SELF_CORRELATION` 一直 `PENDING` 被排除。
- `group_branch_round12_recheck` 随后在 `unsystematic_risk_last_60/90/360_days` 上使用非 decay 的 group/bucket/time-series 模板重试，前 9 条候选仍然因为同样原因被排除。
- `systematic_branch_round13_recheck` 又在 `systematic_risk_last_30/60/90_days` 上重复这些非 decay 模板家族，全部 9 条候选同样因为 `SELF_CORRELATION` 未终态而被排除。
- `focused_validation` 则重新以更窄的 `5 fields x 4 templates = 20` 验证集运行，所有候选都拿到了终态结果。这样之前的模糊点被去掉了：当前主阻塞已经不再是 `SELF_CORRELATION`，而是普通质量门槛，尤其是 `LOW_FITNESS`。
- 在该 focused validation 中，`unsystematic_risk_last_60_days` 成为唯一还足够接近、值得继续投入预算的分支。当前本地前三条最好结果分别是：
  - `model51_ts_zscore_120`：`fitness=0.85`
  - `model51_bucket_cap_zscore_120`：`fitness=0.83`
  - `model51_ts_rank_120`：`fitness=0.78`
- 相比之下，`systematic_risk_last_*` 在同一模板包下整体偏弱，因此下一轮本地 refine 应直接放弃它，把预算只投给 `unsystematic_risk_last_60_days`
- [refine/fields/unsystematic60_refine_round14_fields.txt](/Users/boyaa/Downloads/alpha/templates/model51/refine/fields/unsystematic60_refine_round14_fields.txt) 和 [refine/unsystematic60_refine_round14.json](/Users/boyaa/Downloads/alpha/templates/model51/refine/unsystematic60_refine_round14.json) 记录了这一步本地 refine。该模板包保留了三条 near-pass 核心模板，并补上 `ratio_cap` / `bucket_ratio` / `60-day neighbor` 这些上轮 focused validation 没有真正展开的结构邻居。

到当前阶段，优先动作已经不再是 self-correlation 诊断性重查。更紧的 `focused_validation` 已经证明，最有希望的 live 分支可以正常走完流程，现在主要卡在 `LOW_FITNESS / LOW_SHARPE`，因此下一笔预算更适合继续本地 refine，而不是继续做更广的轮询实验。

建议的 round14 refine 命令：

```bash
python3 -m alpha run \
  --dataset-id model51 \
  --include-fields-file templates/model51/refine/fields/unsystematic60_refine_round14_fields.txt \
  --template-library-file templates/model51/refine/unsystematic60_refine_round14.json \
  --limit 1 \
  --max-templates-per-field 7 \
  --max-templates-per-family 2 \
  --max-concurrent-simulations 2 \
  --max-concurrent-creates 1 \
  --output results/model51/unsystematic60_refine_round14.json \
  --feedback-output results/model51/focused_validation.json \
  --no-auto-update-blacklist
```

当前判断：
- `beta/correlation` 家族依旧偏弱，不会因为之前风险分支卡住过就自动变得更有吸引力。
- 现在信号最强、最值得继续试的分支，已经比较清楚地收敛到 `unsystematic_risk_last_60_days`。
- 它当前的差距主要在质量抬升，而不是流程闭环。
- 历史上相邻风险分支曾出现过 `submittable=true`，仍要谨慎看待，但它们已不是当前行动的核心依据。
- 因此，`model51` 还值得做一轮小型本地 refine，而不是再做一次 broad exploration sweep。
- 操作上意味着：
  - 继续把搜索收缩在最优 unsystematic 分支附近
  - 有限预算优先给结构邻居，而不是更宽的字段覆盖
  - 只有当 round14 本地 refine 明确失败后，再回头做更广的诊断

## 待确认问题

- 只有未来又出现 `PENDING` 卡死时，才再开一轮以 self-correlation 为中心的诊断；它不再是当前 round14 路径的默认下一步。
- 只有后续结果表明风险字段对高波动/低波动 regime 有明显分裂时，才值得补 regime-aware 变体。
- 继续复查，是否能把某个一阶 rank/zscore 模板下沉到 grouped bucket 变体之后。
