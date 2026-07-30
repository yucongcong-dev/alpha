# WorldQuant Brain Alpha Runner

通用的 WorldQuant Brain 数据集 Alpha 模拟/检查/提交运行器。

## 文档导航

- 通用学习与问题索引：先看 [docs/README.md](docs/README.md)
- 数据集专属策略：看 `datasets/<dataset_id>/README.md`
- 想快速上手仓库：继续看本文档的“安装 / 运行 / 结果解读”

## Python 版本

- 最低要求：`Python 3.10`
- 推荐：`Python 3.10+`
- 项目根目录已补 `.python-version=3.10`，便于 `pyenv` / IDE 自动选中兼容解释器
- 下文里的 `python3.10` 可以替换成任意 `3.10+` 解释器路径

## 项目结构

```
alpha/
├── src/alpha/             # 主包
│   ├── __main__.py        # `python3.10 -m alpha` 入口
│   ├── main.py            # 精简 CLI 主入口
│   ├── workspace.py       # 可写工作区与只读资源根目录
│   ├── app/               # 应用编排：bootstrap / run_loop / finalize / clean
│   ├── core/              # 调度、simulation、恢复状态、template planning
│   ├── generators/        # 字段变换、表达式候选、模板变体、payload
│   ├── selection/         # 在线候选剪枝、模板角色与 settings 预算决策
│   ├── analysis/          # 历史聚合、统计、report 与派生结果视图持久化
│   ├── api/               # Brain API 客户端、session、retry、fields、alphas
│   ├── io/                # 凭证、输出路径、results journal、原子写入
│   ├── cli/               # 参数解析、路径归一化、run config、filters
│   ├── models/            # 领域模型、io types、runtime options/protocols
│   ├── runtime/           # 运行期上下文与可变状态
│   ├── policy/            # expression policy、blacklist runtime/store
│   ├── config/            # 配置常量、YAML、profiles、policy overrides
│   └── utils/             # 通用 helpers
├── config/                # YAML 配置
│   ├── settings.yaml
│   ├── dataset_profiles.yaml
│   ├── expression_policies.yaml
│   ├── quality_feedback.yaml
│   ├── templates.yaml
│   └── constants_defaults.yaml
├── datasets/              # 每个 dataset 的模板、黑名单、presets、缓存和运行结果
├── docs/                  # 四篇主文档 + 索引
└── tests/                 # unit / integration
```

## 仓库边界

哪些文件进仓：

- `config/*.yaml`：唯一可编辑的 YAML 配置源，按职责维护默认运行参数、数据集 profile、表达式策略、质量阈值和模板参数。
- `datasets/<dataset_id>/template.json`：数据集专属默认模板库。
- `datasets/<dataset_id>/presets/`：按研究目的集中保存专项模板、字段清单和模板筛选清单。
- `datasets/<dataset_id>/blacklist.json`：统一黑名单。脚本会自动追加，也允许人工维护；空黑名单也可以进仓，用于固定数据集目录边界。

哪些文件不进仓：

- `datasets/<dataset_id>/runs/`：每次运行的结果、分析、日志、可恢复 state 和中断诊断报告。
- `datasets/<dataset_id>/feedback/<market_scope>/`：按 region、universe、instrument、delay 隔离的跨 run 本地反馈仓；保存结果 journal、字段反馈、run 索引和模板 registry，不进仓。
- `datasets/<dataset_id>/cache/`：磁盘上的可重建缓存目录。当前主要承载字段缓存；内存态的 YAML / blacklist / runtime cache 不落在这里。
- `tmp/`：一次性实验输入、临时 include/exclude 列表、临时模板库。
- `scratch/`：外部脚本、对照材料、手工实验草稿。
- `.credentials/`：本地 Fernet 加密凭证和独立密钥；两个文件都会收紧为仅当前用户可读写（`0600`）。

