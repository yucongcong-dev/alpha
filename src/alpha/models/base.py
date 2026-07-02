"""
兼容数据模型导出层。

历史上项目大量从 `alpha.models.base` 导入类型。
当前真实定义已经拆分到：
- domain.py: 纯领域对象
- io_types.py: 路径/过滤边界对象
- runtime.py: 运行时上下文与状态

本模块保留统一导出，避免一次性改动全仓引用点。
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
from .io_types import RunFilters, RunPaths
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
    "FieldTestContext",
    "FieldTestResult",
    "FieldView",
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
