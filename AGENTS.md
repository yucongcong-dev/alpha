# Agent 执行边界

这份文件是自动化 agent 修改本仓库时的工作契约。改动要小，边界要清楚，交回前使用仓库已有检查。

## 运行流程

- `src/alpha/__main__.py` 只负责 Python 版本检查、安装日志格式，然后调用
  `alpha.main.run_cli_entry`。
- `src/alpha/main.py` 是轻量分发层：解析配置，路由 `clean`，路由
  `--dry-run-plan`，然后执行 `bootstrap -> run_loop -> finalize`。
- dry-run 计划只属于 `src/alpha/app/planning.py`。这条路径必须保持离线只读：
  不登录、不创建 simulation、不初始化结果 journal、不修改运行状态文件、不从远端刷新资源。
- 真实运行只属于 `src/alpha/app/bootstrap.py`、`src/alpha/app/run_loop.py` 和
  `src/alpha/app/finalize.py`。`run_loop.py` 不应包含 dry-run 行为。
- dry-run 和真实 bootstrap 共用的本地资源加载逻辑放在
  `src/alpha/app/bootstrap_resource_loading.py`。差异必须显式表达，例如
  `repair_corrupt_summary` 和黑名单日志。

## 配置边界

- `argparse.Namespace` 应停留在 CLI 边界。运行时代码优先使用
  `ApplicationConfig`，或 `src/alpha/models/runtime_options.py` 里的窄配置 dataclass。
- 如果核心逻辑只需要少数字段，不要传完整 `args` 对象。优先新增或复用窄配置类型，例如
  `FieldFetchOptions`、`FieldSelectionOptions`、`TemplateBuildOptions`、
  `ResultWriteOptions`。
- 如果兼容 facade 仍然存在，除非为了兼容性，不要继续扩展它。内部代码优先导入具体模块。

## 状态边界

- 把 `ExecutionState` 当作共享可变运行状态，不要把它当成随手新增字段的容器。新增状态前，先考虑是否应该拆成由具体行为拥有的专用 dataclass。
- 候选级 queue retry 行为属于 `QueueRetryState`。scheduler 代码不应再用裸 dict/set 重复实现重试预算更新规则。
- 字段级 queue-busy 计数与跳过集合属于 `FieldQueueState`，调用方应通过
  `ExecutionState.field_queue` 访问，不要在 `ExecutionState` 上增加影子字段。
- 运行时 worker 上限与拥塞冷却属于 `RuntimeConcurrencyState`；内部代码从
  `alpha.runtime.concurrency` 导入，不要把并发字段并入 `ExecutionState`。
- checkpoint 恢复时，应通过 `ExecutionState.reset_transient_queue_state()` 重置瞬时队列状态，不要直接逐个赋值内部集合。
- `ResultLedgerState.results` 是唯一权威结果序列；结果计数应由它派生到
  `ExecutionMetrics`。不要在 `ExecutionState` 上增加结果列表或计数的影子字段，避免状态漂移。

## 模块分层

- 底层模块不能导入 `alpha.app` 编排模块。Makefile 的 `arch-boundary-check` 会检查这条规则。
- `alpha.io` 必须位于 analysis 下层，不能导入 `alpha.analysis`。
- 内部代码应导入具体模块，不要导入已移除的兼容出口。Makefile 的
  `compat-import-check` 记录了当前禁止形式。
- 旧根目录 app 兼容文件已经移除；使用 `src/alpha/app/*` 下的具体模块。

## 仓库数据规则

- 可编辑配置位于根目录 `config/*.yaml`；包内镜像位于
  `src/alpha/resources/config/*.yaml`，修改后必须通过 `make sync-config` 或
  `make config-sync-check` 保持同步。
- 数据集长期资产放在 `datasets/<dataset_id>/` 下。
- `cache/`、`runs/`、`feedback/`、`.credentials/`、工具缓存和本地生成状态属于私密或可重建内容，不应提交。
- 不要提交明文凭证、Authorization header 或平台密钥。`make scan-secrets` 会覆盖当前已知模式。

## 测试与检查

- 常规代码改动后运行：

```bash
PYTHONPATH=src python3.10 -m pytest -q
```

- 修改 Python 文件后，对触达文件运行定向 Ruff 检查，例如：

```bash
ruff check src/alpha/app/planning.py tests/unit/test_planning.py
```

- 较大交付前优先运行：

```bash
make check
```

- 如果 `python3` 指向 Python 3.9，请使用 `python3.10`；本项目要求 Python 3.10+。

## 修改纪律

- 每次重构尽量只切一个边界。好的粒度包括：合并 dry-run/live 资源加载、收窄一个 args-like 函数边界、从 `ExecutionState` 抽出一个状态职责。
- 除非用户明确要求，不要把研究策略、平台行为变化和架构清理混在同一个 patch 里。
- 修改 planning 相关代码时，必须守住 dry-run 不联网、不写运行产物的保证。
- 跨边界移动行为时，补充聚焦测试；测试也应改用新的边界对象，而不是继续伪造宽泛 namespace。
- 避免留下陈旧 `TODO`、`FIXME`、`HACK` 注释；后续工作请放到明确的 issue 或用户可见总结里。
