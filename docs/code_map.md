# 代码地图（Module Map）

> 回答"这个功能在哪里、改某类东西动哪个文件、为什么模块这么碎"。
> 代码行为与边界契约以 [AGENTS.md](../AGENTS.md) 和本页为准；本页只做导航，不重复实现细节。

## 1. 入口与三叉路由

```text
python -m alpha
  └─ src/alpha/__main__.py            # 版本检查 + run_cli_entry
       └─ src/alpha/main.py           # CLI 生命周期编排
            ├─ cli/parser.py          # parse_application_config -> ApplicationConfig（不可变快照）
            │    └─ cli/arg_resolution.py / path_resolution.py / run_config.py
            ├─ clean 分支             # app/bootstrap_cleanup.py
            ├─ dry-run 分支           # app/planning.py（离线只读，不登录/不写运行产物）
            └─ run 分支               # app/bootstrap.py -> app/run_loop.py -> app/finalize.py
```

三条路由都只拿到 `config/application.py::ApplicationConfig` 的不可变快照；
`argparse.Namespace` 严格停留在 `cli/*`，运行时代码不接触它。

## 2. 包职责总览

| 包 | 职责 | 典型文件 |
| --- | --- | --- |
| `cli/` | CLI 边界：解析、参数优先级、路径解析、配置快照 | `parser.py`、`parser_sections.py`、`arg_resolution.py` |
| `config/` | 配置：YAML 加载、声明式设置表、不可变快照、策略 profile | `settings_spec.py`、`yaml_sources.py`、`application.py`、`application_sections.py` |
| `app/` | 运行编排：bootstrap 初始化、run loop、finalize、dry-run 计划 | `bootstrap.py`、`planning.py`、`run_loop.py`、`finalize.py` |
| `core/` | 运行引擎：scheduler、executor、simulation 阶段、checkpoint、提交检查 | `scheduler_draining.py`、`scheduler_concurrency.py`、`executor.py`、`simulation*.py`、`submission_checks.py`、`pending_check_refresh.py` |
| `runtime/` | 共享可变运行状态与窄调度状态（所有权见 AGENTS.md） | `state.py`、`concurrency.py`、`future_queue.py`、`queue_retry.py`、`result_ledger.py` |
| `api/` | Brain API 客户端：HTTP、会话、字段/模拟/Alpha、重试 | `client.py`、`session.py`、`fields.py`、`simulations.py`、`retry.py` |
| `analysis/` | 结果/反馈分析：加载、持久化、聚合、诊断、报告 | `results_loader.py`、`results_persistence.py`、`feedback_*.py`、`failed_checks.py`、`report_builder.py` |
| `generators/` | 表达式与模板生成：字段、ratio/matrix、变体、指纹 | `expression_builder.py`、`fields.py`、`payload.py`、`templates/*` |
| `policy/` | 表达式策略与黑名单（长期策略资产，只读执行） | `expression.py`、`blacklist_store.py`、`template_blacklist.py` |
| `models/` | 领域类型与窄配置 dataclass（跨层传递的最小契约） | `domain*.py`、`submission_check.py`、`runtime_options.py`、`runtime_protocols.py` |
| `io/` | 底层 IO：凭证、文件锁、结果存储、输出路径、Windows DPAPI | `credentials.py`、`file_lock.py`、`results_store.py`、`output_paths.py` |
| `selection/` `utils/` | 字段筛选辅助 / 通用小工具 | `feedback_filters.py`、`helpers.py` |

## 3. 关键调用链

### 配置链（一次解析，全程只读）

```text
cli/parser_sections.py  ── 读 ──┐
cli/arg_resolution.py   ── 读 ──┼──> config/settings_spec.py（声明式设置表，单一来源）
config/yaml_sources.py  ── 读 ──┘          │
                                          v
                      config/application.py（不可变 ApplicationConfig）
                                          │
                          models/runtime_options.py（各阶段窄配置 bundle）
```

### dry-run 链（离线只读，不联网、不创建 simulation、不写运行产物）

```text
app/planning.py
  ├─ bootstrap_supporting_resources.py::load_supporting_resources()   # 与真实 bootstrap 共用入口
  ├─ generators/fields.py::load_fields_cache()                        # 只读本地字段缓存
  ├─ app/bootstrap_fields.py::prepare_fields_for_execution()
  ├─ app/bootstrap_state.py::create_execution_state()                 # 空状态
  └─ core/executor_dry_run*.py::print_dry_run_plan()                  # 只打印计划
```

### 真实 bootstrap 链

