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
    from .runtime_config import SimulationSettingsConfig, SimulationStageConfig
    from .runtime_options import (
        ApiClientOptions,
        FieldFetchOptions,
        FieldSelectionOptions,
        ResultWriteOptions,
        RunLoopOptions,
        TemplateBuildOptions,
    )
    from .runtime_protocols import (
        ClientFactoryLike,
        RunConfig,
        SemaphoreLike,
        TemplateFeedback,
        TemplateStats,
    )
    from ..runtime.concurrency import RuntimeConcurrencyState
    from ..runtime.contexts import (
        FutureCompletionContext,
        HistoricalRunState,
        PendingFutureContext,
        PendingTemplateEntry,
        TemplateBuildContext,
    )
    from ..runtime.future_queue import FutureQueueState
    from ..runtime.queue_retry import QueueRetryKey, QueueRetryState, QueueRetryUpdate
    from ..runtime.result_ledger import ExecutionMetrics, ResultLedgerState
    from ..runtime.state import ExecutionState, InitializedRunContext

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
    "SimulationSettingsConfig": (".runtime_config", "SimulationSettingsConfig"),
    "SimulationStageConfig": (".runtime_config", "SimulationStageConfig"),
    "ApiClientOptions": (".runtime_options", "ApiClientOptions"),
    "ClientFactoryLike": (".runtime_protocols", "ClientFactoryLike"),
    "ExecutionState": ("..runtime.state", "ExecutionState"),
    "FieldFetchOptions": (".runtime_options", "FieldFetchOptions"),
    "FieldSelectionOptions": (".runtime_options", "FieldSelectionOptions"),
    "FutureCompletionContext": ("..runtime.contexts", "FutureCompletionContext"),
    "HistoricalRunState": ("..runtime.contexts", "HistoricalRunState"),
    "InitializedRunContext": ("..runtime.state", "InitializedRunContext"),
    "PendingFutureContext": ("..runtime.contexts", "PendingFutureContext"),
    "ResultWriteOptions": (".runtime_options", "ResultWriteOptions"),
    "RunLoopOptions": (".runtime_options", "RunLoopOptions"),
    "RunConfig": (".runtime_protocols", "RunConfig"),
    "RuntimeConcurrencyState": ("..runtime.concurrency", "RuntimeConcurrencyState"),
    "SemaphoreLike": (".runtime_protocols", "SemaphoreLike"),
    "TemplateBuildContext": ("..runtime.contexts", "TemplateBuildContext"),
    "TemplateBuildOptions": (".runtime_options", "TemplateBuildOptions"),
    "TemplateFeedback": (".runtime_protocols", "TemplateFeedback"),
    "TemplateStats": (".runtime_protocols", "TemplateStats"),
    "ExecutionMetrics": ("..runtime.result_ledger", "ExecutionMetrics"),
    "FutureQueueState": ("..runtime.future_queue", "FutureQueueState"),
    "PendingTemplateEntry": ("..runtime.contexts", "PendingTemplateEntry"),
    "QueueRetryKey": ("..runtime.queue_retry", "QueueRetryKey"),
    "QueueRetryState": ("..runtime.queue_retry", "QueueRetryState"),
    "QueueRetryUpdate": ("..runtime.queue_retry", "QueueRetryUpdate"),
    "ResultLedgerState": ("..runtime.result_ledger", "ResultLedgerState"),
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