根目录只保留项目入口和说明文件。配置统一放 `config/`；临时文件不要放根目录。如果只是一次性实验，放 `tmp/`；如果已经验证值得长期复用，再整理命名后放入对应数据集的 `template.json` 或 `presets/`。

## 结果目录约定

`datasets/<dataset_id>/runs/` 是纯运行产物目录，不进仓。每次实验使用独立的 `run_name`，例如：

- `20260727-explore-overnight`：广泛探索、overnight sweep、初筛轮次
- `20260727-refine-cashflow`：局部精修、triplet/density/window 等 focused 轮次
- `20260727-compare-neutralization`：同一字段或同一家族的对照实验
- `20260727-scratch-filter-probe`：短期排障或临时验证

runner 会把每个完成 run 去重合并到 `datasets/<dataset_id>/feedback/<market_scope>/`，供相同市场范围的后续 run 自动跳过已尝试组合、继承模板 registry 和选择 near-pass 候选。合并过程由事务锁保护，并按提交终态、revision 和时间解决重复记录冲突；`run_index.json` 让启动阶段只加载新增或变化的 run。它仍是可重建的本地研究状态；成熟结论应继续沉淀到 `template.json`、现役 `presets/` 或 dataset README。结论完成沉淀后，可删除对应 `runs/`。

## 模板资产

模板资产直接放在对应 dataset 根目录：

- 数据集专属模板库：`datasets/<dataset_id>/template.json`
- 数据集专属模板说明：`datasets/<dataset_id>/README.md`
- 专项运行预设：`datasets/<dataset_id>/presets/<name>/`
- 预设内可按需提供 `template.json`、`fields.txt` 和 `templates.txt`
- 历史或失败预设不长期保留；把关键结论写入 dataset README 后删除可执行副本

当前实现采用“数据集专属模板库”模式：

- 每个数据集都显式维护自己的 `template.json`
- 运行时直接读取该数据集模板库，不做额外模板继承
- 缺失的模板 priority 只在内存中按文件顺序补齐，运行启动不会改写模板源文件
- 真正的搜索方向应直接在数据集专属目录里定制和收敛

代码中的模板相关逻辑统一放在 `src/alpha/generators/templates/`：

- `__init__.py`：仅保留历史公开导入路径的兼容 facade
- `library_loader.py`：加载并校验 JSON 模板库
- `library_store.py`：检查数据集模板库并补齐内存态 priority
- `candidates.py`：统一构造 `TemplateCandidate`
- `classification.py`：识别模板 family / stage
- `metadata.py`：构建模板 metadata 索引
- `partner_fields.py`：为 ratio 模板发现配对字段
- `priority.py`：自适应优先级、相似度惩罚、family 数量裁剪
- `refine.py`：near-pass 候选的局部精修
- `variations.py`：feedback mutation、bucket group、trade_when、历史优秀表达式复用

## 黑名单文件

- 统一黑名单：`datasets/<dataset_id>/blacklist.json`。
- 当运行结果持续不佳时，脚本会直接把低质量模板追加到该文件，下次运行自动跳过。
- 你也可以手工编辑同一个文件，用于补充明确不想再跑的模板或表达式规则。

## 当前代码分层

- `main.py` / `__main__.py`：CLI 入口与顶层异常处理
- `ApplicationConfig`：CLI/YAML 合并完成后的不可变运行配置；`argparse.Namespace` 不进入主运行链路
- `WorkspacePaths`：统一管理可写工作区和只读配置资源；可用 `ALPHA_WORKSPACE_ROOT` 显式指定工作区
- `app/`：应用编排层，负责初始化、执行主循环、最终收尾和 `clean`
- `core/`：核心执行层，负责 scheduler、simulation、恢复状态和 template planning
- `generators/`：字段预处理、表达式候选构造、settings 变体、模板细分策略
- `selection/`：在线候选剪枝、模板执行角色、activation scope 和 settings 预算
- `analysis/`：历史反馈聚合、失败检查、字段/模板统计、report 和派生结果视图持久化
- `api/`：Brain API 会话、重试、fields、simulations、alphas
- `io/`：凭证、results journal、输出路径和原子文件写入
- `cli/`：参数解析、路径归一化、run config、filters
- `models/` + `runtime/`：领域模型、运行配置对象、运行期上下文和可变状态
- `policy/`：expression policy 与 blacklist 相关运行策略
- `config/`：代码侧配置入口；根 `config/*.yaml` 提供可调默认值

