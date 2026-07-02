"""
数据模型包

定义系统使用的各种数据类和类型别名。
"""

from __future__ import annotations

from ..config import DatasetExpressionPolicy
from .domain import (
    FieldTestContext,
    FieldTestResult,
    FieldView,
    NearPassCandidate,
    SettingsVariant,
    TemplateCandidate,
    TemplateLibrary,
)
from .io_types import (
    RunFilters,
    RunPaths,
)
from .runtime import (
    ExecutionState,
    FutureCompletionContext,
    HistoricalRunState,
    InitializedRunContext,
    RuntimeConcurrencyState,
    TemplateBuildContext,
)

__all__ = [
    "DatasetExpressionPolicy",
    "ExecutionState",
    "FieldView",
    "FieldTestContext",
    "FieldTestResult",
    "FutureCompletionContext",
    "HistoricalRunState",
    "InitializedRunContext",
    "NearPassCandidate",
    "RunFilters",
    "RunPaths",
    "RuntimeConcurrencyState",
    "SettingsVariant",
    "TemplateBuildContext",
    "TemplateCandidate",
    "TemplateLibrary",
]
