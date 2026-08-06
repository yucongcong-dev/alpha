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
- dry-run 和真实 bootstrap 共用的本地支持资源加载入口是
  `src/alpha/app/bootstrap_supporting_resources.py` 里的
  `load_supporting_resources()`。dry-run 从 `src/alpha/app/planning.py` 直接调用；
  真实 bootstrap 通过同模块的 `load_bootstrap_supporting_resources()` wrapper 调用。
  两条路径的差异必须通过参数显式表达，例如 `repair_corrupt_summary` 和黑名单日志。

## 配置边界

- `argparse.Namespace` 应停留在 CLI 边界。运行时代码优先使用
  `ApplicationConfig`，或 `src/alpha/models/runtime_options.py` 里的窄配置 dataclass。
- 如果核心逻辑只需要少数字段，不要传完整 `args` 对象。优先新增或复用窄配置类型，例如
  `FieldFetchOptions`、`FieldSelectionOptions`、`TemplateBuildOptions`、
  `ResultWriteOptions`。
- 项目是纯 CLI，不维护包级兼容 facade 或 Python 公共导出面；代码和测试都应导入具体模块。

## 状态边界

- 把 `ExecutionState` 当作共享可变运行状态，不要把它当成随手新增字段的容器。新增状态前，先考虑是否应该拆成由具体行为拥有的专用 dataclass。
- 候选级 queue retry 行为属于 `QueueRetryState`。scheduler 代码不应再用裸 dict/set 重复实现重试预算更新规则。
- future 队列、可恢复 simulation 和 stop signal 属于 `FutureQueueState`，调用方应通过
  `ExecutionState.future_queue` 访问，不要在 `ExecutionState` 上增加
  `pending_futures`、`resumable_simulations` 或 `stop_signal` 影子字段。
- queue-busy 重试只作用于候选键，统一由 `QueueRetryState` 管理；不要因为单个模板拥塞
  跳过整个字段，也不要重新引入字段级拥塞计数或跳过集合。
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

## 跨平台边界

- 代码和测试必须兼容 Windows 与 macOS。路径处理优先使用 `pathlib.Path`、`os.PathLike`
  或仓库已有路径封装，不要拼接硬编码 `/`、`\`、盘符或用户目录。
- 运行时代码不要依赖 POSIX-only shell 命令、macOS 专用工具或大小写敏感文件系统行为。
  必须调用外部命令时，优先使用 Python 标准库并显式处理 Windows 与 macOS 差异。
- 文件锁、凭证存储、换行、临时目录和权限逻辑应走仓库已有抽象；新增平台分支时补充聚焦测试。
- Makefile 只作为快捷入口；跨平台仓库检查和开发清理逻辑应优先放在 `scripts/*.py`
  中，避免把复杂规则写成 shell 片段。

## 仓库数据规则

- 可编辑配置位于根目录 `config/*.yaml`；包内镜像位于
  `src/alpha/resources/config/*.yaml`，修改后必须通过 `make sync-config` 或
  `make config-sync-check` 保持同步。
- 数据集长期资产放在 `datasets/<dataset_id>/` 下。
- `datasets/<dataset_id>/blacklist.json` 是人工维护的长期策略资产；运行过程只读取，
  不应根据回测结果自动改写该文件。
- `cache/`、`runs/`、`feedback/`、`.credentials/`、工具缓存和本地生成状态属于私密或可重建内容，不应提交。
- 不要提交明文凭证、Authorization header 或平台密钥。`make scan-secrets` 会覆盖当前已知模式。

## 测试与检查

- 常规代码改动后运行：

```bash
make test
```

- 修改 Python 文件后，对触达文件运行定向 Ruff 检查，例如：

```bash
ruff check src/alpha/app/planning.py tests/unit/test_planning.py
```

- 较大交付前优先运行：

```bash
make check
```

- Windows 或没有 `make` 的环境可直接运行完整跨平台检查：

```bash
py -3.10 scripts/check_all.py
```

- 请在 Python 3.10+ 的虚拟环境里运行检查。Makefile 会优先选择可用的 3.10
  解释器；需要显式解释器时，macOS 可用 `make check PYTHON=python3.10`，
  Windows 可用 `make check PYTHON="py -3.10"`，也可以使用已激活虚拟环境中的
  `python`。

## 修改纪律

- 每次重构尽量只切一个边界。好的粒度包括：合并 dry-run/live 资源加载、收窄一个 args-like 函数边界、从 `ExecutionState` 抽出一个状态职责。
- 除非用户明确要求，不要把研究策略、平台行为变化和架构清理混在同一个 patch 里。
- 修改 planning 相关代码时，必须守住 dry-run 不联网、不写运行产物的保证。
- 跨边界移动行为时，补充聚焦测试；测试也应改用新的边界对象，而不是继续伪造宽泛 namespace。
- 避免留下陈旧 `TODO`、`FIXME`、`HACK` 注释；后续工作请放到明确的 issue 或用户可见总结里。
