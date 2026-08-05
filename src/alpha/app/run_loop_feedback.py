"""Runtime feedback refresh helpers for the run loop."""

from __future__ import annotations

from dataclasses import dataclass

from ..analysis.feedback_stats import (
    compile_failed_check_counts_by_field_type,
    compile_field_feedback,
    compile_global_failed_check_counts,
    update_failed_check_counts_by_field_type,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from ..models.domain import FieldTestResult
from ..models.result_predicates import (
    is_feedback_eligible_result,
    is_queue_timeout_result,
    is_retryable_infrastructure_result,
)
from ..runtime.contexts import TemplateBuildContext


@dataclass(frozen=True, slots=True)
class RuntimeFeedbackRefresh:
    """Describe which cached template queues must be rebuilt after new results."""

    feedback_changed: bool
    retry_field_ids: frozenset[str] = frozenset()


def refresh_runtime_feedback(
    template_build_ctx: TemplateBuildContext,
    results: list[FieldTestResult],
    *,
    force: bool = False,
) -> RuntimeFeedbackRefresh:
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
        return RuntimeFeedbackRefresh(feedback_changed=True)
    if cached_count == result_count:
        return RuntimeFeedbackRefresh(feedback_changed=False)
    if cached_count is None or cached_count > result_count:
        template_build_ctx.field_feedback = compile_field_feedback(results)
        template_build_ctx.global_failed_check_counts = compile_global_failed_check_counts(results)
        template_build_ctx.failed_check_counts_by_field_type = (
            compile_failed_check_counts_by_field_type(results)
        )
        template_build_ctx.feedback_result_count = result_count
        return RuntimeFeedbackRefresh(feedback_changed=True)
    feedback_changed = False
    retry_field_ids: set[str] = set()
    for result in results[cached_count:]:
        feedback_changed = feedback_changed or is_feedback_eligible_result(result)
        if is_queue_timeout_result(result) or is_retryable_infrastructure_result(result):
            retry_field_ids.add(result.field_id)
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
    return RuntimeFeedbackRefresh(
        feedback_changed=feedback_changed,
        retry_field_ids=frozenset(retry_field_ids),
    )
