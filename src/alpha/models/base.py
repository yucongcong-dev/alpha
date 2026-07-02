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
    AnalysisInputs,
    AnalysisPayload,
    FailedCheck,
    FieldFeedbackMap,
    FieldFeedbackSummary,
    FieldTestContext,
    FieldTestResult,
    FieldView,
    NearPassCandidate,
    ResultRow,
    SettingsVariant,
    SummaryPayload,
    TemplateCandidate,
    TemplateLibrary,
    TemplateMetadata,
)
from .io_types import RunFilters, RunPaths
from .runtime import (
    ApiClientArgs,
    ApiClientOptions,
    BootstrapRuntimeArgs,
    ClientFactoryLike,
    CleanRuntimeArgs,
    CredentialsArgs,
    ExecutionState,
    FieldFetchOptions,
    FieldSelectionArgs,
    FutureCompletionContext,
    HistoricalRunState,
    InitializedRunContext,
    PendingFutureContext,
    PendingFutureLike,
    RunConfigArgs,
    ResultWriteArgs,
    ResultWriteOptions,
    RunLoopArgs,
    RuntimeConcurrencyState,
    SchedulerRuntimeArgs,
    SemaphoreLike,
    SimulationStageArgs,
    SimulationSettingsArgs,
    StopAfterSubmittableArgs,
    TemplateFeedback,
    TemplateBuildArgs,
    TemplateBuildContext,
    TemplateBuildOptions,
    TemplateField,
    TemplateSequence,
)

__all__ = [
    "AnalysisInputs",
    "AnalysisPayload",
    "ApiClientArgs",
    "ApiClientOptions",
    "BootstrapRuntimeArgs",
    "ClientFactoryLike",
    "CleanRuntimeArgs",
    "CredentialsArgs",
    "DatasetExpressionPolicy",
    "ExecutionState",
    "FailedCheck",
    "FieldFeedbackMap",
    "FieldFeedbackSummary",
    "FieldFetchOptions",
    "FieldSelectionArgs",
    "FieldTestContext",
    "FieldTestResult",
    "FieldView",
    "FutureCompletionContext",
    "HistoricalRunState",
    "InitializedRunContext",
    "NearPassCandidate",
    "PendingFutureContext",
    "PendingFutureLike",
    "ResultRow",
    "RunConfigArgs",
    "ResultWriteArgs",
    "ResultWriteOptions",
    "RunLoopArgs",
    "RunFilters",
    "RunPaths",
    "RuntimeConcurrencyState",
    "SchedulerRuntimeArgs",
    "SemaphoreLike",
    "SettingsVariant",
    "SummaryPayload",
    "SimulationStageArgs",
    "SimulationSettingsArgs",
    "StopAfterSubmittableArgs",
    "TemplateBuildArgs",
    "TemplateBuildContext",
    "TemplateBuildOptions",
    "TemplateCandidate",
    "TemplateFeedback",
    "TemplateField",
    "TemplateLibrary",
    "TemplateMetadata",
    "TemplateSequence",
]
