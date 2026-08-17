# Alpha Runner 运行与本地资产 Reference

> 负责 CLI 运行路径、字段调度、缓存、续跑、结果文件、配置和清理。字段研究方法仍见
> [02 数据研究与仓库实践](02_research_and_data_guide.md)。

以下命令默认在已激活的 Python 3.10+ 虚拟环境中运行，因此统一使用 `python`。
macOS 也可以在未激活环境时显式使用 `python3.10`，Windows 可使用 `py -3.10`。

本文说明仓库如何把研究计划变成可恢复的本地运行。默认流程只执行
`simulation + Check Submission`，不会自动执行平台的正式 `submit`。

## 1. 最小运行路径

```bash
# 需要登录：冒烟模式（1 字段/1 模板、并发 1）快速验证凭证、API 连通性和模拟创建，
# 同时会生成 dry-run 依赖的本地字段缓存
python -m alpha --dataset-id fundamental2 --template-library-file datasets/fundamental2/template.json --run-mode smoke

# 离线只读：检查字段、模板和候选计划，不创建 simulation（依赖上面生成的字段缓存）
python -m alpha --dataset-id fundamental2 --dry-run-plan

# fundamental6 广泛探索：首次会拉取字段缓存，且必须显式给出 simulation 硬预算
python -m alpha --dataset-id fundamental6 --run-mode full --max-new-simulations 100

# 聚焦历史上更有希望的字段
python -m alpha --dataset-id fundamental2 --template-library-file datasets/fundamental2/template.json --top-fields-by-feedback 10 --max-templates-per-field 15
```

`run` 必须显式传入 `--dataset-id`，避免误跑历史数据集。`clean` 不进入研究配置路径，
也不要求数据集参数；它会处理所有数据集的可重建运行产物。选择数据集后，
运行器采用内置默认搜索预算。`--run-mode full` 会枚举更大的字段和模板空间，
但仍保留本次进程的新建 simulation 预算。恢复任务只负责轮询已有远端 simulation，
不消耗新建预算。运行器先进入 Seed 阶段：历史上没有有效尝试的合格字段
每个最多调度一个候选；只有所有字段都已获得种子尝试或被判定为不可执行后，才进入正常
refine 轮次。full-run 默认预算由 `config/constants_defaults.yaml` 的
`full_run.max_new_simulations` 定义；可用 `--max-new-simulations N` 调整，显式传入 `0`
才会取消总预算。若预算低于剩余 Seed 字段数，运行日志和 dry-run 会明确
标记 partial seed coverage，并且本次不会提前进入 refine。全量模式只适合有足够时间、
且明确希望从零开始验证时使用。日常研究应从 `--dry-run-plan` 开始。

## 2. 字段选择如何落地

首次真实运行会按 `dataset + region + universe + instrument_type + delay` 拉取字段，
并缓存到：

```text
datasets/<dataset>/cache/<region>_<universe>_<instrument>_d<delay>.json
```

例如 `usa_top3000_equity_d1.json`。同一市场范围会复用缓存；缓存缺失或结构失效时，
正常运行会重新拉取。`--dry-run-plan` 只使用本地缓存，不登录、不联网；没有匹配缓存时
先用一次带凭证的冒烟运行生成缓存，例如：

```bash
python -m alpha --dataset-id <dataset-id> --limit 1 --run-mode smoke
```

有限 `--limit` 下的候选保护机制：

- 先按 `coverage`、`dateCoverage`、`alphaCount`、`userCount` 做质量与拥挤度筛选；少量历史使用可以证明字段可运行，超过拥挤起点后才逐步降权。
- 字段指标缺失会保留候选、轻微降分并记录 `unknown_*`，不会与真实低覆盖或低验证样本混为同一过滤原因。
- `_10 / _30 / _60 / _180_days` 等数字窗口会归并成字段族，即使后面还有标的后缀也会归并；每族代表数由 `expression_policies.__default__.field_max_per_family` 控制。
- 未探索字段配额由 `expression_policies.__default__.field_exploration_ratio` 控制；其余名额只给历史优质字段，普通失败记录不会挤占探索预算。
- 任一通过 submission check 的 Alpha 会立即成为强正反馈；其他反馈还需满足最小尝试次数和结果时间衰减条件。
- 新字段先以一个低成本种子模板探索；达到明确门槛后才进入 resimulate/refine，全局模板历史不会让未探索字段整体空跑。

