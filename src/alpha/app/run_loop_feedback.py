"""Runtime feedback refresh helpers for the run loop."""

from __future__ import annotations

from ..analysis.feedback_stats import (
    compile_failed_check_counts_by_field_type,
    compile_field_feedback,
    compile_global_failed_check_counts,
    update_failed_check_counts_by_field_type,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from ..models.domain import FieldTestResult
from ..runtime.contexts import TemplateBuildContext


def refresh_runtime_feedback(
    template_build_ctx: TemplateBuildContext,
    results: list[FieldTestResult],
    *,
    force: bool = False,
) -> None:
    """Incrementally feed newly produced results back into the template context."""
    result_count = len(results)
    cached_count = template_build_ctx.feedback_result_count
    if force:
        template_build_ctx.field_feedback = compile_field_feedback(results)
        template_build_ctx.global_failed_check_counts = compile_global_failed_check_counts(results)
        template_build_ctx.failed_check_counts_by_field_type = (
            compile_failed_check_counts_by_field_type(results)
        )
        template_build_ctx.feedback_result_count = result_count
        return
    if cached_count == result_count:
        return
    if cached_count < 0 or cached_count > result_count:
        template_build_ctx.field_feedback = compile_field_feedback(results)
        template_build_ctx.global_failed_check_counts = compile_global_failed_check_counts(results)
        template_build_ctx.failed_check_counts_by_field_type = (
            compile_failed_check_counts_by_field_type(results)
        )
        template_build_ctx.feedback_result_count = result_count
        return
    for result in results[cached_count:]:
        update_field_feedback_with_result(template_build_ctx.field_feedback, result)
        update_global_failed_check_counts_with_result(
            template_build_ctx.global_failed_check_counts,
            result,
        )
        update_failed_check_counts_by_field_type(
            template_build_ctx.failed_check_counts_by_field_type,
            result,
        )
    template_build_ctx.feedback_result_count = result_count
