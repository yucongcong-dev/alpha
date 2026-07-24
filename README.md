# WorldQuant Brain Alpha Runner

通用的 WorldQuant Brain 数据集 Alpha 模拟/检查/提交运行器。

## 学习入口

- 文档总入口：先看 [docs/README.md](docs/README.md)
- 数据集策略说明：看 `templates/<dataset_id>/README.md`

## 常用路径

- 想按问题找文档：看 [docs/README.md](docs/README.md)
- 想按学习顺序看：看 [docs/README.md](docs/README.md)
- 想看数据集策略：看 `templates/<dataset_id>/README.md`

## Python 版本

- 最低要求：`Python 3.10`
- 推荐：`Python 3.10+`
- 项目根目录已补 `.python-version=3.10`，便于 `pyenv` / IDE 自动选中兼容解释器
- 下文里的 `python3.10` 可以替换成任意 `3.10+` 解释器路径

## 项目结构

```
alpha/                     # 项目根目录
├── src/                   # 源码目录
│   └── alpha/             # 主包
│       ├── __init__.py    # 包入口（导出基础公共 API）
│       ├── __main__.py    # python3.10 -m alpha / alpha 命令入口
│       ├── main.py        # 精简入口，调用 app 编排层
│       │
│       ├── app/           # 应用编排层：初始化、运行循环、收尾、clean
│       │   ├── bootstrap.py
│       │   ├── bootstrap_cleanup.py
│       │   ├── bootstrap_fields.py
│       │   ├── bootstrap_state.py
│       │   ├── finalize.py
│       │   ├── loop_future_support.py
│       │   ├── run_loop.py
│       │   ├── run_loop_feedback.py
│       │   ├── run_loop_paths.py
│       │   ├── run_loop_resume.py
│       │   └── run_loop_rounds.py
│       │
│       ├── core/          # 核心业务层
│       │   ├── checkpoint.py
│       │   ├── execution_filters.py
│       │   ├── executor.py
│       │   ├── scheduler.py
│       │   ├── result_processing.py
│       │   ├── simulation_parsing.py
│       │   ├── simulation_precheck.py
│       │   ├── simulation_results.py
│       │   ├── simulation_stages.py
│       │   ├── template_planning.py
│       │   └── simulation.py   # 兼容导出层
│       │
│       ├── generators/    # Alpha 生成层
│       │   ├── expressions.py
│       │   ├── expression_builder.py
│       │   ├── field_transforms.py
│       │   ├── fields.py
│       │   ├── fingerprint.py
│       │   ├── matrix_templates.py
│       │   ├── payload.py
│       │   ├── ratio_templates.py
│       │   ├── settings.py # 兼容导出层
│       │   ├── variants.py
│       │   └── templates/ # 模板库、候选构造、分类、优先级、refine 变体
│       │       ├── __init__.py
│       │       ├── candidates.py
│       │       ├── classification.py
│       │       ├── feedback_best_expression.py
│       │       ├── feedback_mutations.py
│       │       ├── feedback_mutation_sets.py
│       │       ├── historical_reuse.py
│       │       ├── metadata.py
│       │       ├── partner_fields.py
│       │       ├── priority.py
│       │       ├── refine.py
│       │       ├── variation_common.py
│       │       ├── wrappers.py
│       │       └── variations.py
│       │
│       ├── analysis/      # 分析优化层
│       │   ├── feedback.py
│       │   ├── feedback_filters.py
│       │   ├── feedback_history.py
│       │   ├── failed_checks.py
│       │   ├── feedback_stats.py
│       │   ├── field_stats.py
│       │   ├── report_builder.py
│       │   ├── result_identity.py
│       │   ├── results_loader.py
│       │   ├── template_execution_policy.py
│       │   ├── template_registry.py
│       │   ├── template_registry_budget.py
│       │   ├── template_registry_rules.py
│       │   ├── template_registry_sidecars.py
│       │   ├── template_registry_store.py
│       │   ├── stats.py       # 兼容导出层
│       │   └── template_stats.py
│       │
│       ├── api/           # API 客户端层
│       │   ├── alphas.py
│       │   ├── api_types.py
│       │   ├── client.py      # BrainClient / WorkerClientFactory 组合入口
│       │   ├── fields.py
│       │   ├── payloads.py
│       │   ├── retry.py
│       │   ├── session.py
│       │   ├── simulations.py
│       │   └── timing.py
│       │
│       ├── io/            # 输入输出层
│       │   ├── analysis_sync.py
│       │   ├── common.py
│       │   ├── credentials.py
│       │   ├── credentials_crypto.py
│       │   ├── output_paths.py
│       │   ├── results_store.py
│       │   └── output.py      # 兼容导出层
│       │
│       ├── cli/           # 命令行接口层
│       │   ├── arg_resolution.py
│       │   ├── constants.py
│       │   ├── filters.py
│       │   ├── parser_sections.py
│       │   ├── parser_schema.py
│       │   ├── path_resolution.py
│       │   ├── run_config.py
│       │   └── parser.py
│       │
│       ├── models/        # 数据模型层
│       │   ├── domain.py
│       │   ├── io_types.py
│       │   ├── runtime.py
│       │   ├── runtime_options.py
│       │   ├── runtime_protocols.py
│       │   ├── runtime_state.py # 兼容导出层
│       │   └── base.py    # 兼容导出层
│       │
│       ├── runtime/       # 运行期上下文与可变执行状态
│       │   ├── __init__.py
│       │   ├── contexts.py
│       │   └── state.py
│       │
│       ├── policy/        # 运行期策略层
│       │   ├── __init__.py     # facade 导出入口
│       │   ├── blacklist_context.py
│       │   ├── blacklist_runtime.py
│       │   ├── blacklist_runtime_stats.py
│       │   ├── blacklist_runtime_updates.py
│       │   ├── blacklist_store.py
│       │   ├── expression.py
│       │   ├── template_blacklist.py
│       │   └── types.py
│       │
│       ├── utils/         # 工具函数层
│       │   └── helpers.py
│       │
│       ├── config/        # 配置入口、YAML、模型、profiles、CLI defaults
│       │   ├── __init__.py
│       │   ├── constants.py
│       │   ├── defaults.py
│       │   ├── getters.py
│       │   ├── models.py
│       │   ├── policy.py
│       │   ├── policy_coercers.py
│       │   ├── policy_overrides.py
│       │   ├── profiles.py
│       │   ├── types.py
│       │   ├── yaml.py
│       │   ├── yaml_sources.py
│       │   └── yaml_validator.py
│       └── exceptions.py  # 自定义异常
│
├── tests/                 # 测试目录
│   ├── unit/              # 单元测试
│   └── integration/       # 集成测试
│
├── README.md              # 项目说明
├── requirements.txt       # 依赖
├── pyproject.toml         # 项目配置
├── config/                # 按职责拆分的 YAML 配置
│   ├── settings.yaml      # 默认运行配置
│   ├── dataset_profiles.yaml # 数据集运行 profile
│   ├── expression_policies.yaml # 数据集表达式策略
│   ├── constants_defaults.yaml # 代码级常量默认值
│   ├── api.yaml           # API endpoint、headers、HTTP 超时与退避
│   ├── simulation.yaml    # simulation 状态、默认日期、表达式窗口
│   ├── quality_feedback.yaml # 质量阈值、反馈、统计、checkpoint 默认值
│   ├── templates.yaml     # 模板优先级、ratio/partner 生成参数
│   └── runtime.yaml       # 路径、状态字符串、哨兵值等运行约定
├── templates/             # 模板库与 README
│   ├── base/              # 基础共享模板库与说明
│   ├── fundamental6/      # fundamental6 专属模板库与说明
│   ├── model16/           # model16 专属模板库与说明
│   └── model51/           # model51 专属模板库与说明
├── blacklists/            # dataset 统一 blacklist（脚本自动追加，也可人工补充）
└── .gitignore
```