`--include-fields-file` 是人工明确指定的研究范围，因此跳过字段族配额和探索比例，但仍执行基础质量检查。
`--dry-run-plan` 会输出字段分数、原始排名、字段族、入选原因、不可执行字段数和过滤统计，
用于在真实运行前解释最终候选范围。数据集可在 `config/expression_policies.yaml` 覆盖默认策略，
因此具体生效值以 dry-run 和 run config snapshot 为准。

## 3. 数据集资产与仓库边界

每个数据集的长期、可审阅资产：

| 路径 | 用途 | 是否提交 |
|---|---|---|
| `datasets/<id>/template.json` | 默认模板库 | 是 |
| `datasets/<id>/presets/` | 专项模板、字段或模板筛选清单 | 是 |
| `datasets/<id>/blacklist.json` | 长期排除规则 | 是 |
| `datasets/<id>/README.md` | 当前策略、验证结论与下一步 | 是 |
| `datasets/<id>/cache/` | 可重拉的字段缓存 | 否 |
| `datasets/<id>/runs/` | 单次运行 journal、state、分析与日志 | 否 |
| `datasets/<id>/feedback/<scope>/` | 跨 run 反馈、只读模板统计和去重索引 | 否 |

`blacklist.json` 是唯一模板排除入口：`learned_templates` 保存历史学习结果或人工条目，
`expression_rules` 保存人工规则；规则可用 `target: expression` 匹配表达式，或用
`target: template_name` 匹配模板名称。运行过程只读取该文件，不会根据回测结果自动
改写长期策略资产；新增或删除排除项应经过人工复核。

成熟结论必须从 `runs/` 或 `feedback/` 中沉淀到 `template.json`、`presets/` 或数据集 README；
不要把长期人工决策留在临时文件名或 JSON 结果里。一次性实验输入放 `tmp/`，外部对照材料或手工草稿放 `scratch/`。
模板的默认排序直接维护在 `template.json` 的 `priority`；不要再为单个历史模板名叠加 YAML 优先级惩罚。

## 4. 续跑、反馈与结果

每次运行默认是增量模式：已完成的“字段 + 模板 + 表达式 + settings”组合不会重复创建；
中断时会保存 `state.json` 与 `interrupt_report.json`，再次运行自动恢复可轮询的远端 simulation。
如需独立实验，优先使用新的 `--run-name`。

运行结果目录：

| 文件 | 含义 |
|---|---|
| `runs/<run>/results.jsonl` | 权威结果 journal；其他分析视图可由它重建 |
| `runs/<run>/summary.json` | 当前 run 的轻量 summary 与 journal 指针 |
| `runs/<run>/analysis.json` | near-pass、失败分布、模板和字段表现 |
| `feedback/<scope>/results.jsonl` | 带来源和 revision 的跨 run 去重结果历史 |
| `feedback/<scope>/run_index.json` | 已聚合 run 的轻量索引 |

`submittable=true` 只表示该 Alpha 通过本轮 submission check，是值得继续比较和人工评估的
候选信号，不代表它已经最优，也不会触发正式提交或自动停止。`PENDING` 结果以
`submittable=null` 保存，不会被当作通过、失败反馈或 near-pass，但会在后续启动时重新查询终态。

如果只想刷新已有结果，可使用独立的 `check-submissions` 命令：

```bash
# 只读取已有 Alpha 详情；不会发现字段、创建 simulation 或触发新的 Check Submission
python -m alpha check-submissions --dataset-id fundamental6 \
  --pending-check-max-seconds 900 --pending-check-workers 1
```

该命令按 `alpha_id` 去重，把 `PENDING` 与接口暂不可用分开处理，使用有界退避直到终态或时间预算耗尽。
运行模式统一通过 `--run-mode` 指定；不同命令的帮助和
参数边界是独立的，误把 run-only 参数传给 `clean` 或 `check-submissions` 会被拒绝。