补充说明：

- 内部代码现在优先直接依赖具体模块，不再鼓励继续增加新的“兼容壳”。
- 包级 facade 仍然保留在 `alpha.models`、`alpha.core`、`alpha.config` 等入口，用来维持已有导入路径稳定。
- 生产代码使用具体模块导入；facade 只承担外部兼容，不再参与内部依赖方向。
- 如果 README 的结构说明再次过期，应优先更新这里的高层分层说明，而不是回到逐文件枚举。

这次重构的目标是把原先集中在少数大文件里的职责拆开，让入口、运行态、分析构建、配置、模板生成、策略和 IO 边界更清晰。旧入口仍保持兼容，例如 `from alpha.config import get_yaml_config`、`from alpha.generators.templates import load_template_library` 仍然可用。

## 安装

```bash
# 开发模式安装（推荐）
python3.10 -m pip install -e .

# 如果在 config/settings.yaml 启用 httpx 后端，同时安装 HTTP/2 可选依赖
python3.10 -m pip install -e ".[httpx]"

# 安装后可直接运行
alpha --smoke-test

# 或直接使用 PYTHONPATH 运行
export PYTHONPATH=src
python3.10 -m alpha --smoke-test
```

`alpha` 控制台命令与 `python3.10 -m alpha` 使用同一入口；如果误用低于 3.10 的解释器，入口会直接报告当前版本并退出，不再进入包内模块后才出现语法错误。

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
`datasets/<dataset>/cache/<cache_key>.json`，
其中 `cache_key` 由 `region + universe + instrument_type + delay` 生成，例如
`usa_top3000_equity_d1`，
后续同一 `dataset_id + region + universe + instrument_type + delay` 组合直接复用缓存。

**目标**：从数据集中找出有潜力的字段和模板家族。

**字段筛选与排序**：
- 先应用 `include_fields` / `exclude_fields`
- 再用官网返回的字段元数据做基础过滤：`coverage`、`dateCoverage`、`alphaCount`、`userCount`
- 未配置专属策略的新数据集也会继承通用质量门槛、拥挤度上限和非零评分权重
- 官网指标使用固定尺度评分，不会因为临时 include 列表变化而整体改写相对分数
- `alphaCount / userCount` 先提供适度验证奖励，超过拥挤起点后才逐步扣分
- 未探索字段默认保留 40% 的有限预算；其余 exploitation 预算只给历史优质字段，普通失败记录不会占用该配额
- 任一已通过 submission 检查的 Alpha 会立即成为强正反馈；其余历史反馈需要达到最小尝试次数才会被标记为强反馈，并按最近结果时间做半衰期衰减
- 未探索字段默认优先 `MATRIX`，但已有可靠历史反馈的字段仍按历史表现排序
- 数字期限片段（包括 `*_last_30_days_spy` 这类带标的后缀的字段）会折叠为字段族，每个家族默认最多先取 2 个代表字段，优先 30/60/90 等常用窗口
- 最后才应用 `offset` / `limit`
- 默认启用 breadth-first 调度：前 200 个字段先各试 2 个高优模板，再在后续轮次逐步补深

`--include-fields-file` 表示人工明确指定字段，因此不会再应用字段族配额和探索比例；基础质量门槛仍然有效。`--dry-run-plan` 会输出字段原始排名、评分、字段族、入选原因、不可执行字段数以及各类过滤计数。若全局模板历史将一个未探索字段的所有模板剪枝，执行器仅保留一个结构合法的种子模板，避免计划出现“选中字段但零模拟”的空跑。