## 仓库边界

哪些文件进仓：

- `config/*.yaml`：统一配置入口，按职责维护默认运行参数、数据集 profile、表达式策略、API、simulation、质量阈值、模板参数和运行约定。
- `templates/base/` 与 `templates/<dataset_id>/`：基础模板、数据集专属模板、聚焦字段/模板白名单，以及经过验证值得复用的本地 refine 模板。
- `templates/<dataset_id>/refine/fields/*.json`：少量、可复用、人工裁剪的字段 fixture；它们服务于稳定复现实验，不应再混入 `cache/`。
- `blacklists/<dataset_id>/blacklist.json`：统一黑名单。脚本会自动追加，也允许人工维护；空黑名单也可以进仓，用于固定数据集目录边界。

哪些文件不进仓：

- `results/`：每次运行的结果、分析、日志、checkpoint 和 state。
- `cache/`：磁盘上的可重建缓存目录。当前主要承载字段缓存；内存态的 YAML / blacklist / runtime cache 不落在这里。
- `tmp/`：一次性实验输入、临时 include/exclude 列表、临时模板库。
- `scratch/`：外部脚本、对照材料、手工实验草稿。
- `.credentials/`：本地加密凭证和密钥。

根目录只保留项目入口和说明文件。配置统一放 `config/`；临时文件不要放根目录。如果只是一次性实验，放 `tmp/`；如果已经验证值得长期复用，再整理命名后放入 `templates/<dataset_id>/`。

