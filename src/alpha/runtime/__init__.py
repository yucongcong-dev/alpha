"""Runtime session contexts and mutable execution state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from .contexts import (
        FutureCompletionContext,
        HistoricalRunState,
        PendingFutureContext,
        PendingTemplateEntry,
        TemplateBuildContext,
    )
    from .state import (
        ExecutionState,
        InitializedRunContext,
        PendingFutureLike,
        RuntimeConcurrencyState,
    )

_EXPORT_MAP: ExportMap = {
    "FutureCompletionContext": (".contexts", "FutureCompletionContext"),
    "HistoricalRunState": (".contexts", "HistoricalRunState"),
    "PendingFutureContext": (".contexts", "PendingFutureContext"),
    "PendingTemplateEntry": (".contexts", "PendingTemplateEntry"),
    "TemplateBuildContext": (".contexts", "TemplateBuildContext"),
    "ExecutionState": (".state", "ExecutionState"),
    "InitializedRunContext": (".state", "InitializedRunContext"),
    "PendingFutureLike": (".state", "PendingFutureLike"),
    "RuntimeConcurrencyState": (".state", "RuntimeConcurrencyState"),
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
