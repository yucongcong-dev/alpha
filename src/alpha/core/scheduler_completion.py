"""Helpers for future completion context and result resolution."""

from __future__ import annotations

from concurrent.futures import Future

from ..models.domain import FieldTestResult
from ..models.runtime_options import ResultWriteOptions
from ..models.runtime_protocols import RunConfig
from ..runtime.contexts import FutureCompletionContext, PendingFutureContext
from .simulation_results import build_failure_result


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
        settings = dict(context.settings)
        return build_failure_result(
            field_id=context.field_id,
            field_type=context.field_type,
            field_name=context.field_name,
            template_name=context.template_name,
            template_family=context.template_family,
            template_stage=context.template_stage,
            template_role=context.template_role,
            template_activation_scope=context.template_activation_scope,
            policy_version=context.policy_version,
            simulation_id=None,
            alpha_id=None,
            expression=context.expression,
            settings_fingerprint=context.settings_fingerprint,
            template_library_fingerprint=template_library_fingerprint,
            settings=settings,
            failed_stage="worker",
            message=str(exc),
        )
