# WorldQuant Brain Alpha Runner

通用的 WorldQuant Brain 数据集 Alpha 模拟/检查/提交运行器。

## 项目结构

```
alpha/                     # 项目根目录
├── src/                   # 源码目录
│   └── alpha/             # 主包
│       ├── __init__.py    # 包入口（导出基础公共 API）
│       ├── __main__.py    # python -m alpha 入口
│       ├── main.py        # 主流程编排
│       │
│       ├── core/          # 核心业务层
│       │   └── executor.py
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
│       │   └── client.py
│       │
│       ├── io/            # 输入输出层
│       │   ├── credentials.py
│       │   └── output.py
│       │
│       ├── cli/           # 命令行接口层
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
└── .gitignore
```

## 安装

```bash
# 开发模式安装（推荐）
pip install -e .

# 或直接使用 PYTHONPATH 运行
export PYTHONPATH=src
python -m alpha --smoke-test
```

## 运行

冒烟测试，仅用于检查登录/API 流程：

```bash
python -m alpha --smoke-test
```

默认探索运行，适合寻找候选 Alpha：

```bash
python -m alpha
```

预览下一次运行而不创建模拟任务：

```bash
python -m alpha --dry-run-plan
```

更广泛的探索：

```bash
python -m alpha --limit 50 --max-templates-per-field 8
```

强制刷新本地字段缓存：

```bash
python -m alpha --refresh-fields-cache
```

完整运行：

```bash
python -m alpha --full-run
```

## 测试

运行单元测试：

```bash
python -m unittest discover tests -v

# 或使用 pytest（需要安装）
pip install pytest
pytest tests/ -v
```

## 打包发布

```bash
pip install build
python -m build
```

生成的包在 `dist/` 目录下。