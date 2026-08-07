# WorldQuant Brain Alpha Runner

面向 WorldQuant BRAIN 的数据集 Alpha 模拟、submission check 与本地研究运行器。默认只执行
`simulation + Check Submission`，**不会自动正式提交 Alpha**。

## 快速开始

要求：Python 3.10+（项目根目录的 `.python-version` 为 `3.10`）。

```bash
# 创建并激活虚拟环境后，安装完整开发依赖
make install-dev

# 先确认本地候选计划；不会登录、联网或创建 simulation
python -m alpha --dataset-id fundamental2 --dry-run-plan

# 首次真实运行：显式选择数据集，执行 1 字段 / 1 模板冒烟测试
python -m alpha --dataset-id fundamental2 --template-library-file datasets/fundamental2/template.json --smoke-test

# fundamental6 已暂停普通运行；全量探索必须显式给出 simulation 硬预算
python -m alpha --dataset-id fundamental6 --full-run --max-total-simulations 100
```

也可以安装后使用 `alpha` 命令。误用低于 Python 3.10 的解释器时，入口会直接退出并提示版本问题。Makefile 会优先选择 Python 3.10：macOS/Linux 优先 `python3.10`，Windows 优先 `py -3.10`。需要手动覆盖时可以传入 `PYTHON`，例如 `make check PYTHON=python3.10` 或 `make check PYTHON="py -3.10"`。

## 文档导航

| 想解决的问题 | 位置 |
|---|---|
| 平台基础、指标、设置与表达式入门 | [01 入门](docs/01_beginner_guide.md) |
| 字段研究、模板设计与研究流程 | [02 数据研究与仓库实践](docs/02_research_and_data_guide.md) |
| CLI、字段调度、缓存、续跑、结果与配置 | [Runner Reference](docs/runner_reference.md) |
| 根据回测和 submission check 优化 Alpha | [03 优化与提交](docs/03_optimization_and_submission.md) |
| 查 IS/OS、Coverage、状态或平台术语 | [04 平台 Reference](docs/04_platform_reference.md) |
| 顾问申请、Workday、银行、Referral 或账号问题 | [05 平台运营 Reference](docs/05_platform_operations_reference.md) |
| 按问题查找全部文档 | [Docs Index](docs/README.md) |
| 某一数据集当前策略与下一步 | `datasets/<dataset_id>/README.md` |

## 项目结构

```text
alpha/
├── src/alpha/       # CLI、运行编排、模板生成、策略、API 与结果处理
├── config/          # 唯一可编辑的 YAML 配置源
├── datasets/        # 各数据集的模板、预设、黑名单、缓存与本地运行状态
├── docs/            # 研究主文档、平台与 runner reference、索引
└── tests/           # unit / integration
```

每个数据集的长期资产放在 `datasets/<dataset_id>/`：

- `template.json`：默认模板库
- `presets/`：专项模板、字段与模板筛选清单
- `blacklist.json`：人工维护的长期排除规则；运行过程只读取，不自动改写
- `README.md`：该数据集的有效结论、当前策略与下一步

`cache/`、`runs/`、`feedback/` 与 `.credentials/` 属于本地可重建或私密状态，不提交。详细目录、工作区、结果和清理规则见 [Runner Reference](docs/runner_reference.md)。

## 更多常用命令

```bash
# 聚焦历史高反馈字段
python -m alpha --dataset-id fundamental2 --template-library-file datasets/fundamental2/template.json --top-fields-by-feedback 10 --max-templates-per-field 15

# 预览 / 执行本地运行产物清理
python -m alpha clean --dataset-id fundamental2 --dry-run-clean
python -m alpha clean --dataset-id fundamental2
```

完整的运行阶段、续跑、配置覆盖、缓存和结果文件说明统一在
[Runner Reference](docs/runner_reference.md)。

## 开发检查

```bash
make install-dev
make test
make check
```

`make install-dev` 会根据 `pyproject.toml` 安装运行依赖和开发检查依赖。
`make check` 会执行测试、配置同步、文档和密钥扫描检查；修改根 `config/*.yaml` 后使用 `make sync-config` 更新包内镜像。
Makefile 只是快捷入口，完整检查由跨平台 Python 脚本编排，不依赖 Git Bash：

```bash
# macOS / Linux
python3.10 scripts/check_all.py

# Windows
py -3.10 scripts/check_all.py
```

也可以直接运行 `python scripts/clean_dev.py` 清理开发缓存。

## 安全边界

- `.credentials/` 保存本地加密凭证与密钥，不应提交或共享。
- `--dry-run-plan` 是离线只读操作；正常运行才会登录和创建 simulation。
- `submittable=true` 只表示通过本轮检查、值得继续优化和人工评估；运行器不提供正式提交功能。
