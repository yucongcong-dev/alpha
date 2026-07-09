"""Compatibility export layer for model types.

The concrete model definitions live in focused submodules. This package-level
facade keeps the public ``alpha.models`` surface stable while deferring imports
until a specific symbol is requested.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
        TemplateField,
        TemplateLibrary,
        TemplateMetadata,
    )
    from .io_types import RunFilters, RunPaths
    from .result_predicates import is_informative_result, is_queue_timeout_result
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

_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "DatasetExpressionPolicy": ("..config.models", "DatasetExpressionPolicy"),
    "AnalysisInputs": (".domain", "AnalysisInputs"),
    "AnalysisPayload": (".domain", "AnalysisPayload"),
    "FailedCheck": (".domain", "FailedCheck"),
    "FieldFeedbackMap": (".domain", "FieldFeedbackMap"),
    "FieldFeedbackSummary": (".domain", "FieldFeedbackSummary"),
    "FieldTestContext": (".domain", "FieldTestContext"),
    "FieldTestResult": (".domain", "FieldTestResult"),
    "FieldView": (".domain", "FieldView"),
    "NearPassCandidate": (".domain", "NearPassCandidate"),
    "ResultRow": (".domain", "ResultRow"),
    "SettingsVariant": (".domain", "SettingsVariant"),
    "SummaryPayload": (".domain", "SummaryPayload"),
    "TemplateCandidate": (".domain", "TemplateCandidate"),
    "TemplateField": (".domain", "TemplateField"),
    "TemplateLibrary": (".domain", "TemplateLibrary"),
    "TemplateMetadata": (".domain", "TemplateMetadata"),
    "RunFilters": (".io_types", "RunFilters"),
    "RunPaths": (".io_types", "RunPaths"),
    "is_informative_result": (".result_predicates", "is_informative_result"),
    "is_queue_timeout_result": (".result_predicates", "is_queue_timeout_result"),
    "ApiClientArgs": (".runtime", "ApiClientArgs"),
    "ApiClientOptions": (".runtime", "ApiClientOptions"),
    "BootstrapRuntimeArgs": (".runtime", "BootstrapRuntimeArgs"),
    "CleanRuntimeArgs": (".runtime", "CleanRuntimeArgs"),
    "ClientFactoryLike": (".runtime", "ClientFactoryLike"),
    "CredentialsArgs": (".runtime", "CredentialsArgs"),
    "ExecutionState": (".runtime", "ExecutionState"),
    "FieldFetchOptions": (".runtime", "FieldFetchOptions"),
    "FieldSelectionArgs": (".runtime", "FieldSelectionArgs"),
    "FutureCompletionContext": (".runtime", "FutureCompletionContext"),
    "HistoricalRunState": (".runtime", "HistoricalRunState"),
    "InitializedRunContext": (".runtime", "InitializedRunContext"),
    "PendingFutureContext": (".runtime", "PendingFutureContext"),
    "PendingFutureLike": (".runtime", "PendingFutureLike"),
    "ResultWriteArgs": (".runtime", "ResultWriteArgs"),
    "ResultWriteOptions": (".runtime", "ResultWriteOptions"),
    "RunConfigArgs": (".runtime", "RunConfigArgs"),
    "RunLoopArgs": (".runtime", "RunLoopArgs"),
    "RuntimeConcurrencyState": (".runtime", "RuntimeConcurrencyState"),
    "SchedulerRuntimeArgs": (".runtime", "SchedulerRuntimeArgs"),
    "SemaphoreLike": (".runtime", "SemaphoreLike"),
    "SimulationSettingsArgs": (".runtime", "SimulationSettingsArgs"),
    "SimulationStageArgs": (".runtime", "SimulationStageArgs"),
    "StopAfterSubmittableArgs": (".runtime", "StopAfterSubmittableArgs"),
    "TemplateBuildArgs": (".runtime", "TemplateBuildArgs"),
    "TemplateBuildContext": (".runtime", "TemplateBuildContext"),
    "TemplateBuildOptions": (".runtime", "TemplateBuildOptions"),
    "TemplateFeedback": (".runtime", "TemplateFeedback"),
    "TemplateSequence": (".runtime", "TemplateSequence"),
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
