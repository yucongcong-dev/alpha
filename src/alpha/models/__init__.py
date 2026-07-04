"""
数据模型包。

对外暴露稳定的类型导出层，按职责分为：
- domain.py: 纯领域对象（模板、字段、反馈等）
- io_types.py: 路径/过滤边界对象
- runtime.py: 运行时上下文与状态
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
from .result_predicates import (
    is_informative_result,
    is_queue_timeout_result,
)
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
    "is_informative_result",
    "is_queue_timeout_result",

]
