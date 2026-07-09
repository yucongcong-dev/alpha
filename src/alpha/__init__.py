"""
WorldQuant BRAIN Alpha 自动生成与测试工具包。

本工具包用于：
- 自动生成 Alpha 表达式
- 批量回测并筛选可提交的 Alpha
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
    python3.10 -m alpha --smoke-test
    python3.10 -m alpha --dry-run-plan
    python3.10 -m alpha --limit 50
"""

from __future__ import annotations

from importlib import import_module
import sys
from typing import TYPE_CHECKING

if sys.version_info < (3, 10):
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    raise RuntimeError(
        "alpha requires Python 3.10+ because the runtime models use dataclass(kw_only=True). "
        f"Current interpreter: {version}. Please switch to python3.10 or newer."
    )

if TYPE_CHECKING:
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
    from .exceptions import BrainAPIError, BrainQueueBusyError, BrainRateLimitError
    from .generators import choose_field_name, choose_field_type
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

_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "ALPHAS_URL": (".config", "ALPHAS_URL"),
    "API_BASE": (".config", "API_BASE"),
    "AUTH_URL": (".config", "AUTH_URL"),
    "DATA_FIELDS_URL": (".config", "DATA_FIELDS_URL"),
    "DEFAULT_DATASET_ID": (".config", "DEFAULT_DATASET_ID"),
    "DEFAULT_HEADERS": (".config", "DEFAULT_HEADERS"),
    "SIM_ACCEPT_HEADER": (".config", "SIM_ACCEPT_HEADER"),
    "SIMULATIONS_URL": (".config", "SIMULATIONS_URL"),
    "VERSION_HEADER": (".config", "VERSION_HEADER"),
    "ErrorCategory": (".error_handling", "ErrorCategory"),
    "ErrorContext": (".error_handling", "ErrorContext"),
    "ErrorHandler": (".error_handling", "ErrorHandler"),
    "ErrorRecord": (".error_handling", "ErrorRecord"),
    "ErrorSeverity": (".error_handling", "ErrorSeverity"),
    "error_handler": (".error_handling", "error_handler"),
    "get_error_handler": (".error_handling", "get_error_handler"),
    "handle_global_error": (".error_handling", "handle_global_error"),
    "retry_on_error": (".error_handling", "retry_on_error"),
    "set_error_handler": (".error_handling", "set_error_handler"),
    "BrainAPIError": (".exceptions", "BrainAPIError"),
    "BrainQueueBusyError": (".exceptions", "BrainQueueBusyError"),
    "BrainRateLimitError": (".exceptions", "BrainRateLimitError"),
    "choose_field_name": (".generators", "choose_field_name"),
    "choose_field_type": (".generators", "choose_field_type"),
    "DatasetExpressionPolicy": (".models", "DatasetExpressionPolicy"),
    "ExecutionState": (".models", "ExecutionState"),
    "FieldTestResult": (".models", "FieldTestResult"),
    "FieldView": (".models", "FieldView"),
    "HistoricalRunState": (".models", "HistoricalRunState"),
    "RunFilters": (".models", "RunFilters"),
    "RunPaths": (".models", "RunPaths"),
    "RuntimeConcurrencyState": (".models", "RuntimeConcurrencyState"),
    "SettingsVariant": (".models", "SettingsVariant"),
    "TemplateLibrary": (".models", "TemplateLibrary"),
    "first_non_empty": (".utils", "first_non_empty"),
}


def __getattr__(name: str) -> object:
    try:
        module_name, attr_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name, __package__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