历史 `PENDING` 的刷新是有界保护，不保证一次运行取得所有终态：启动阶段和收尾阶段各自最多
选择 20 条（按最早 `updated_at` / `created_at` 优先），各自最多等待 30 秒，并遵守
`check_submission_retries`。它只重试传输失败或空响应；收到语义 `PENDING` 后，后续刷新改读
Alpha 详情，不会反复触发网页的 Check Submission 动作。未刷新、仍为 `PENDING` 或因时间预算
中止的条目会原样保留到结果 journal，下一次真实运行再继续查询；它们不会重新创建 simulation，
也不会被视为 submission check 已通过或已失败。若同一响应已经包含明确 `FAIL`，该 Alpha 会立即
归为不可提交，不会再因为无关的自相关 `PENDING` 占用刷新队列。

## 5. 路径、配置与清理

工作区按以下优先级选择：`ALPHA_WORKSPACE_ROOT`、源码仓库（或当前含 `datasets/` 与 `config/` 的目录）、`~/.alpha/`。
相对路径参数按命令执行目录解析；`--output`、`--fields-cache-file`、`--include-fields-file` 和模板库路径都可显式覆盖默认值。

可编辑配置的唯一来源是根目录 `config/*.yaml`。日常运行参数主要在 `settings.yaml`，
运行策略 profile schema、数据集 profile、表达式策略、质量反馈和模板默认值分别按各自 YAML 维护；
`src/alpha/resources/config/*.yaml` 是安装包镜像，不应直接修改。

运行策略用 `global.runtime.strategy_profile` 或 `--strategy-profile` 显式标记，当前支持：

- `explore`：广覆盖探索，优先发现字段/模板是否有基本信息量
- `refine`：反馈邻域优化，优先围绕 near-pass 和已知有效结构做小范围变体
- `candidate-focused`：候选质量收敛，聚焦高反馈字段并继续验证风险、相关性和稳健性

`config/strategy_profiles.yaml` 同时定义策略说明、常调参数边界和可执行的
`runtime_defaults`；其中 `tuning_keys` 仅用于说明边界，不会单独改写参数，
而 `runtime_defaults` 会在 CLI 配置解析阶段参与默认值覆盖。
当前 `refine` 会收窄字段与模板预算，`candidate-focused` 还会聚焦历史反馈字段，但不会因为
出现 `submittable=true` 就停止；`explore` 不额外改写默认预算。

配置只在 CLI 边界解析一次，固定优先级为：**显式 CLI > run mode > strategy profile >
dataset profile > global YAML > parser 默认值**。`--run-mode smoke/full` 是安全契约：若同时传入
与该模式矛盾的搜索参数，例如 `--run-mode full --limit 20`，命令会明确报错，绝不会静默改写
你的参数。旧的 smoke/full 布尔开关仍可用作兼容别名。`--dry-run-plan` 会输出关键参数的来源，
结果文件中的 `run_config.config_sources` 保存最终来源，
`run_config.config_source_chains` 保存完整覆盖链。

默认 `python -m alpha --help` 只展示日常研究所需的命令、模式、搜索范围、输入过滤和输出参数。
并发、HTTP 重试、质量阈值和启动阶段的 PENDING 刷新控制属于高级运维配置，应优先在
`config/settings.yaml` 中维护；为兼容既有脚本，这些 CLI 覆盖参数仍可解析，但不再占用默认帮助输出。

```bash
# YAML 改动后同步并检查
make sync-config
make check

# 默认只预览所有数据集的清理目标
python -m alpha clean

# 确认后仅清理一个数据集
python -m alpha clean --dataset-id option9 --confirm-clean

# 全局清理必须显式声明范围并确认
python -m alpha clean --all-datasets --confirm-clean
```

`alpha clean` 默认只打印目标，不删除文件。指定 `--dataset-id` 时只处理该数据集的
`cache/`、`runs/` 和 `feedback/`；全局范围必须使用 `--all-datasets`，并额外处理遗留根目录
运行产物。实际删除都要求 `--confirm-clean`。`runs/results.jsonl` 是本地权威回测记录，不能在
删除后由分析视图反向重建；清理前应先将重要证据沉淀到数据集 README、模板或外部备份。
`make clean-dev` 只处理 Python 字节码、测试缓存、coverage 与开发安装元数据。
只有 `--all-datasets --include-credentials --confirm-clean` 才会清理本地加密凭证。
凭证优先使用交互式提示或 `.credentials/` 加密存储；`--email` / `--password` 明文参数
会出现在 shell 历史与进程列表中，仅用于一次性调试。
