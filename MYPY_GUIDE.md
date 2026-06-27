# Mypy 类型检查使用指南

## 快速开始

### 基本检查

```bash
# 使用便捷脚本（推荐）
python scripts/run_mypy.py

# 或直接使用 mypy
python -m mypy src/alpha
```

### 检查特定文件

```bash
# 检查单个文件
python scripts/run_mypy.py src/alpha/core/simulation.py

# 检查多个文件
python scripts/run_mypy.py src/alpha/core/simulation.py src/alpha/api/client.py

# 检查整个目录
python scripts/run_mypy.py src/alpha/core
```

## 高级用法

### 严格模式

```bash
python scripts/run_mypy.py --strict
```

严格模式会启用更多检查项：
- `--disallow-untyped-calls`
- `--disallow-untyped-defs`
- `--disallow-incomplete-defs`
- `--check-untyped-defs`
- `--disallow-untyped-decorators`
- `--no-implicit-optional`
- 等等...

### 生成报告

```bash
# 生成 JUnit XML 报告（用于 CI/CD）
python scripts/run_mypy.py --junit-xml mypy-report.xml

# 生成 HTML 报告
python scripts/run_mypy.py --html-report mypy-html-report
```

### 详细输出

```bash
python scripts/run_mypy.py --verbose
```

## 配置说明

Mypy 配置位于 `pyproject.toml`：

```toml
[tool.mypy]
python_version = "3.10"
strict = false
warn_unused_ignores = true
warn_return_any = true
warn_unreachable = true
ignore_missing_imports = true
no_implicit_optional = true
check_untyped_defs = true
disallow_untyped_decorators = false
exclude = ["tests/"]

# 对核心模块启用更严格检查
[[tool.mypy.overrides]]
module = [
    "alpha.core.simulation",
    "alpha.core.scheduler",
    "alpha.generators.expressions",
    "alpha.models.base",
]
warn_return_any = true
check_untyped_defs = true
```

### 配置项说明

| 配置项 | 说明 | 当前值 |
|--------|------|--------|
| `python_version` | 目标 Python 版本 | 3.10 |
| `strict` | 严格模式（全局） | false |
| `warn_unused_ignores` | 警告未使用的 type: ignore | true |
| `warn_return_any` | 警告返回 Any 类型 | true |
| `warn_unreachable` | 警告不可达代码 | true |
| `ignore_missing_imports` | 忽略缺失的导入 | true |
| `no_implicit_optional` | 禁止隐式 Optional | true |
| `check_untyped_defs` | 检查无类型注解的函数 | true |
| `disallow_untyped_decorators` | 禁止无类型装饰器 | false |

## 常见问题

### 1. 忽略特定行的类型检查

```python
def some_function() -> str:
    result = some_untyped_call()  # type: ignore[no-any-return]
    return result
```

### 2. 忽略整个文件的类型检查

在文件顶部添加：

```python
# mypy: ignore-errors
```

### 3. 处理第三方库缺少类型注解

mypy 配置中已设置 `ignore_missing_imports = true`，会自动忽略第三方库的类型问题。

如果需要对特定库添加类型存根：

```bash
pip install types-requests  # 示例
```

### 4. Windows 编码问题

如果在 Windows 上遇到编码错误，确保使用 Python 3.6+ 并设置：

```bash
set PYTHONIOENCODING=utf-8
python scripts/run_mypy.py
```

## 集成到开发流程

### Git Pre-commit Hook

创建 `.git/hooks/pre-commit`：

```bash
#!/bin/bash
echo "运行 mypy 类型检查..."
python scripts/run_mypy.py
if [ $? -ne 0 ]; then
    echo "类型检查失败，提交中止"
    exit 1
fi
```

### GitHub Actions

```yaml
name: Type Check

on: [push, pull_request]

jobs:
  mypy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.10"
      - run: pip install -e ".[dev]"
      - run: python scripts/run_mypy.py
```

### VS Code 集成

1. 安装 Python 扩展
2. 在 `.vscode/settings.json` 中添加：

```json
{
  "python.linting.mypyEnabled": true,
  "python.linting.mypyArgs": [
    "--config-file",
    "pyproject.toml",
    "src/alpha"
  ]
}
```

## 最佳实践

1. **渐进式采用**：不要一次性启用 strict 模式，逐步增加检查项
2. **优先核心模块**：对核心业务逻辑启用更严格检查
3. **定期运行**：每次提交前运行 mypy 检查
4. **团队共识**：确保团队成员理解类型注解规范
5. **文档化**：为复杂类型添加注释说明

## 性能优化

对于大型项目，可以缓存 mypy 结果：

```bash
# 启用缓存
python -m mypy src/alpha --cache-dir .mypy_cache

# 清理缓存
rm -rf .mypy_cache
```

## 当前状态

✅ **所有类型检查通过**

```
Success: no issues found in 30 source files
```

- 检查文件数：30
- 错误数：0
- 警告数：0
- 测试通过率：207/207 (100%)

## 参考资料

- [Mypy 官方文档](https://mypy.readthedocs.io/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [PEP 526 - Syntax for Variable Annotations](https://peps.python.org/pep-0526/)
- [PEP 585 - Type Hinting Generics](https://peps.python.org/pep-0585/)
- [PEP 604 - Allow Writing Union Types](https://peps.python.org/pep-0604/)
