"""
模板过滤与跳过规则模块。

集中管理字段级与模板级的跳过判断，避免 executor 在编排逻辑中
重复内联同一组规则。
"""

from __future__ import annotations

from collections.abc import Sequence
import logging

from ..analysis.feedback import (
    is_legacy_family_disabled,
    is_template_disabled,
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)
from ..config import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    DatasetExpressionPolicy,
)
from ..models.base import (
    FieldTestResult,
    RunFilters,
    TemplateBuildContext,
    TemplateCandidate,
    TemplateFeedback,
)

logger = logging.getLogger(__name__)


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
    if field_id in skipped_fields_due_to_queue:
        logger.info("[skip] field=%s skipped after repeated queue-busy simulations", field_id)
        return True
    if (
        filters.include_fields
        and field_id not in filters.include_fields
        and field_name not in filters.include_fields
    ):
        logger.info("[skip] field=%s excluded by include-fields filter", field_id)
        return True
    if field_id in filters.exclude_fields or field_name in filters.exclude_fields:
        logger.info("[skip] field=%s excluded by exclude-fields filter", field_id)
        return True
    return False


def is_template_actionable(
    *,
    template: TemplateCandidate,
    build_ctx: TemplateBuildContext,
    field_id: str,
    field_name: str,
    field_feedback: TemplateFeedback | None,
    expression_policy: DatasetExpressionPolicy | None,
    template_stats: dict[str, dict[str, int]],
    prior_results: Sequence[FieldTestResult],
) -> bool:
    """判断模板在当前字段上下文中是否应继续展开 settings 变体。"""
    options = build_ctx.options
    template_name = template.name
    expression = template.expression
    priority = template.priority
    template_metadata = template.metadata
    if build_ctx.include_templates and template_name not in build_ctx.include_templates:
        return False
    if template_name in build_ctx.exclude_templates:
        return False
    if not should_keep_template_for_feedback(
        template_name,
        expression,
        priority,
        field_feedback,
        expression_policy=expression_policy,
        template_metadata=template_metadata,
    ):
        return False
    if should_skip_field_template_family(
        field_name,
        template_name,
        expression,
        template_metadata=template_metadata,
        expression_policy=expression_policy,
    ):
        return False
    if is_template_disabled(template_name, template_stats, options.template_disable_after):
        return False
    if is_legacy_family_disabled(
        template_name,
        expression,
        template_stats,
        options.disable_legacy_after,
        template_metadata=template_metadata,
    ):
        return False
    return not should_skip_expression_by_history(field_id, template_name, expression, prior_results)
