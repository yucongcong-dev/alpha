# WorldQuant Brain Alpha Runner

通用的 WorldQuant Brain 数据集 Alpha 模拟/检查/提交运行器。

## 项目结构

```
alpha/                     # 项目根目录
├── src/                   # 源码目录
│   └── alpha/             # 主包
│       ├── __init__.py    # 包入口（导出基础公共 API）
│       ├── __main__.py    # python3 -m alpha / alpha 命令入口
│       ├── main.py        # 精简入口与兼容导出
│       ├── bootstrap.py   # 初始化阶段：参数、字段、模板、历史状态
│       ├── run_loop.py    # 主运行循环：调度、反馈刷新、续跑推进
│       ├── finalize.py    # 收尾阶段：最终落盘与清理
│       │
│       ├── core/          # 核心业务层
│       │   ├── checkpoint.py
│       │   ├── executor.py
│       │   ├── scheduler.py
│       │   └── simulation.py
│       │
│       ├── generators/    # Alpha 生成层
│       │   ├── templates.py
│       │   ├── expressions.py
│       │   ├── fields.py
│       │   └── settings.py
│       │
│       ├── analysis/      # 分析优化层
│       │   ├── stats.py
│       │   ├── feedback.py
│       │   └── report_builder.py
│       │
│       ├── api/           # API 客户端层
│       │   ├── api_types.py
│       │   └── client.py
│       │
│       ├── io/            # 输入输出层
│       │   ├── common.py
│       │   ├── credentials.py
│       │   └── output.py
│       │
│       ├── cli/           # 命令行接口层
│       │   ├── filters.py
│       │   └── parser.py
│       │
│       ├── models/        # 数据模型层
│       │   ├── domain.py
│       │   ├── runtime.py
│       │   ├── io_types.py
│       │   └── base.py    # 兼容导出层
│       │
│       ├── policy/        # 运行期策略层
│       │   └── blacklist.py
│       │
│       ├── utils/         # 工具函数层
│       │   └── helpers.py
│       │
│       ├── config.py      # 配置常量
│       └── exceptions.py  # 自定义异常
│
├── tests/                 # 测试目录
│   ├── unit/              # 单元测试
│   └── integration/       # 集成测试
│
├── README.md              # 项目说明
├── requirements.txt       # 依赖
├── pyproject.toml         # 项目配置
├── settings.yaml          # 默认运行配置
├── data/                  # 模板库与黑名单
│   ├── templates/
│   │   ├── base/          # 基础共享模板库与说明
│   │   ├── fundamental6/  # fundamental6 专属模板库与说明
│   │   ├── model16/       # model16 专属模板库与说明
│   │   └── model51/       # model51 专属模板库与说明
│   └── blacklists/        # dataset 专属 blacklist
└── .gitignore
```

## 模板目录

当前模板目录统一放在 `data/templates/`：

- 基础共享模板库：`data/templates/base/library.json`
- 基础模板说明：`data/templates/base/README.md`
- 数据集专属模板库：`data/templates/<dataset_id>/library.json`
- 数据集专属模板说明：`data/templates/<dataset_id>/README.md`
- 数据集聚焦白名单：可选放在 `data/templates/<dataset_id>/*.txt`

其中 `base` 只负责提供共享 fallback 模板，真正的搜索方向应尽量在数据集专属目录里定制和收敛。

## 当前代码分层

- `main.py` 现在只保留精简入口和兼容导出，具体实现已经拆到 `bootstrap.py`、`run_loop.py`、`finalize.py`
- `models/domain.py` 只放领域对象；`models/runtime.py` 放运行态上下文；`models/io_types.py` 放路径/过滤边界对象；`models/base.py` 仅保留兼容导出
- `analysis/report_builder.py` 负责从结果构建 summary/analysis payload
- `policy/blacklist.py` 负责黑名单策略、聚合与增量更新
- `io/output.py` 负责结果持久化与分析边车编排，不再承载黑名单策略实现
- `io/common.py` 放更底层的 JSON 原子写入、路径常量、dataset 文件名安全化与运行时 `data/` 目录解析

这次重构的目标是把原先集中在 `main.py`、`models/base.py`、`io/output.py` 的大杂烩职责拆开，让入口、运行态、分析构建、策略和 IO 边界更清晰。

## 安装

```bash
# 开发模式安装（推荐）
python3 -m pip install -e .

# 安装后可直接运行
alpha --smoke-test

# 或直接使用 PYTHONPATH 运行
export PYTHONPATH=src
python3 -m alpha --smoke-test
```

