# WorldQuant Brain Alpha Runner

通用的 WorldQuant Brain 数据集 Alpha 模拟/检查/提交运行器。

## 文档导航

- 通用学习与问题索引：先看 [docs/README.md](docs/README.md)
- 数据集专属策略：看 `templates/<dataset_id>/README.md`
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
│   ├── app/               # 应用编排：bootstrap / run_loop / finalize / clean
│   ├── core/              # 调度、simulation、checkpoint、template planning
│   ├── generators/        # 字段变换、表达式候选、模板变体、payload
│   ├── analysis/          # 反馈、统计、report、template-registry sidecars
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
├── templates/             # 数据集模板库与说明
├── blacklists/            # 数据集 blacklist
├── docs/                  # 四篇主文档 + 索引
└── tests/                 # unit / integration
```

## 仓库边界

哪些文件进仓：

- `config/*.yaml`：统一配置入口，按职责维护默认运行参数、数据集 profile、表达式策略、质量阈值和模板参数。
- `templates/<dataset_id>/`：数据集专属模板、聚焦字段/模板白名单，以及经过验证值得复用的本地 refine 模板。
- `templates/<dataset_id>/refine/fields/*.txt`：少量、可复用、人工裁剪的字段白名单；它们服务于稳定复现实验，不应再混入 `cache/`。
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

- 数据集专属模板库：`templates/<dataset_id>/library.json`
- 数据集专属模板说明：`templates/<dataset_id>/README.md`
- 数据集聚焦白名单：可选放在 `templates/<dataset_id>/*.txt`
- 数据集 refine 模板库：可选放在 `templates/<dataset_id>/refine/*.json`

当前实现采用“数据集专属模板库”模式：

- 每个数据集都显式维护自己的 `library.json`
- 运行时直接读取该数据集模板库，不做额外模板继承
- 真正的搜索方向应直接在数据集专属目录里定制和收敛

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

- `main.py` / `__main__.py`：CLI 入口与顶层异常处理
- `app/`：应用编排层，负责初始化、执行主循环、最终收尾和 `clean`
- `core/`：核心执行层，负责 scheduler、simulation、checkpoint、template planning
- `generators/`：字段预处理、表达式候选构造、settings 变体、模板细分策略
- `analysis/`：反馈画像、失败检查、字段/模板统计、report 和 template-registry sidecars
- `api/`：Brain API 会话、重试、fields、simulations、alphas
- `io/`：凭证、results journal、输出 sidecar、原子写入
- `cli/`：参数解析、路径归一化、run config、filters
- `models/` + `runtime/`：领域模型、运行配置对象、运行期上下文和可变状态
- `policy/`：expression policy 与 blacklist 相关运行策略
- `config/`：代码侧配置入口；根 `config/*.yaml` 提供可调默认值

补充说明：

- 内部代码现在优先直接依赖具体模块，不再鼓励继续增加新的“兼容壳”。
- 包级 facade 仍然保留在 `alpha.models`、`alpha.core`、`alpha.config` 等入口，用来维持已有导入路径稳定。
- 如果 README 的结构说明再次过期，应优先更新这里的高层分层说明，而不是回到逐文件枚举。

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
- 模板本身优先放在 `templates/<dataset_id>/` 下维护，而不是继续把模板内容塞回 Python 常量

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

根 `README` 只保留通用运行方法，不长期维护具体数据集的作战细节。

- `fundamental6`、`model51`、`model16` 的当前策略，统一下沉到对应的 `templates/<dataset_id>/README.md`
- 如果某个数据集有聚焦字段白名单、模板白名单、refine 包，也应优先放在对应模板目录说明里维护
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
- `config/policy.py`：dataset expression policy 构建与反馈阶段解析
- `config/profiles.py`：dataset profile fallback

YAML 分层优先级为：`config/settings.yaml` > `config/expression_policies.yaml` > `config/dataset_profiles.yaml` > `config/templates.yaml` / `config/quality_feedback.yaml` > `config/constants_defaults.yaml`。其中 `config/settings.yaml` 面向日常运行调参，其余 `config/*.yaml` 面向按职责拆分的默认值；`templates/` 面向表达式模板，`blacklists/` 面向低质量模板过滤。

实际运行配置优先维护在 `config/*.yaml`、`templates/` 和 `blacklists/`，不要把数据集专属模板重新塞回 Python 常量。

## 结果解读

当前仓库的默认运行语义是：

- 只做 `simulation + check-submit`
- 产出 `submittable / submitted` 状态字段
- 不会自动向平台执行正式 `submit`

也就是说，当前看到的：

- `submittable=true` = 这条 Alpha 通过了本轮检查，具备后续人工提交价值
- `submitted=false` = 仍然没有被本地 runner 自动正式提交

如果后续要做正式提交，仍然需要人工干预，而不是依赖默认 CLI 运行流程。

每次运行至少会生成一组结果文件；若未显式指定 `--output`，常见默认命名如下：

| 文件 | 用途 |
|------|------|
| `results/<dataset>/test_results.json` | 原始结果（每个模拟的详细数据） |
| `results/<dataset>/test_results_analysis.json` | 分析汇总（用于决策下一步） |

### 关键分析字段

| 字段 | 含义 | 如何使用 |
|------|------|----------|
| `submittable_count` | 通过本轮 check-submit 的数量 | =0 时继续优化；>0 也不代表已自动提交 |
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
