# WorldQuant Brain Alpha Runner

面向 WorldQuant BRAIN 的数据集 Alpha 模拟、submission check 与本地研究运行器。默认只执行
`simulation + check-submit`，**不会自动正式提交 Alpha**。

## 快速开始

要求：Python 3.10+（项目根目录的 `.python-version` 为 `3.10`）。

```bash
# 创建并激活虚拟环境后，安装完整开发依赖
make install-dev

# 先确认本地候选计划；不会登录、联网或创建 simulation
python -m alpha --dry-run-plan

# 首次真实运行：登录、拉取字段缓存，并执行模拟与 check
python -m alpha --dataset-id fundamental6
```

也可以安装后使用 `alpha` 命令。误用低于 Python 3.10 的解释器时，入口会直接退出并提示版本问题。

## 文档导航

| 想解决的问题 | 位置 |
|---|---|
| 平台基础、指标、设置与表达式入门 | [01 入门](docs/01_beginner_guide.md) |
| 字段研究、仓库运行、缓存、反馈与资产管理 | [02 数据研究与仓库实践](docs/02_research_and_data_guide.md) |
| 根据回测和 submission check 优化 Alpha | [03 优化与提交](docs/03_optimization_and_submission.md) |
| 查 IS/OS、Coverage、状态或平台术语 | [04 平台 Reference](docs/04_platform_reference.md) |
| 按问题查找全部文档 | [Docs Index](docs/README.md) |
| 某一数据集当前策略与下一步 | `datasets/<dataset_id>/README.md` |

## 项目结构

```text
alpha/
├── src/alpha/       # CLI、运行编排、模板生成、策略、API 与结果处理
├── config/          # 唯一可编辑的 YAML 配置源
├── datasets/        # 各数据集的模板、预设、黑名单、缓存与本地运行状态
├── docs/            # 四篇主文档与索引
└── tests/           # unit / integration
```

每个数据集的长期资产放在 `datasets/<dataset_id>/`：

- `template.json`：默认模板库
- `presets/`：专项模板、字段与模板筛选清单
- `blacklist.json`：自动或人工维护的排除规则
- `README.md`：该数据集的有效结论、当前策略与下一步

`cache/`、`runs/`、`feedback/` 与 `.credentials/` 属于本地可重建或私密状态，不提交。详细目录、工作区、结果和清理规则见 [02](docs/02_research_and_data_guide.md)。

## 常用命令

```bash
# 环境验证（需要登录）
python -m alpha --smoke-test

# 只读预览下一次计划
python -m alpha --dry-run-plan

# 聚焦历史高反馈字段
python -m alpha --top-fields-by-feedback 10 --max-templates-per-field 15

# 预览 / 执行本地运行产物清理
python -m alpha clean --dry-run-clean
python -m alpha clean
```

完整的运行阶段、续跑、配置覆盖、缓存和结果文件说明统一在 [02](docs/02_research_and_data_guide.md)。

## 开发检查

```bash
make install-dev
python -m pytest -q
make check
```

`make install-dev` 会根据 `pyproject.toml` 安装运行依赖、开发检查依赖和 HTTPX 后端。
`make check` 会执行测试、配置同步、文档和密钥扫描检查；修改根 `config/*.yaml` 后使用 `make sync-config` 更新包内镜像。

## 安全边界

- `.credentials/` 保存本地加密凭证与密钥，不应提交或共享。
- `--dry-run-plan` 是离线只读操作；正常运行才会登录和创建 simulation。
- `submittable=true` 表示通过本轮检查、值得人工评估，**不表示已正式提交**。