## 结果目录约定

`results/` 仍然是纯运行产物目录，不进仓；但建议在数据集子目录下按意图分层，避免长期扁平堆叠：

- `results/<dataset_id>/explore/`：广泛探索、overnight sweep、初筛轮次
- `results/<dataset_id>/refine/`：局部精修、triplet/density/window 等 focused 轮次
- `results/<dataset_id>/compare/`：同一字段或同一家族的对照实验
- `results/<dataset_id>/scratch/`：短期排障、filter probe、临时验证

如果暂时没迁移旧文件，至少在新命名中保持阶段前缀一致；一旦某轮结果成为长期参考，再把对应模板/字段知识沉淀回 `templates/<dataset_id>/`，而不是继续让 `results/` 承担知识库角色。

## 模板目录

当前模板目录统一放在 `templates/`：

- 基础共享模板库：`templates/base/library.json`
- 基础模板说明：`templates/base/README.md`
- 数据集专属模板库：`templates/<dataset_id>/library.json`
- 数据集专属模板说明：`templates/<dataset_id>/README.md`
- 数据集聚焦白名单：可选放在 `templates/<dataset_id>/*.txt`
- 数据集 refine 模板库：可选放在 `templates/<dataset_id>/*refine*.json`

其中 `base` 只负责提供共享 fallback 模板，真正的搜索方向应尽量在数据集专属目录里定制和收敛。

代码中的模板相关逻辑统一放在 `src/alpha/generators/templates/`：

- `__init__.py`：加载、校验、补齐和生成 JSON 模板库
- `candidates.py`：统一构造 `TemplateCandidate`
- `classification.py`：识别模板 family / stage
- `metadata.py`：构建模板 metadata 索引
- `partner_fields.py`：为 ratio 模板发现配对字段
- `priority.py`：自适应优先级、相似度惩罚、family 数量裁剪
- `refine.py`：near-pass 候选的局部精修
- `variations.py`：feedback mutation、bucket group、trade_when、历史优秀表达式复用

## 黑名单目录

- 统一黑名单：`blacklists/<dataset_id>/blacklist.json`。
- 当运行结果持续不佳时，脚本会直接把低质量模板追加到该文件，下次运行自动跳过。
- 你也可以手工编辑同一个文件，用于补充明确不想再跑的模板或表达式规则。

## 当前代码分层

