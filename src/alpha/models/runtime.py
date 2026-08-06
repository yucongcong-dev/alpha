"""Compatibility export layer for runtime model access.

The runtime surface is split across config/options/protocol/state modules. This
module preserves the historical ``alpha.models.runtime`` import path while
loading concrete definitions lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from .domain import TemplateField
    from .runtime_config import (
        SimulationSettingsConfig,
        SimulationStageConfig,
    )
    from .runtime_options import (
        ApiClientOptions,
        FieldFetchOptions,
        FieldSelectionOptions,
        ResultWriteOptions,
        RunLoopOptions,
        TemplateBuildOptions,
    )
    from .runtime_protocols import (
        BlacklistRuntimeStats,
        ClientFactoryLike,
        RunConfig,
        SemaphoreLike,
        TemplateFeedback,
        TemplateSequence,
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
    from ..runtime.state import (
        ExecutionState,
        InitializedRunContext,
        PendingFutureLike,
    )

_EXPORT_MAP: ExportMap = {
    "TemplateField": (".domain", "TemplateField"),
    "SimulationSettingsConfig": (".runtime_config", "SimulationSettingsConfig"),
    "SimulationStageConfig": (".runtime_config", "SimulationStageConfig"),
    "ApiClientOptions": (".runtime_options", "ApiClientOptions"),
    "FieldFetchOptions": (".runtime_options", "FieldFetchOptions"),
    "FieldSelectionOptions": (".runtime_options", "FieldSelectionOptions"),
    "ResultWriteOptions": (".runtime_options", "ResultWriteOptions"),
    "RunLoopOptions": (".runtime_options", "RunLoopOptions"),
    "TemplateBuildOptions": (".runtime_options", "TemplateBuildOptions"),
    "BlacklistRuntimeStats": (".runtime_protocols", "BlacklistRuntimeStats"),
    "ClientFactoryLike": (".runtime_protocols", "ClientFactoryLike"),
    "RunConfig": (".runtime_protocols", "RunConfig"),
    "SemaphoreLike": (".runtime_protocols", "SemaphoreLike"),
    "TemplateFeedback": (".runtime_protocols", "TemplateFeedback"),
    "TemplateSequence": (".runtime_protocols", "TemplateSequence"),
    "TemplateStats": (".runtime_protocols", "TemplateStats"),
    "ExecutionMetrics": ("..runtime.result_ledger", "ExecutionMetrics"),
    "ExecutionState": ("..runtime.state", "ExecutionState"),
    "FutureQueueState": ("..runtime.future_queue", "FutureQueueState"),
    "FutureCompletionContext": ("..runtime.contexts", "FutureCompletionContext"),
    "HistoricalRunState": ("..runtime.contexts", "HistoricalRunState"),
    "InitializedRunContext": ("..runtime.state", "InitializedRunContext"),
    "PendingFutureContext": ("..runtime.contexts", "PendingFutureContext"),
    "PendingFutureLike": ("..runtime.state", "PendingFutureLike"),
    "PendingTemplateEntry": ("..runtime.contexts", "PendingTemplateEntry"),
    "QueueRetryKey": ("..runtime.queue_retry", "QueueRetryKey"),
    "QueueRetryState": ("..runtime.queue_retry", "QueueRetryState"),
    "QueueRetryUpdate": ("..runtime.queue_retry", "QueueRetryUpdate"),
    "ResultLedgerState": ("..runtime.result_ledger", "ResultLedgerState"),
    "RuntimeConcurrencyState": ("..runtime.concurrency", "RuntimeConcurrencyState"),
    "TemplateBuildContext": ("..runtime.contexts", "TemplateBuildContext"),
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
