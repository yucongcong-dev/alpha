"""Compatibility export layer for model types.

The concrete model definitions live in focused submodules. This package-level
facade keeps the public ``alpha.models`` surface stable while deferring imports
until a specific symbol is requested.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from ..config.models import DatasetExpressionPolicy
    from .domain import (
        FailedCheck,
        FieldTestContext,
        FieldTestResult,
        FieldView,
        NearPassCandidate,
        SettingsVariant,
        TemplateCandidate,
        TemplateField,
        TemplateLibrary,
    )
    from .domain_parsers import (
        parse_failed_check,
        parse_settings_variant,
        parse_template_field,
        parse_template_library_item,
    )
    from .domain_serializers import serialize_field_test_result
    from .domain_serializers import (
        serialize_settings_variant,
        serialize_template_field,
        serialize_template_library_item,
    )
    from .domain_types import (
        AnalysisInputs,
        AnalysisPayload,
        FieldFeedbackMap,
        FieldFeedbackSummary,
        ResultRow,
        SummaryPayload,
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

_EXPORT_MAP: ExportMap = {
    "DatasetExpressionPolicy": ("..config.models", "DatasetExpressionPolicy"),
    "AnalysisInputs": (".domain_types", "AnalysisInputs"),
    "AnalysisPayload": (".domain_types", "AnalysisPayload"),
    "FailedCheck": (".domain", "FailedCheck"),
    "FieldFeedbackMap": (".domain_types", "FieldFeedbackMap"),
    "FieldFeedbackSummary": (".domain_types", "FieldFeedbackSummary"),
    "FieldTestContext": (".domain", "FieldTestContext"),
    "FieldTestResult": (".domain", "FieldTestResult"),
    "FieldView": (".domain", "FieldView"),
    "NearPassCandidate": (".domain", "NearPassCandidate"),
    "parse_failed_check": (".domain_parsers", "parse_failed_check"),
    "parse_settings_variant": (".domain_parsers", "parse_settings_variant"),
    "parse_template_field": (".domain_parsers", "parse_template_field"),
    "parse_template_library_item": (".domain_parsers", "parse_template_library_item"),
    "serialize_field_test_result": (".domain_serializers", "serialize_field_test_result"),
    "serialize_settings_variant": (".domain_serializers", "serialize_settings_variant"),
    "serialize_template_field": (".domain_serializers", "serialize_template_field"),
    "serialize_template_library_item": (".domain_serializers", "serialize_template_library_item"),
    "ResultRow": (".domain_types", "ResultRow"),
    "SettingsVariant": (".domain", "SettingsVariant"),
    "SummaryPayload": (".domain_types", "SummaryPayload"),
    "TemplateCandidate": (".domain", "TemplateCandidate"),
    "TemplateField": (".domain", "TemplateField"),
    "TemplateLibrary": (".domain", "TemplateLibrary"),
    "TemplateMetadata": (".domain_types", "TemplateMetadata"),
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

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str) -> object:
    return resolve_export(
        name=name,
        export_map=_EXPORT_MAP,
        package=__package__ or "",
        namespace=__name__,
        target_globals=globals(),
    )


def __dir__() -> list[str]:
    return facade_dir(globals(), _EXPORT_MAP)