```text
app/bootstrap.py
  ├─ bootstrap_clients.py            # 凭证 + 登录 + worker 客户端工厂
  ├─ bootstrap_field_resources.py    # 拉取/缓存字段 + 字段选择统计
  ├─ bootstrap_field_selection.py    # 字段排序/筛选
  ├─ bootstrap_fields.py             # 字段预处理（含 field_quality/field_families 辅助）
  ├─ bootstrap_pending_checks.py     # 恢复未决 Check Submission
  ├─ bootstrap_supporting_resources.py / bootstrap_types.py
  ├─ bootstrap_run_context.py        # 组装 InitializedRunContext + 并发资源
  ├─ bootstrap_state.py              # 构建 ExecutionState
  ├─ run_identity.py                 # run/checkpoint 指纹
  └─ bootstrap_runtime_outputs.py    # 输出路径与运行配置快照副作用
```

### run loop 链

```text
app/run_loop.py
  ├─ run_loop_contexts.py      # 上下文构造
  ├─ run_loop_rounds.py        # 每轮调度（入口）
  ├─ run_loop_dispatch.py      # 单字段派发
  ├─ run_loop_seed_phase.py    # full-run 的 seed 阶段
  ├─ run_loop_resume.py        # checkpoint 续跑
  ├─ run_loop_feedback.py      # 反馈刷新
  ├─ future_submission.py      # 新任务提交、恢复任务、停止前元数据等待
  ├─ future_completion.py      # future 完成、结果消费、容量排空与 checkpoint
  └─ core/scheduler_draining.py + core/scheduler_concurrency.py + core/executor.py + core/simulation*.py
```

### scheduler 链（边界拆分示例）

```text
core/scheduler_draining.py      # 排空/完成推进（调度主入口）
  ├─ scheduler_queue.py         # 候选队列
  ├─ scheduler_concurrency.py   # 运行时并发状态
  ├─ scheduler_completion.py    # future -> 结果行
  └─ scheduler_decisions.py     # 纯决策函数（与副作用分离）
```

### finalize 链

```text
app/finalize.py
  ├─ analysis/results_loader.py / results_persistence.py   # 加载/落盘
  ├─ analysis/result_identity.py / result_provenance.py    # 去重与溯源
  ├─ analysis/feedback_run_index.py                        # 反馈 run 索引
  ├─ core/checkpoint_files.py                              # 清理恢复状态
  └─ io/results_store.py                                   # 结果事务
```

## 4. AGENTS.md 边界规则 → 具体文件

| 规则 | 落点 |
| --- | --- |
| dry-run 必须离线只读 | `app/planning.py` + `bootstrap_supporting_resources.py::load_supporting_resources()` |
| `ExecutionState` 共享可变状态，新增状态先考虑专用 dataclass | `runtime/state.py` + `runtime/contexts.py` |
| queue retry 属于 `QueueRetryState` | `runtime/queue_retry.py` |
| future 队列 / 可恢复 simulation / stop signal 属于 `FutureQueueState` | `runtime/future_queue.py`，经 `ExecutionState.future_queue` 访问 |
| worker 上限与拥塞冷却属于 `RuntimeConcurrencyState` | `runtime/concurrency.py` |
| `ResultLedgerState.results` 唯一权威结果序列 | `runtime/result_ledger.py` |
| checkpoint 恢复重置瞬时队列 | `ExecutionState.reset_transient_queue_state()` |
| `argparse.Namespace` 只到 CLI 边界 | `cli/*`；运行时代码用 `ApplicationConfig` / `models/runtime_options.py` |
| 底层不 import `alpha.app`；`alpha.io` 在 analysis 下层 | 由 `scripts/check_repo.py arch-boundary` 强制 |
| 数据设置单一来源 | `config/settings_spec_*.py`（按职责声明，`settings_spec.py` 统一组合供 CLI / YAML / 运行时共用） |

## 5. 常见「改哪里」快速索引

| 想做的事 | 文件 |
| --- | --- |
| 新增/调整一个 YAML 镜像设置 | 按职责编辑 `config/settings_spec_dataset.py`、`settings_spec_planning.py`、`settings_spec_execution.py`、`settings_spec_quality.py` 或 `settings_spec_runtime.py`；`settings_spec.py` 负责统一组合 |
| 调整某个数据集的运行参数 | `config/dataset_profiles.yaml`（键集合由 `dataset_profile_keys()` 锁定） |
| 新增模板族 / 表达式规则 | `generators/templates/*` + `policy/expression.py` |
| 新增提交前检查 | `core/submission_checks.py` + `analysis/failed_checks.py` |
| 调整模拟阶段/轮询 | `core/simulation*.py`（create/poll/parsing/results/precheck） |
| 新增数据集 | `datasets/<id>/` + `config/dataset_profiles.yaml` + `datasets/README.md` |
| 新增 API 调用 | `api/*`（fields/simulations/alphas + http_backend/retry） |
| 调整调度行为 | `core/scheduler*.py` + `runtime/*` 状态模块 |