- `main.py` 现在只保留精简入口，具体应用编排已经拆到 `app/bootstrap.py`、`app/run_loop.py`、`app/finalize.py`
- 根目录的 `bootstrap.py`、`run_loop.py`、`finalize.py`、`loop_*` 和 `run_loop_*` 兼容壳已经移除；代码应直接依赖 `alpha.app.*`
- `models/domain.py` 只放领域对象；`models/io_types.py` 放路径/过滤边界对象；`models/runtime_options.py`、`models/runtime_protocols.py` 放运行配置与协议；运行期上下文和可变执行状态已经下沉到 `runtime/contexts.py`、`runtime/state.py`；`models/runtime_state.py`、`models/runtime.py` / `models/base.py` 仅保留兼容导出
- `analysis/stats.py` 是兼容导出层；结果加载、失败检查评分、模板/字段统计、反馈画像已经分别拆到 `results_loader.py`、`failed_checks.py`、`template_stats.py`、`field_stats.py`、`feedback_stats.py`
- `analysis/feedback.py` 是兼容导出层；历史状态/near-pass 选择放在 `feedback_history.py`，模板禁用/保留/跳过策略放在 `feedback_filters.py`
- `analysis/template_execution_policy.py` 负责把模板 registry 的角色、scope、预算和 refine candidate 这些“模板治理判定”整理成执行前决策
- `analysis/template_registry.py` 及其配套的 `template_registry_budget.py`、`template_registry_rules.py`、`template_registry_store.py`、`template_registry_sidecars.py` 负责模板角色、scope、预算和 sidecar 汇总这组“模板治理”逻辑
- `analysis/report_builder.py` 负责从结果构建 summary/analysis payload
- `core/execution_filters.py` 负责执行期字段/模板跳过判断；`core/template_planning.py` 负责把模板候选展开为执行队列，本身尽量不再承载 template registry 的细粒度策略判定。旧的 `core/template_filters.py` / `core/template_queue.py` 仅保留兼容导出。
- `policy/__init__.py` 是策略 facade；`blacklist_runtime.py` 负责运行态黑名单聚合与自动更新，`blacklist_store.py` 负责黑名单文件存取，`template_blacklist.py` 负责模板名/表达式规则匹配，`expression.py` 负责数据集表达式策略和反馈阶段判断
- `io/output.py` 负责结果持久化与分析边车编排，不再承载黑名单策略实现
- `io/common.py` 放更底层的 JSON 原子写入、路径常量、dataset 文件名安全化与运行时 `data/` 目录解析
- `cli/path_resolution.py` 负责把模板库、字段缓存、结果 sidecar、blacklist 根目录等运行路径显式归一化为 `RunPaths`
- `config/` 是配置子包：`__init__.py` 保留旧的 `alpha.config` 入口，`models.py` 放配置 dataclass，`yaml.py` 只保留线程安全缓存和公共 API，`yaml_sources.py` 放 YAML 查找/加载/合并/签名，`yaml_validator.py` 放 schema 和交叉一致性校验，`defaults.py` 放 YAML global 到 CLI 参数的合并，`policy.py` 放策略构建和反馈阶段判断，`policy_coercers.py` 放 YAML 类型转换，`policy_overrides.py` 放 expression policy 覆盖解析，`profiles.py` 放 dataset profile fallback。
- `generators/templates/` 是模板子包：`__init__.py` 管理 JSON 模板库，`candidates.py` 构造 `TemplateCandidate`，`classification.py` 做模板 family/stage 分类，`metadata.py` 建模板元数据索引，`partner_fields.py` 发现 ratio 配对字段，`priority.py` 做自适应优先级和 family 裁剪，`refine.py` 生成 near-pass 精修模板，`feedback_mutations.py` 编排反馈 mutation，`feedback_mutation_sets.py` 放具体 mutation 集合，`feedback_best_expression.py` 放历史最佳表达式变异，`historical_reuse.py`、`wrappers.py` 和 `variation_common.py` 拆分模板变体策略，`variations.py` 保留组合入口。
- `generators/expression_builder.py` 是表达式候选编排层，负责把字段、模板库、策略和反馈组合成候选表达式。
- `generators/matrix_templates.py` 负责 MATRIX 字段的多样化、ratio、bucket、trade_when 和 legacy 模板构造。
- `generators/ratio_templates.py` 负责高信心 ratio、字段配对 ratio、delta-rank 和 delta/std ratio 模板构造。
- `generators/expressions.py` 现在是兼容导出层，不再承载模板分类、元数据、优先级、refine、feedback mutation 或候选构建的具体实现。
- `api/client.py` 保留 `BrainClient` / `WorkerClientFactory` 组合入口；`api/retry.py` 放阶段重试和登录重试；`api/session.py` 放登录、底层 request 和全局节流；`api/fields.py` 放 dataset 字段分页；`api/simulations.py` 放 simulation create/poll；`api/alphas.py` 放 alpha detail/submit；`api/payloads.py` 放响应 payload 解析，`api/timing.py` 放等待和 `Retry-After` 解析。
- 内部源码已改为直接依赖具体模块（如 `models/domain.py`、`models/runtime.py`、`models/io_types.py`、`config/constants.py`、`config/getters.py`、`config/policy.py`），`models/base.py` 和 `config/__init__.py` 主要服务外部旧导入兼容。

这次重构的目标是把原先集中在少数大文件里的职责拆开，让入口、运行态、分析构建、配置、模板生成、策略和 IO 边界更清晰。旧入口仍保持兼容，例如 `from alpha.config import get_yaml_config`、`from alpha.generators.templates import load_template_library` 仍然可用。

## 安装

