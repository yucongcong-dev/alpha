"""
simulation 结果构建辅助模块。
"""

from __future__ import annotations

from typing import Any

from ..config.constants import STATUS_ERROR
from ..models.domain import FieldTestContext, FieldTestResult


def build_failure_result(
    *,
    field_id: str,
    field_type: str,
    field_name: str,
    template_name: str,
    template_family: str = "",
    template_stage: str = "",
    simulation_id: str | None,
    alpha_id: str | None,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    failed_stage: str,
    message: str,
    status: str = STATUS_ERROR,
    failed_checks: list[dict[str, Any]] | None = None,
) -> FieldTestResult:
    return FieldTestResult(
        field_id=field_id,
        field_type=field_type,
        field_name=field_name,
        template_name=template_name,
        template_family=template_family,
        template_stage=template_stage,
        simulation_id=simulation_id,
        alpha_id=alpha_id,
        status=status,
        submittable=False,
        submitted=False,
        message=message,
        expression=expression,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        failed_stage=failed_stage,
        failed_checks=failed_checks,
    )


def handle_stage_error(
    ctx: FieldTestContext,
    failed_stage: str,
    exc: Exception,
    *,
    simulation_id: str | None = None,
    alpha_id: str | None = None,
) -> FieldTestResult:
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise exc
    return ctx.failure(
        failed_stage=failed_stage,
        message=str(exc),
        simulation_id=simulation_id,
        alpha_id=alpha_id,
    )


__all__ = ["build_failure_result", "handle_stage_error"]
