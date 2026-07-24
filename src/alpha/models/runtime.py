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
        FieldSelectionConfig,
        SimulationSettingsConfig,
        SimulationStageConfig,
    )
    from .runtime_options import (
        ApiClientOptions,
        FieldFetchOptions,
        ResultWriteOptions,
        TemplateBuildOptions,
    )
    from .runtime_protocols import (
        ApiClientArgs,
        BlacklistRuntimeStats,
        BootstrapRuntimeArgs,
        CleanRuntimeArgs,
        ClientFactoryLike,
        CredentialsArgs,
        FieldFetchArgs,
        FieldSelectionArgs,
        ResultWriteArgs,
        RuntimeConcurrencyArgs,
        RunConfig,
        RunConfigArgs,
        RunLoopArgs,
        SchedulerRuntimeArgs,
        SemaphoreLike,
        SimulationSettingsArgs,
        SimulationStageArgs,
        StopAfterSubmittableArgs,
        TemplateBuildArgs,
        TemplateFeedback,
        TemplateSequence,
        TemplateStats,
    )
    from .runtime_state import (
        ExecutionState,
        FutureCompletionContext,
        HistoricalRunState,
        InitializedRunContext,
        PendingFutureContext,
        PendingFutureLike,
        PendingTemplateEntry,
        RuntimeConcurrencyState,
        TemplateBuildContext,
    )

_EXPORT_MAP: ExportMap = {
    "TemplateField": (".domain", "TemplateField"),
    "FieldSelectionConfig": (".runtime_config", "FieldSelectionConfig"),
    "SimulationSettingsConfig": (".runtime_config", "SimulationSettingsConfig"),
    "SimulationStageConfig": (".runtime_config", "SimulationStageConfig"),
    "ApiClientOptions": (".runtime_options", "ApiClientOptions"),
    "FieldFetchOptions": (".runtime_options", "FieldFetchOptions"),
    "ResultWriteOptions": (".runtime_options", "ResultWriteOptions"),
    "TemplateBuildOptions": (".runtime_options", "TemplateBuildOptions"),
    "ApiClientArgs": (".runtime_protocols", "ApiClientArgs"),
    "BlacklistRuntimeStats": (".runtime_protocols", "BlacklistRuntimeStats"),
    "BootstrapRuntimeArgs": (".runtime_protocols", "BootstrapRuntimeArgs"),
    "CleanRuntimeArgs": (".runtime_protocols", "CleanRuntimeArgs"),
    "ClientFactoryLike": (".runtime_protocols", "ClientFactoryLike"),
    "CredentialsArgs": (".runtime_protocols", "CredentialsArgs"),
    "FieldFetchArgs": (".runtime_protocols", "FieldFetchArgs"),
    "FieldSelectionArgs": (".runtime_protocols", "FieldSelectionArgs"),
    "ResultWriteArgs": (".runtime_protocols", "ResultWriteArgs"),
    "RuntimeConcurrencyArgs": (".runtime_protocols", "RuntimeConcurrencyArgs"),
    "RunConfig": (".runtime_protocols", "RunConfig"),
    "RunConfigArgs": (".runtime_protocols", "RunConfigArgs"),
    "RunLoopArgs": (".runtime_protocols", "RunLoopArgs"),
    "SchedulerRuntimeArgs": (".runtime_protocols", "SchedulerRuntimeArgs"),
    "SemaphoreLike": (".runtime_protocols", "SemaphoreLike"),
    "SimulationSettingsArgs": (".runtime_protocols", "SimulationSettingsArgs"),
    "SimulationStageArgs": (".runtime_protocols", "SimulationStageArgs"),
    "StopAfterSubmittableArgs": (".runtime_protocols", "StopAfterSubmittableArgs"),
    "TemplateBuildArgs": (".runtime_protocols", "TemplateBuildArgs"),
    "TemplateFeedback": (".runtime_protocols", "TemplateFeedback"),
    "TemplateSequence": (".runtime_protocols", "TemplateSequence"),
    "TemplateStats": (".runtime_protocols", "TemplateStats"),
    "ExecutionState": (".runtime_state", "ExecutionState"),
    "FutureCompletionContext": (".runtime_state", "FutureCompletionContext"),
    "HistoricalRunState": (".runtime_state", "HistoricalRunState"),
    "InitializedRunContext": (".runtime_state", "InitializedRunContext"),
    "PendingFutureContext": (".runtime_state", "PendingFutureContext"),
    "PendingFutureLike": (".runtime_state", "PendingFutureLike"),
    "PendingTemplateEntry": (".runtime_state", "PendingTemplateEntry"),
    "RuntimeConcurrencyState": (".runtime_state", "RuntimeConcurrencyState"),
    "TemplateBuildContext": (".runtime_state", "TemplateBuildContext"),
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
