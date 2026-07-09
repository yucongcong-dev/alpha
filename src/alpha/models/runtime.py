"""Compatibility export layer for runtime model access.

The runtime surface is split across config/options/protocol/state modules. This
module preserves the historical ``alpha.models.runtime`` import path while
loading concrete definitions lazily.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .domain import TemplateField
    from .runtime_config import (
        ApiClientConfig,
        BootstrapConfig,
        CleanConfig,
        CredentialsConfig,
        FieldFetchConfig,
        FieldSelectionConfig,
        ResultWriteConfig,
        RunLoopConfig,
        SchedulerConfig,
        SimulationSettingsConfig,
        SimulationStageConfig,
        TemplateBuildConfig,
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

__all__ = [
    "ApiClientArgs",
    "ApiClientConfig",
    "ApiClientOptions",
    "BlacklistRuntimeStats",
    "BootstrapConfig",
    "BootstrapRuntimeArgs",
    "CleanConfig",
    "CleanRuntimeArgs",
    "ClientFactoryLike",
    "CredentialsArgs",
    "CredentialsConfig",
    "ExecutionState",
    "FieldFetchArgs",
    "FieldFetchConfig",
    "FieldFetchOptions",
    "FieldSelectionArgs",
    "FieldSelectionConfig",
    "FutureCompletionContext",
    "HistoricalRunState",
    "InitializedRunContext",
    "PendingFutureContext",
    "PendingFutureLike",
    "PendingTemplateEntry",
    "ResultWriteArgs",
    "ResultWriteConfig",
    "ResultWriteOptions",
    "RunConfig",
    "RunConfigArgs",
    "RunLoopArgs",
    "RunLoopConfig",
    "RuntimeConcurrencyState",
    "SchedulerConfig",
    "SchedulerRuntimeArgs",
    "SemaphoreLike",
    "SimulationSettingsArgs",
    "SimulationSettingsConfig",
    "SimulationStageArgs",
    "SimulationStageConfig",
    "StopAfterSubmittableArgs",
    "TemplateBuildArgs",
    "TemplateBuildConfig",
    "TemplateBuildContext",
    "TemplateBuildOptions",
    "TemplateFeedback",
    "TemplateField",
    "TemplateSequence",
    "TemplateStats",
]

_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "TemplateField": (".domain", "TemplateField"),
    "ApiClientConfig": (".runtime_config", "ApiClientConfig"),
    "BootstrapConfig": (".runtime_config", "BootstrapConfig"),
    "CleanConfig": (".runtime_config", "CleanConfig"),
    "CredentialsConfig": (".runtime_config", "CredentialsConfig"),
    "FieldFetchConfig": (".runtime_config", "FieldFetchConfig"),
    "FieldSelectionConfig": (".runtime_config", "FieldSelectionConfig"),
    "ResultWriteConfig": (".runtime_config", "ResultWriteConfig"),
    "RunLoopConfig": (".runtime_config", "RunLoopConfig"),
    "SchedulerConfig": (".runtime_config", "SchedulerConfig"),
    "SimulationSettingsConfig": (".runtime_config", "SimulationSettingsConfig"),
    "SimulationStageConfig": (".runtime_config", "SimulationStageConfig"),
    "TemplateBuildConfig": (".runtime_config", "TemplateBuildConfig"),
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