```bash
# 开发模式安装（推荐）
python3.10 -m pip install -e .

# 安装后可直接运行
alpha --smoke-test

# 或直接使用 PYTHONPATH 运行
export PYTHONPATH=src
python3.10 -m alpha --smoke-test
```

## 运行

### 推荐工作流

Alpha 发现是一个**迭代优化**过程，建议按以下阶段执行：

#### 阶段 1：环境验证（冒烟测试）

```bash
python3.10 -m alpha --smoke-test
```

验证：登录认证、API 连通性、模拟创建、401 重认证。
全部 PASS 后方可继续。

#### 阶段 2：广泛探索（发现候选字段）

```bash
python3.10 -m alpha
```

不传参时使用内置默认值（`--limit 200 --max-templates-per-field 6 --field-template-batch-size 2`）。
首次运行会先按当前数据集上下文全量拉取字段并写入磁盘缓存
`cache/fields/<dataset>/<cache_key>/fields.json`，
其中 `cache_key` 由 `region + universe + instrument_type + delay` 生成，例如
`usa_top3000_equity_d1`，
后续同一 `dataset_id + region + universe + instrument_type + delay` 组合直接复用缓存。

**目标**：从数据集中找出有潜力的字段和模板家族。

**字段筛选与排序**：
- 先应用 `include_fields` / `exclude_fields`
- 再用官网返回的字段元数据做基础过滤：`coverage`、`dateCoverage`、`alphaCount`、`userCount`
- 然后联合历史反馈与官网指标排序
- 最后才应用 `offset` / `limit`
- 默认启用 breadth-first 调度：前 200 个字段先各试 2 个高优模板，再在后续轮次逐步补深

**官网字段指标使用方式**：
- `coverage`：横截面覆盖率，正向质量信号
- `dateCoverage`：时间覆盖率，正向质量信号
- `alphaCount`：历史 alpha 使用量，兼作弱验证信号和拥挤度惩罚
- `userCount`：历史用户使用量，兼作弱验证信号和拥挤度惩罚
- `dateCreated`：较新的字段有轻微加分
- `themes`：主题标签数量仅作很弱的辅助加分

**表达式策略配置**：
- 数据集级表达式搜索策略可在 `config/expression_policies.yaml` 或 `config/settings.yaml` 的 `expression_policies.<dataset_id>` 下覆盖
- 适合放这里的参数包括：`partner_limit`、字段质量阈值、反馈阶段设置、少量运行期策略开关
- 模板本身优先放在 `templates/base/` 或 `templates/<dataset_id>/` 下维护，而不是继续把模板内容塞回 Python 常量

**输出**：`*_analysis.json` 中的关键字段：
- `near_pass_summary`：接近通过的候选（按 score 排序）
- `failed_check_leaderboard`：主要失败原因分布
- `optimization_hints`：自动生成的优化建议
- `pending_self_correlation` 结果会保留在主结果文件 / journal 中，但默认不会被当作有效反馈去驱动下一轮模板统计和字段排序

**预估时间**：30-70 分钟（默认先覆盖 200 字段，但每轮每字段只浅试少量高优模板）

**关于 `SELF_CORRELATION=PENDING` 的当前流程**：
- 阶段 2 主探索只做短轮询，不再默认在 `finalize` 阶段同步卡住等待所有 pending alpha
- 若 `SELF_CORRELATION` 仍为 `PENDING`，结果会以 `pending_self_correlation` 状态落盘，并保留 `pending_since / last_recheck_at / recheck_count` 元数据
- 这类结果默认不会参与模板统计、字段反馈画像、near-pass 排行和 failed-check 学习
- 如需同步复查 pending 结果，可显式加 `--finalize-recheck-pending-self-correlation`
- 更推荐把复查独立成后处理命令，见下方“Pending 复查”

#### 阶段 3：聚焦深挖（针对高反馈字段）

```bash
python3.10 -m alpha --top-fields-by-feedback 10 --max-templates-per-field 15
```

**目标**：对接近通过的候选进行精修，而不是继续做一轮广泛模板扩张。

**机制**：
- 当字段进入 `resimulate` 阶段后，执行器会优先从历史结果中选择近门槛候选，而不是回退到整套 broad template 枚举
- 当前 refine 候选按历史 `failed_checks` 的接近度排序，同时会对明显不适合继续追的 `CONCENTRATED_WEIGHT` 候选降权
- refine 只做局部、可解释的表达式变异，例如：
  - `subindustry -> industry`
  - `ts_zscore(..., 60) -> 63 / 126 / 200`
  - `ts_rank(..., 60) -> 126 / 200`
  - `trade_when(...)` 事件包裹
  - 轻度 `ts_decay_linear(...)` 平滑
