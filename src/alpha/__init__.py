"""
WorldQuant BRAIN Alpha 自动生成与提交工具包。

本工具包用于：
- 自动生成 Alpha 表达式
- 批量回测并筛选可提交的 Alpha
- 提交符合平台检查标准的 Alpha
- 分析失败原因并迭代优化策略

包结构：
    utils/          公共工具函数
    models/         数据类定义
    api/            Brain API 客户端
    generators/     Alpha 生成器（模板、表达式、字段、参数）
    analysis/       分析与优化（统计、反馈迭代）
    core/           核心执行业务
    io/             输入输出（凭证、结果持久化）
    cli/            命令行接口
    config.py       配置常量
    exceptions.py   自定义异常类
    main.py         主入口函数

使用方式：
    python3 -m alpha --smoke-test
    python3 -m alpha --dry-run-plan
    python3 -m alpha --limit 50 --submit
"""

from __future__ import annotations

from .config import (
    ALPHAS_URL,
    API_BASE,
    AUTH_URL,
    DATA_FIELDS_URL,
    DEFAULT_DATASET_ID,
    DEFAULT_HEADERS,
    SIM_ACCEPT_HEADER,
    SIMULATIONS_URL,
    VERSION_HEADER,
)

# 新增模块导出
from .error_handling import (
    ErrorCategory,
    ErrorContext,
    ErrorHandler,
    ErrorRecord,
    ErrorSeverity,
    error_handler,
    get_error_handler,
    handle_global_error,
    retry_on_error,
    set_error_handler,
)
from .exceptions import (
    BrainAPIError,
    BrainQueueBusyError,
    BrainRateLimitError,
)
from .generators.fields import choose_field_name, choose_field_type
from .models import (
    DatasetExpressionPolicy,
    ExecutionState,
    FieldTestResult,
    FieldView,
    HistoricalRunState,
    RunFilters,
    RunPaths,
    RuntimeConcurrencyState,
    SettingsVariant,
    TemplateLibrary,
)
from .utils import first_non_empty

__version__ = "1.0.0"
__author__ = "Alpha Generator Team"

__all__ = [
    "ALPHAS_URL",
    "API_BASE",
    "AUTH_URL",
    "DATA_FIELDS_URL",
    "DEFAULT_DATASET_ID",
    "DEFAULT_HEADERS",
    "SIMULATIONS_URL",
    "SIM_ACCEPT_HEADER",
    "VERSION_HEADER",
    "BrainAPIError",
    "BrainQueueBusyError",
    "BrainRateLimitError",
    "DatasetExpressionPolicy",
    "ErrorCategory",
    "ErrorContext",
    # 错误处理模块
    "ErrorHandler",
    "ErrorRecord",
    "ErrorSeverity",
    "ExecutionState",
    "FieldTestResult",
    "FieldView",
    "HistoricalRunState",
    "RunFilters",
    "RunPaths",
    "RuntimeConcurrencyState",
    "SettingsVariant",
    "TemplateLibrary",
    "__author__",
    "__version__",
    "choose_field_name",
    "choose_field_type",
    "error_handler",
    "first_non_empty",
    "get_error_handler",
    "handle_global_error",
    "retry_on_error",
    "set_error_handler",
]