**官网字段指标使用方式**：
- `coverage`：横截面覆盖率，正向质量信号
- `dateCoverage`：时间覆盖率，正向质量信号
- `alphaCount`：历史 alpha 使用量；低于门槛视为验证不足，适度使用提供验证，过高才进入拥挤惩罚
- `userCount`：历史用户使用量；采用同样的“验证区间 + 拥挤区间”逻辑
- `dateCreated`：较新的字段有轻微加分
- `themes`：主题标签数量仅作很弱的辅助加分
- 字段指标缺失时不会直接误删字段，而是记录缺失计数并降低排序分数

**表达式策略配置**：
- 数据集级表达式搜索策略可在 `config/expression_policies.yaml` 或 `config/settings.yaml` 的 `expression_policies.<dataset_id>` 下覆盖
- 字段优先级既支持完整字段 ID，也支持 `value`、`quality` 等语义 token；未知配置键会记录告警并忽略，避免配置看似生效但实际未加载
- 适合放这里的参数包括：`partner_limit`、字段质量阈值、反馈阶段设置、少量运行期策略开关
- `policy_version` 标识启发式版本，失败反馈默认按 `field_type` 隔离
- `evaluation_holdout_percent` 会按 dataset/field/version 稳定分配对照组；holdout 不应用自适应优先级
- 默认模板优先维护在 `datasets/<dataset_id>/template.json`，专项运行资产集中放在 `presets/`，不要把模板内容塞回 Python 常量

**输出**：默认 `datasets/<dataset>/runs/<run_name>/analysis.json` 中的关键字段：
- `near_pass_summary`：接近通过的候选（按 score 排序）
- `failed_check_leaderboard`：主要失败原因分布
- `optimization_hints`：自动生成的优化建议
- `pending_check_count`：仍存在未决 submission check 的结果数量

**预估时间**：30-70 分钟（默认先覆盖 200 字段，但每轮每字段只浅试少量高优模板）

**关于 `SELF_CORRELATION=PENDING` 的当前流程**：
- `PENDING` 不等于通过；这类结果会以 `submittable=null` 落盘，并在 `failed_checks` 中保留原始未决检查
- 未决结果仍算一次已经执行的组合，续跑时不会重复创建相同 simulation
- 未决结果不会参与模板统计、字段反馈画像、near-pass 排行、failed-check 学习和策略效果评估
- 后续正常启动时会先重新查询历史记录中仍为 `PENDING` 且已有 `alpha_id` 的 submission checks；只刷新检查结果，不会重新创建 simulation
- 如果平台仍返回 `PENDING`，结果会继续保持未决，等待下一次启动再查询

**关于平台队列拥塞的当前流程**：
- 全局并发冷却仍然生效，避免平台繁忙时持续创建新 simulation
- `--field-queue-busy-skip-after` 保留旧参数名，但现在按“字段 + 模板 + 表达式 + settings”候选分别计数，不会因为一个候选排队超时而跳过整个字段
- 候选达到阈值后只在当前进程中停止重试；队列计数不写入 state，重启后可重新尝试

`--stop-after-submittable N` 只统计本次启动后新增的可提交 Alpha；输出文件中的历史可提交结果仍用于续跑和分析，但不会让新进程一启动就提前停止。

#### 阶段 3：聚焦深挖（针对高反馈字段）

```bash
python3.10 -m alpha --top-fields-by-feedback 10 --max-templates-per-field 15
```

**目标**：对接近通过的候选进行精修，而不是继续做一轮广泛模板扩张。

