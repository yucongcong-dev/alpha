# WorldQuant Brain Alpha Runner

通用的 WorldQuant Brain 数据集 Alpha 模拟/检查/提交运行器。

## 项目结构

```
alpha/                     # 项目根目录
├── src/                   # 源码目录
│   └── alpha/             # 主包
│       ├── __init__.py    # 包入口（导出基础公共 API）
│       ├── __main__.py    # python3 -m alpha / alpha 命令入口
│       ├── main.py        # 主流程编排
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
│       │   └── feedback.py
│       │
│       ├── api/           # API 客户端层
│       │   ├── api_types.py
│       │   └── client.py
│       │
│       ├── io/            # 输入输出层
│       │   ├── credentials.py
│       │   └── output.py
│       │
│       ├── cli/           # 命令行接口层
│       │   ├── filters.py
│       │   └── parser.py
│       │
│       ├── models/        # 数据模型层
│       │   └── base.py
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
├── data/                  # 模板库和人工维护的黑名单
└── .gitignore
```

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

不传参时使用内置默认值（`--limit 50 --max-templates-per-field 8`）。

**目标**：从数据集中找出有潜力的字段和模板家族。

**输出**：`*_analysis.json` 中的关键字段：
- `near_pass_summary`：接近通过的候选（按 score 排序）
- `failed_check_leaderboard`：主要失败原因分布
- `optimization_hints`：自动生成的优化建议

**预估时间**：25-50 分钟（50 字段 × 8 模板 ≈ 400 模拟）

#### 阶段 3：聚焦深挖（针对高反馈字段）

```bash
python3 -m alpha --top-fields-by-feedback 10 --max-templates-per-field 15
```

**目标**：对接近通过的候选进行精细搜索。

**机制**：
- 自动根据历史反馈调整模板优先级
- 优先探索 **delta/std 比率模板**（如 `delta_over_std`、`ratio_delta_over_std`），历史数据显示该家族 Sharpe 显著优于均值
- 为 high-score 字段生成更多 near-pass 变体
- 为 vol-scaled delta 家族生成更多 settings 变体

**反馈循环**：
- 默认读取同一输出文件（`results/fundamental6/test_results.json`）
- 阶段 2 的结果会自动用于字段优先级排序
- 可多次运行，每次自动续跑（不重复已完成的组合）

**预估时间**：30-60 分钟（10 字段 × 15 模板 ≈ 150 模拟，含变体）

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

强制刷新本地字段缓存：

```bash
python3 -m alpha --refresh-fields-cache
```

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
