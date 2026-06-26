# -*- coding: utf-8 -*-
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
    python -m alpha --smoke-test
    python -m alpha --dry-run-plan
    python -m alpha --limit 50 --submit
"""

from .config import (
    API_BASE,
    AUTH_URL,
    DATA_FIELDS_URL,
    SIMULATIONS_URL,
    ALPHAS_URL,
    DEFAULT_DATASET_ID,
    DEFAULT_HEADERS,
    VERSION_HEADER,
    SIM_ACCEPT_HEADER,
    use_fundamental6_heuristics,
)
from .exceptions import (
    BrainAPIError,
    BrainRateLimitError,
    BrainQueueBusyError,
)
from .models import (
    FieldTestResult,
    TemplateLibrary,
    SettingsVariant,
    RunPaths,
    RuntimeConcurrencyState,
    RunFilters,
    HistoricalRunState,
    ExecutionState,
)
from .utils import first_non_empty, choose_field_name, choose_field_type

__version__ = "1.0.0"
__author__ = "Alpha Generator Team"

__all__ = [
    "__version__",
    "__author__",
    "API_BASE",
    "AUTH_URL",
    "DATA_FIELDS_URL",
    "SIMULATIONS_URL",
    "ALPHAS_URL",
    "DEFAULT_DATASET_ID",
    "DEFAULT_HEADERS",
    "VERSION_HEADER",
    "SIM_ACCEPT_HEADER",
    "use_fundamental6_heuristics",
    "BrainAPIError",
    "BrainRateLimitError",
    "BrainQueueBusyError",
    "FieldTestResult",
    "TemplateLibrary",
    "SettingsVariant",
    "RunPaths",
    "RuntimeConcurrencyState",
    "RunFilters",
    "HistoricalRunState",
    "ExecutionState",
    "first_non_empty",
    "choose_field_name",
    "choose_field_type",
]
