"""Helpers for future completion context and result resolution."""

from __future__ import annotations

from concurrent.futures import Future

from ..models.domain import FieldTestResult
from ..models.runtime_options import ResultWriteOptions
from ..models.runtime_protocols import RunConfig
from ..runtime.contexts import (
    FutureCompletionContext,
    PendingFutureContext,
)
from .simulation_results import build_failure_result


def _context_value(
    context: PendingFutureContext | dict[str, object], key: str, default: object = ""
) -> object:
    """Read one value from either PendingFutureContext or legacy dict-style test contexts."""
    if isinstance(context, dict):
        return context.get(key, default)
    return getattr(context, key, default)


def build_completion_context(
    *,
    result_write_options: ResultWriteOptions,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: RunConfig | None,
) -> FutureCompletionContext:
    """Build the immutable completion context shared by done futures."""
    return FutureCompletionContext(
        result_write_options=result_write_options,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
    )


def resolve_completed_future_result(
    future: Future[FieldTestResult],
    *,
    context: PendingFutureContext,
    template_library_fingerprint: str,
) -> FieldTestResult:
    """Resolve one completed future into a concrete result row."""
    try:
        return future.result()
    except Exception as exc:
        settings_value = _context_value(context, "settings", {})
        settings = dict(settings_value) if isinstance(settings_value, dict) else {}
        return build_failure_result(
            field_id=str(_context_value(context, "field_id")),
            field_type=str(_context_value(context, "field_type")),
            field_name=str(_context_value(context, "field_name")),
            template_name=str(_context_value(context, "template_name")),
            template_family=str(_context_value(context, "template_family")),
            template_stage=str(_context_value(context, "template_stage")),
            template_role=str(_context_value(context, "template_role")),
            template_activation_scope=str(_context_value(context, "template_activation_scope")),
            policy_version=str(_context_value(context, "policy_version")),
            simulation_id=None,
            alpha_id=None,
            expression=str(_context_value(context, "expression")),
            settings_fingerprint=str(_context_value(context, "settings_fingerprint")),
            template_library_fingerprint=template_library_fingerprint,
            settings=settings,
            failed_stage="worker",
            message=str(exc),
        )