## 6. 为什么模块这么多（边界设计，不是碎片）

184 个源码模块 / 约 2.28 万行不是随意拆分，而是三类动机：

1. **状态所有权**：`runtime/*` 与 `core/scheduler*` 的拆分直接对应 AGENTS.md 的
   "一个可变状态一个专用 dataclass" 规则，避免 `ExecutionState` 膨胀成万能容器。
2. **纯逻辑与副作用分离**：如 `core/scheduler_decisions.py` 只放无副作用的决策函数，
   `generators/templates/*` 把候选/元数据/配对分开，便于单测。
3. **编排与步骤分离**：`app/bootstrap_*.py` 是 `bootstrap.py` 的步骤化拆分，让主流程
   保持可读；dry-run 与真实运行共用 `bootstrap_supporting_resources.py` 一个入口。

合并文件会破坏上述契约（AGENTS.md 的 `arch-boundary-check` / `compat-import-check`
会拦截越层导入）。因此优化方向是**降低导航成本而不是合并**：本页即第一版地图；
后续若某处拆分失去边界价值（单消费者、无状态所有权含义），再按"一次只切一个边界"
的原则做机械合并，并同步更新本页。


## 7. 术语表（Ubiquitous Language）

研究文档、CLI 输出与代码共用同一套术语；命名新类型前先查本表，避免同义反复。

| 领域概念 | 代码标识 | 说明 |
| --- | --- | --- |
| Alpha 结果（一次模拟+检查的产物） | `models/domain.py::FieldTestResult` | 已落盘结果行：指标、failed_checks、error_type、failed_stage |
| 字段（数据集数据字段） | `models/domain.py::TemplateField` | API 字段元数据 + 选择/质量元数据 |
| 模板（候选表达式结构） | `models/domain.py::TemplateCandidate` / `TemplateLibraryItem` | 一个表达式模板候选 / 模板库条目 |
| 检查项 | `models/domain.py::FailedCheck` | 一次 submission check：name/value/limit/result |
| Submission Check 结果 | `models/submission_check.py::SubmissionCheckOutcome` | 将通过、失败、PENDING、接口不可用和终态错误统一成不可变观察值 |
| PENDING 刷新服务 | `core/pending_check_refresh.py::PendingCheckService` | 按 Alpha ID 去重，并在有界预算内退避刷新，不创建新 simulation |
| 结果持久化上下文 | `analysis/results_persistence.py::ResultPersistenceContext` | 统一结果路径、运行身份、配置快照与 metadata scope |
| 设置变体 | `models/domain.py::SettingsVariant` | 一次模拟的 settings 覆盖（不可变值对象） |
| 字段测试上下文 | `models/domain.py::FieldTestContext` | 单次 字段×模板 执行上下文，产出 FieldTestResult |
| 结果聚合 | `runtime/result_ledger.py::ResultLedgerState` | 唯一权威结果序列 + 派生计数 |
| 队列聚合 | `runtime/future_queue.py::FutureQueueState` | 未完成 future + 可恢复远端 simulation + stop signal |
| 重试预算聚合 | `runtime/queue_retry.py::QueueRetryState` | 候选级 queue-busy 重试计数与耗尽集 |
| 并发/拥塞聚合 | `runtime/concurrency.py::RuntimeConcurrencyState` | worker 上限与拥塞冷却 |
| 模拟阶段（stage） | `config/_constants_strings.py::TEMPLATE_STAGE_*` | first_order / group_second_order / event_conditioned |
| 结果状态 | `config/_constants_strings.py::STATUS_*` | simulated / error / skipped |
| 失败阶段 | `FieldTestResult.failed_stage` | simulation / check_submission / stopped / worker |

约定：文档说"结果 / Alpha 结果"即代码 `FieldTestResult`；"字段"即 `TemplateField`；
"模板"即 `TemplateCandidate`；"检查"即 `FailedCheck`。不要为同一概念引入新词。

状态归属的聚合级地图见 [聚合边界图](aggregate_boundaries.md)。