**机制**：
- `generate` 阶段固定结构优先：promoted、broad 和 high-coverage 标签不会自动增加 settings 变体预算
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
- `--output` 默认指向当前 run；`--feedback-output` 默认指向 `datasets/<dataset>/feedback/<region>_<universe>_<instrument>_d<delay>/summary.json`
- 新 run 只恢复自己的运行结果，但候选选择会读取 dataset 级反馈、模板 registry 和已尝试组合
- run 正常收尾时会把新结果按字段、表达式和 settings 指纹去重合并回 dataset 反馈仓
- 阶段 2 的结果会自动用于字段优先级排序和 near-pass 候选筛选
- 可多次运行，每次自动续跑（不重复已完成的组合）
- 如果阶段 2 产生较多未决检查，先在平台确认终态，再决定是否继续 refine；runner 不会把它们当作普通 near-pass 历史

**当前实现状态**：
- 阶段 1：环境验证
- 阶段 2：breadth-first 广泛探索
- 阶段 3：candidate-centric refine / resimulate

**预估时间**：通常短于阶段 2，因为会把预算收缩到少数 near-pass 候选，而不是继续全模板铺开

#### 数据集 Playbooks

根 `README` 只保留通用运行方法，不长期维护具体数据集的作战细节。

- `fundamental6`、`model51`、`model16` 的当前策略，统一下沉到对应的 `datasets/<dataset_id>/README.md`
- 如果某个数据集有聚焦字段白名单、模板白名单、专项模板包，也应在对应 dataset 的 README 中维护
- 根文档只回答“怎么运行这个仓库”，数据集文档再回答“这个数据集现在该怎么跑”

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
- 按 `Ctrl+C` 时会通知轮询 worker 停止、取消尚未启动的任务并立即保存 `state.json` 与 `interrupt_report.json`；恢复只读取 state，已经拿到 Location 的远端 simulation 会在下次运行继续轮询
- 中断后再次运行自动继续
- 如需重新开始，优先使用新的 `--run-name`；显式 `--output` 仍用于兼容自定义路径

### 其他命令

预览下一次运行而不创建模拟任务：

```bash
python3.10 -m alpha --dry-run-plan
```

该命令是只读离线预览：不会读取登录凭证、连接 Brain、创建 simulation，
也不会初始化或重写结果、journal、state、中断诊断报告和日志文件。它会复用当前数据集上下文的
本地字段缓存（即使缓存已超过在线刷新 TTL）；若没有匹配缓存，会提示先执行一次正常认证运行。

首次生成或复用本地字段缓存：

```bash
python3.10 -m alpha
```

字段缓存会校验完整 market scope、TTL 和字段结构；全部记录无效时会自动重新从 API 拉取，重复 field ID 只保留第一条。

所有相对路径参数（如 `--output`、`--fields-cache-file`、`--include-fields-file`）都相对于当前命令执行目录解析。

运行时默认路径统一从工作区根目录派生。工作区选择优先级是：

1. `ALPHA_WORKSPACE_ROOT` 显式指定的目录。
2. 源码仓库根目录，或包含 `datasets/`、`config/` 等标记的当前目录。
3. 用户目录下的 `~/.alpha/`。

单个文件参数（如 `--output`、`--template-library-file`）仍可显式覆盖默认路径。

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

清理 Python 字节码、检查工具缓存和开发安装产生的包元数据：

```bash
make clean-dev
```

`alpha clean` 只负责数据集的 `cache/`、`runs/` 和迁移前遗留的根目录
`cache/`、`results/`；`make clean-dev` 只负责 `__pycache__`、`.pycache`、
`.mypy_cache`、`.pytest_cache`、`.ruff_cache`、coverage 和 `*.egg-info` 等
可重建的开发环境产物。

### YAML 开关覆盖

YAML 中打开的布尔开关可以用对应的 `--no-*` 在命令行临时关闭：