- settings 变体也会结合候选的失败原因定向展开，而不是统一撒网：
  - 优先尝试更严格的 `truncation=0.05`
  - 对集中持仓或子宇宙问题尝试 `INDUSTRY / MARKET / NONE`
  - 对换手问题尝试更快或更慢的 `decay`

**反馈循环**：
- 默认读取同一输出文件（`results/model51/test_results.json`）
- 阶段 2 的结果会自动用于字段优先级排序和 near-pass 候选筛选
- 可多次运行，每次自动续跑（不重复已完成的组合）
- 如果阶段 2 产生了较多 `pending_self_correlation` 结果，建议先单独复查，再决定是否继续 refine，而不是直接把这些 pending 结果当作普通 near-pass 历史

**当前实现状态**：
- 阶段 1：环境验证
- 阶段 2：breadth-first 广泛探索
- 阶段 3：candidate-centric refine / resimulate

**预估时间**：通常短于阶段 2，因为会把预算收缩到少数 near-pass 候选，而不是继续全模板铺开

#### 数据集 Playbooks

`fundamental6`:
- 当前更适合做止损式小验证，而不是继续大范围单字段深挖。

`model51`:
- 当前更适合做“小字段集 + 小模板集”的聚焦 refine。
- 项目内已提供可复用白名单：
  - `templates/model51/focused_fields.txt`
  - `templates/model51/focused_templates.txt`

示例：

```bash
python3.10 -m alpha --dataset-id model51 --dry-run-plan \
  --include-fields-file templates/model51/focused_fields.txt \
  --include-templates-file templates/model51/focused_templates.txt \
  --limit 4 --max-templates-per-field 4 --max-templates-per-family 1 \
  --output results/model51/focused_validation.json \
  --feedback-output results/model51/focused_validation.json \
  --no-auto-update-blacklist
```

```bash
python3.10 -m alpha --dataset-id model51 \
  --include-fields-file templates/model51/focused_fields.txt \
  --include-templates-file templates/model51/focused_templates.txt \
  --limit 4 --max-templates-per-field 4 --max-templates-per-family 1 \
  --max-concurrent-simulations 2 --max-concurrent-creates 1 \
  --output results/model51/focused_validation.json \
  --feedback-output results/model51/focused_validation.json \
  --no-auto-update-blacklist
```

#### 阶段 4：完整运行（可选）

```bash
python3.10 -m alpha --full-run
```

穷举所有字段和模板组合，适合：
- 首次使用新数据集时进行全面扫描
- 有充足时间（可能数小时）
- 不依赖反馈历史，从零开始探索

---

### 续跑机制

每次运行默认是**增量模式**：
- 已完成的字段+模板组合不会重复
- 新结果追加到同一输出文件
- 中断后再次运行自动继续
- 如需重新开始，使用不同的 `--output` 路径

### Pending 复查

当结果里出现较多 `pending_self_correlation` 时，推荐把复查与主探索拆开：

```bash
python3.10 -m alpha --dataset-id model51 \
  --output results/model51/stage2_explore_clean.json \
  --feedback-output results/model51/stage2_explore_clean.json \
  --recheck-pending-self-correlation-only \
  --no-auto-update-blacklist
```

说明：
- 该模式只会读取历史结果并复查 `SELF_CORRELATION=PENDING` 的 alpha
- 不会发起新的字段探索
- 若只是想在本次运行结束前顺手复查，可显式加 `--finalize-recheck-pending-self-correlation`

---

### 其他命令

预览下一次运行而不创建模拟任务：

```bash
python3.10 -m alpha --dry-run-plan
```

首次生成或复用本地字段缓存：

```bash
python3.10 -m alpha
```

所有相对路径参数（如 `--output`、`--fields-cache-file`、`--include-fields-file`）都相对于当前命令执行目录解析。

运行时资源目录按类型分别解析：
- 模板目录：显式传入的路径 > 当前命令目录下的 `templates/` > 项目内置 `templates/`
- 黑名单目录：显式传入的路径 > 当前命令目录下的 `blacklists/` > 项目内置 `blacklists/`
- 其余普通数据目录仍是：显式传入的 `data_dir` > 当前命令目录下的 `data/` > 项目内置 `data/`

