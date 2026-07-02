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
    ClientFactoryLike,
    ExecutionState,
    FieldFetchOptions,
    FutureCompletionContext,
    HistoricalRunState,
    InitializedRunContext,
    PendingFutureLike,
    RuntimeConcurrencyState,
    SemaphoreLike,
    SimulationSettingsArgs,
    TemplateFeedback,
    TemplateBuildContext,
    TemplateField,
    TemplateSequence,
)

__all__ = [
    "DatasetExpressionPolicy",
    "ClientFactoryLike",
    "ExecutionState",
    "FieldFetchOptions",
    "FieldView",
    "FieldTestContext",
    "FieldTestResult",
    "FutureCompletionContext",
    "HistoricalRunState",
    "InitializedRunContext",
    "NearPassCandidate",
    "PendingFutureLike",
    "RunFilters",
    "RunPaths",
    "RuntimeConcurrencyState",
    "SemaphoreLike",
    "SettingsVariant",
    "SimulationSettingsArgs",
    "TemplateFeedback",
    "TemplateBuildContext",
    "TemplateCandidate",
    "TemplateField",
    "TemplateLibrary",
    "TemplateSequence",
]