```bash
python3.10 -m alpha --no-auto-update-blacklist
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
- `config/policy_overrides.py`：解析并应用 dataset expression policy 的 YAML 覆盖
- `config/policy_coercers.py`：把 YAML policy 值转换成类型化配置
- `config/profiles.py`：dataset profile fallback

YAML 分层优先级为：`config/settings.yaml` > `config/expression_policies.yaml` > `config/dataset_profiles.yaml` > `config/templates.yaml` / `config/quality_feedback.yaml` > `config/constants_defaults.yaml`。其中 `config/settings.yaml` 面向日常运行调参，其余 `config/*.yaml` 面向按职责拆分的默认值；dataset 根目录的 `template.json` 与 `presets/` 面向表达式模板和定向运行输入，`blacklist.json` 面向低质量模板过滤。

实际运行配置优先维护在 `config/*.yaml` 和对应的 dataset 目录中，不要把数据集专属模板重新塞回 Python 常量。

`src/alpha/resources/config/*.yaml` 只是安装包使用的生成镜像，不要直接编辑。修改根
`config/*.yaml` 后运行 `make sync-config`；`make check` 会验证文件名和内容完全一致。

## 结果解读

当前仓库的默认运行语义是：

- 只做 `simulation + check-submit`
- 产出 `submittable / submitted` 状态字段
- 不会自动向平台执行正式 `submit`

也就是说，当前看到的：

- `submittable=true` = 这条 Alpha 通过了本轮检查，具备后续人工提交价值
- `submitted=false` = 仍然没有被本地 runner 自动正式提交

如果后续要做正式提交，仍然需要人工干预，而不是依赖默认 CLI 运行流程。

每次运行至少会生成一组结果文件；若未显式指定 `--output`，默认目录如下：

| 文件 | 用途 |
|------|------|
| `datasets/<dataset>/runs/<run_name>/summary.json` | 轻量运行 summary 与 journal 指针 |
| `datasets/<dataset>/runs/<run_name>/results.jsonl` | 权威结果 journal；主 summary 和分析文件都可由它重建 |
| `datasets/<dataset>/runs/<run_name>/analysis.json` | 分析汇总（用于决策下一步） |
| `datasets/<dataset>/feedback/<market_scope>/summary.json` | 同一市场范围的跨 run 反馈 summary；journal 指针使用相对路径 |
| `datasets/<dataset>/feedback/<market_scope>/results.jsonl` | 带 run/source/time/revision 数据血缘的去重结果历史 |
| `datasets/<dataset>/feedback/<market_scope>/run_index.json` | 已聚合 run 的轻量签名索引；只重新读取新增或变化的 summary |

### 关键分析字段

| 字段 | 含义 | 如何使用 |
|------|------|----------|
| `submittable_count` | 通过本轮 check-submit 的数量 | =0 时继续优化；>0 也不代表已自动提交 |
| `near_pass_summary` | 接近通过的候选 | score > 0.5 的优先深挖 |
| `failed_check_leaderboard` | 失败原因分布 | 看主要卡点是 LOW_SHARPE 还是 LOW_FITNESS |
| `optimization_hints` | 自动生成的建议 | 直接参考执行 |
| `template_performance_summary` | 模板家族表现 | 看哪些模板类型效果好 |
| `field_performance_summary` | 字段表现 | 看哪些字段有潜力 |
| `policy_evaluation` | 按策略版本和 adaptive/holdout 分组的通过率 | 判断自适应启发式是否真正优于对照组 |

结果恢复以 JSONL journal 为唯一事实来源。`summary.json`、analysis 和 template registry
都是派生视图；启动时缺失的分析边车只会被重建，不会反向改写 journal 或主 summary。
每条结果同时保存实际 simulation `settings` 和平台返回的完整 `is` 指标字典 `metrics`，
因此通过检查的 Alpha 也可以在本地按 Sharpe、Fitness、Turnover 等指标继续比较。

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

`make check` 同时要求分支覆盖率不低于 `80%`。如只想单独运行覆盖率检查：

```bash
make coverage-check
```
也可以分步运行：

```bash
make test
make help-check
make docs-check
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
make package
```

`make package` 会先同步包内 YAML 镜像，再生成 `dist/` 下的发布包。