## 运行

### 推荐工作流

Alpha 发现是一个**迭代优化**过程，建议按以下阶段执行：

#### 阶段 1：环境验证（冒烟测试）

```bash
python3 -m alpha --smoke-test
```

验证：登录认证、API 连通性、模拟创建、401 重认证。
全部 PASS 后方可继续。

#### 阶段 2：广泛探索（发现候选字段）

```bash
python3 -m alpha
```

不传参时使用内置默认值（`--limit 200 --max-templates-per-field 6 --field-template-batch-size 2`）。
首次运行会先按当前数据集上下文全量拉取字段并写入
`cache/fields/<dataset>/<region>/<universe>/<instrument_type>/delay<delay>/fields.json`，
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
- 数据集级表达式搜索策略可在 `settings.yaml` 的 `expression_policies.<dataset_id>` 下覆盖
- 适合放这里的参数包括：`partner_limit`、字段质量阈值、反馈阶段设置、少量运行期策略开关
- 模板本身优先放在 `data/templates/base/` 或 `data/templates/<dataset_id>/` 下维护，而不是继续把模板内容塞回 Python 常量

**输出**：`*_analysis.json` 中的关键字段：
- `near_pass_summary`：接近通过的候选（按 score 排序）
- `failed_check_leaderboard`：主要失败原因分布
- `optimization_hints`：自动生成的优化建议

**预估时间**：30-70 分钟（默认先覆盖 200 字段，但每轮每字段只浅试少量高优模板）

#### 阶段 3：聚焦深挖（针对高反馈字段）

```bash
python3 -m alpha --top-fields-by-feedback 10 --max-templates-per-field 15
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
- 默认读取同一输出文件（`results/fundamental6/test_results.json`）
- 阶段 2 的结果会自动用于字段优先级排序和 near-pass 候选筛选
- 可多次运行，每次自动续跑（不重复已完成的组合）

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
  - `data/templates/model51/focused_fields.txt`
  - `data/templates/model51/focused_templates.txt`

示例：

```bash
python3 -m alpha --dataset-id model51 --dry-run-plan \
  --include-fields-file data/templates/model51/focused_fields.txt \
  --include-templates-file data/templates/model51/focused_templates.txt \
  --limit 4 --max-templates-per-field 4 --max-templates-per-family 1 \
  --output results/model51/focused_validation.json \
  --feedback-output results/model51/focused_validation.json \
  --no-auto-update-blacklist
```

```bash
python3 -m alpha --dataset-id model51 \
  --include-fields-file data/templates/model51/focused_fields.txt \
  --include-templates-file data/templates/model51/focused_templates.txt \
  --limit 4 --max-templates-per-field 4 --max-templates-per-family 1 \
  --max-concurrent-simulations 2 --max-concurrent-creates 1 \
  --output results/model51/focused_validation.json \
  --feedback-output results/model51/focused_validation.json \
  --no-auto-update-blacklist
```

#### 阶段 4：完整运行（可选）

```bash
python3 -m alpha --full-run
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

---

### 其他命令

预览下一次运行而不创建模拟任务：

```bash
python3 -m alpha --dry-run-plan
```

首次生成或复用本地字段缓存：

```bash
python3 -m alpha
```

所有相对路径参数（如 `--output`、`--fields-cache-file`、`--include-fields-file`）都相对于当前命令执行目录解析。

运行时 `data/` 目录也遵循类似优先级：
- 显式传入的 `data_dir`
- 当前命令执行目录下的 `data/`
- 项目内置 `data/`

这意味着你可以在临时工作目录放一份独立的 `data/templates/` 或 `data/blacklists/`，而不用改动仓库内置数据。

清理本地运行产物（默认保留 `.credentials/`）：

```bash
python3 -m alpha clean
```

预览清理内容，不实际删除：

```bash
python3 -m alpha clean --dry-run-clean
```

如确实需要同时删除本地加密凭据：

```bash
python3 -m alpha clean --include-credentials
```

### YAML 开关覆盖

YAML 中打开的布尔开关可以用 `--no-*` 在命令行临时关闭：

```bash
python3 -m alpha --no-submit --no-auto-update-blacklist
python3 -m alpha --no-smoke-test --no-full-run
```

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
PYTHONPATH=src python3 -m pytest -q
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
python3 -m pip install -e ".[dev]"
python3 -m ruff check .
python3 -m ruff format .
```

## 打包发布

```bash
python3 -m pip install build
python3 -m build
```

生成的包在 `dist/` 目录下。
