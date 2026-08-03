"""
模板过滤与跳过规则模块。

集中管理字段级与模板级的跳过判断，避免 executor 在编排逻辑中
重复内联同一组规则。
"""

from __future__ import annotations

from collections.abc import Sequence
import logging

from ..config.constants import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
)
from ..config.models import DatasetExpressionPolicy
from ..models.domain import FieldTestResult, TemplateCandidate
from ..models.io_types import RunFilters
from ..models.runtime_protocols import TemplateFeedback
from ..runtime.contexts import TemplateBuildContext
from ..selection.feedback_filters import (
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)

logger = logging.getLogger(__name__)


def is_template_selected_by_filters(
    build_ctx: TemplateBuildContext,
    template_name: str,
) -> bool:
    """Return whether a template survives explicit include/exclude name filters."""
    if build_ctx.include_templates and template_name not in build_ctx.include_templates:
        return False
    return template_name not in build_ctx.exclude_templates


def should_skip_expression_by_history(
    field_id: str,
    template_name: str,
    expression: str,
    prior_results: Sequence[FieldTestResult],
) -> bool:
    """对历史上已明显偏弱的同字段同表达式，续跑时直接跳过剩余变体。"""
    for result in prior_results:
        if (
            result.field_id != field_id
            or result.template_name != template_name
            or result.expression != expression
        ):
            continue
        if result.submittable:
            return False
        failed_checks = result.failed_checks or []
        if not failed_checks:
            continue
        values = {str(check.get("name")): check.get("value") for check in failed_checks}
        low_sharpe = values.get(CHECK_LOW_SHARPE)
        low_fitness = values.get(CHECK_LOW_FITNESS)
        if (
            isinstance(low_sharpe, (int, float))
            and isinstance(low_fitness, (int, float))
            and low_sharpe < 0.0
            and low_fitness < 0.0
        ):
            return True
        if CHECK_CONCENTRATED_WEIGHT in values and CHECK_LOW_SUB_UNIVERSE_SHARPE in values:
            return True
    return False


def should_skip_field(
    field_id: str,
    field_name: str,
    filters: RunFilters,
    skipped_fields_due_to_queue: set[str],
) -> bool:
    """判断某个字段是否应在生成模板前被直接跳过。"""
    skip_reason = resolve_field_skip_reason(
        field_id,
        field_name,
        filters,
        skipped_fields_due_to_queue,
    )
    if skip_reason == "queue":
        logger.info("[skip] field=%s skipped after repeated queue-busy simulations", field_id)
        return True
    if skip_reason == "include":
        logger.info("[skip] field=%s excluded by include-fields filter", field_id)
        return True
    if skip_reason == "exclude":
        logger.info("[skip] field=%s excluded by exclude-fields filter", field_id)
        return True
    return False


def resolve_field_skip_reason(
    field_id: str,
    field_name: str,
    filters: RunFilters,
    skipped_fields_due_to_queue: set[str],
) -> str | None:
    """Return the field skip reason without emitting logs or mutating state."""
    if field_id in skipped_fields_due_to_queue:
        return "queue"
    if (
        filters.include_fields
        and field_id not in filters.include_fields
        and field_name not in filters.include_fields
    ):
        return "include"
    if field_id in filters.exclude_fields or field_name in filters.exclude_fields:
        return "exclude"
    return None


def is_template_actionable(
    *,
    template: TemplateCandidate,
    build_ctx: TemplateBuildContext,
    field_id: str,
    field_name: str,
    field_feedback: TemplateFeedback | None,
    expression_policy: DatasetExpressionPolicy | None,
    prior_results: Sequence[FieldTestResult],
) -> bool:
    """判断模板在当前字段上下文中是否应继续展开 settings 变体。"""
    return (
        resolve_template_skip_reason(
            template=template,
            build_ctx=build_ctx,
            field_id=field_id,
            field_name=field_name,
            field_feedback=field_feedback,
            expression_policy=expression_policy,
            prior_results=prior_results,
        )
        is None
    )


def resolve_template_skip_reason(
    *,
    template: TemplateCandidate,
    build_ctx: TemplateBuildContext,
    field_id: str,
    field_name: str,
    field_feedback: TemplateFeedback | None,
    expression_policy: DatasetExpressionPolicy | None,
    prior_results: Sequence[FieldTestResult],
) -> str | None:
    """Return the template skip reason without emitting logs or mutating state."""
    template_name = template.name
    expression = template.expression
    priority = template.priority
    template_metadata = template.metadata
    if not is_template_selected_by_filters(build_ctx, template_name):
        return "name_filter"
    if build_ctx.options.preset_mode:
        if should_skip_expression_by_history(
            field_id,
            template_name,
            expression,
            prior_results,
        ):
            return "history"
        return None
    if not should_keep_template_for_feedback(
        template_name,
        expression,
        priority,
        field_feedback,
        expression_policy=expression_policy,
        template_metadata=template_metadata,
    ):
        return "feedback"
    if should_skip_field_template_family(
        field_name,
        template_name,
        expression,
        template_metadata=template_metadata,
        expression_policy=expression_policy,
    ):
        return "family"
    if should_skip_expression_by_history(field_id, template_name, expression, prior_results):
        return "history"
    return None