这意味着你可以在临时工作目录放一份独立的 `templates/` 或 `blacklists/`，而不用改动仓库内置数据。

清理本地运行产物（默认保留 `.credentials/`）：

```bash
python3.10 -m alpha clean
```

预览清理内容，不实际删除：

```bash
python3.10 -m alpha clean --dry-run-clean
```

如确实需要同时删除本地加密凭据：

```bash
python3.10 -m alpha clean --include-credentials
```

### YAML 开关覆盖

YAML 中打开的布尔开关可以用 `--no-*` 在命令行临时关闭：

```bash
python3.10 -m alpha --no-submit --no-auto-update-blacklist
python3.10 -m alpha --no-smoke-test --no-full-run
```

## 配置代码结构

配置入口仍然是 `alpha.config`，内部已拆成子模块：

- `config/__init__.py`：公共兼容入口，集中导出常量、getter 和策略函数
- `config/constants.py`：API、状态、统计字段和默认阈值常量
- `config/models.py`：`DatasetExpressionPolicy`、`FieldTransformSpec`、`FeedbackLoopPolicy`
- `config/yaml.py`：`config/*.yaml` 查找、加载和缓存
- `config/defaults.py`：把 YAML `global` 配置合并到 CLI 参数
- `config/getters.py`：运行参数 getter
- `config/policy.py`：dataset expression policy 构建与反馈阶段解析
- `config/profiles.py`：dataset profile fallback

YAML 分层优先级为：`config/settings.yaml` > `config/expression_policies.yaml` > `config/dataset_profiles.yaml` > `config/runtime.yaml` / `config/templates.yaml` / `config/quality_feedback.yaml` / `config/simulation.yaml` / `config/api.yaml` > `config/constants_defaults.yaml`。其中 `config/settings.yaml` 面向日常运行调参，其他 `config/*.yaml` 面向按职责拆分的默认值，`templates/` 面向表达式模板，`blacklists/` 面向低质量模板过滤。

实际运行配置优先维护在 `config/*.yaml`、`templates/` 和 `blacklists/`，不要把数据集专属模板重新塞回 Python 常量。

## 结果解读

每次运行会生成两个文件：

| 文件 | 用途 |
|------|------|
| `results/<dataset>/test_results.json` | 原始结果（每个模拟的详细数据） |
| `results/<dataset>/test_results_analysis.json` | 分析汇总（用于决策下一步） |

### 关键分析字段

| 字段 | 含义 | 如何使用 |
|------|------|----------|
| `submittable_count` | 可提交数量 | =0 时继续优化 |
| `near_pass_summary` | 接近通过的候选 | score > 0.5 的优先深挖 |
| `failed_check_leaderboard` | 失败原因分布 | 看主要卡点是 LOW_SHARPE 还是 LOW_FITNESS |
| `optimization_hints` | 自动生成的建议 | 直接参考执行 |
| `template_performance_summary` | 模板家族表现 | 看哪些模板类型效果好 |
| `field_performance_summary` | 字段表现 | 看哪些字段有潜力 |

### 失败检查含义

| 检查名 | 含义 | 优化方向 |
|--------|------|----------|
| `LOW_SHARPE` | 风险调整收益不足 | 用 vol-scaled delta、group neutralization |
| `LOW_FITNESS` | 综合得分低 | 提高 Sharpe + 降低 Turnover |
| `HIGH_TURNOVER` | 换手率过高 | 用 spread/decay 模板平滑 |
| `CONCENTRATED_WEIGHT` | 权重过于集中 | 用 group neutralization |
| `LOW_SUB_UNIVERSE_SHARPE` | 子宇宙 Sharpe 不足 | 用 MARKET neutralization |

## 测试

运行单元测试：

```bash
PYTHONPATH=src python3.10 -m pytest -q
```

一键开发检查：

```bash
make check
```

也可以分步运行：

```bash
make test
make help-check
make scan-secrets
```

如需运行 lint/format，请安装开发依赖：

```bash
python3.10 -m pip install -e ".[dev]"
python3.10 -m ruff check .
python3.10 -m ruff format .
```

## 打包发布

```bash
python3.10 -m pip install build
python3.10 -m build
```

生成的包在 `dist/` 目录下。
