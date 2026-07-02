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

from ..config.models import DatasetExpressionPolicy
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
    CleanRuntimeArgs,
    ClientFactoryLike,
    CredentialsArgs,
    ExecutionState,
    FieldFetchOptions,
    FieldSelectionArgs,
    FutureCompletionContext,
    HistoricalRunState,
    InitializedRunContext,
    PendingFutureContext,
    PendingFutureLike,
    ResultWriteArgs,
    ResultWriteOptions,
    RunConfigArgs,
    RunLoopArgs,
    RuntimeConcurrencyState,
    SchedulerRuntimeArgs,
    SemaphoreLike,
    SimulationSettingsArgs,
    SimulationStageArgs,
    StopAfterSubmittableArgs,
    TemplateBuildArgs,
    TemplateBuildContext,
    TemplateBuildOptions,
    TemplateFeedback,
    TemplateField,
    TemplateSequence,
)

__all__ = [
    "AnalysisInputs",
    "AnalysisPayload",
    "ApiClientArgs",
    "ApiClientOptions",
    "BootstrapRuntimeArgs",
    "CleanRuntimeArgs",
    "ClientFactoryLike",
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
    "ResultWriteArgs",
    "ResultWriteOptions",
    "RunConfigArgs",
    "RunFilters",
    "RunLoopArgs",
    "RunPaths",
    "RuntimeConcurrencyState",
    "SchedulerRuntimeArgs",
    "SemaphoreLike",
    "SettingsVariant",
    "SimulationSettingsArgs",
    "SimulationStageArgs",
    "StopAfterSubmittableArgs",
    "SummaryPayload",
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
