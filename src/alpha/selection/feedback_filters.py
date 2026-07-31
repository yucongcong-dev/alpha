"""Template feedback pruning and skip policies."""

from __future__ import annotations

from ..analysis.feedback_stats import dominant_failed_check_names
from ..config.constants import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_TURNOVER,
    FEEDBACK_STAGE_RESIMULATE,
)
from ..config.models import DatasetExpressionPolicy
from ..config.runtime_values import get_runtime_config
from ..generators.templates.classification import (
    classify_expression_family,
    classify_template_stage,
)
from ..generators.templates.variation_common import (
    is_blacklisted_template as _is_blacklisted_template,
)
from ..models.domain_types import FieldFeedbackSummary, TemplateMetadata
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage


def should_keep_template_for_feedback(
    template_name: str,
    expression: str,
    priority: int,
    field_feedback: FieldFeedbackSummary | None,
    *,
    dataset_id: str = "",
    expression_policy: DatasetExpressionPolicy | None = None,
    template_metadata: TemplateMetadata | None = None,
) -> bool:
    """在字段反馈足够后剪掉低信号、低价值的模板。"""
    if not field_feedback:
        return True
    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    feedback_stage = resolve_feedback_stage(field_feedback, policy.feedback_loop_policy)
    stage_policy = (
        policy.feedback_loop_policy.resimulate
        if feedback_stage == FEEDBACK_STAGE_RESIMULATE
        else policy.feedback_loop_policy.generate
    )
    if not stage_policy.enable_template_pruning:
        return True

    dominant_counts = field_feedback.get("failed_check_counts", {})
    dominant_names = dominant_failed_check_names(dominant_counts)
    family = classify_expression_family(template_name, expression, template_metadata)
    template_stage = classify_template_stage(template_name, expression, template_metadata)
    lower_name = template_name.lower()
    lower_expr = expression.lower()

    if (
        feedback_stage == FEEDBACK_STAGE_RESIMULATE
        and stage_policy.preferred_template_stages
        and template_stage not in stage_policy.preferred_template_stages
        and template_name not in policy.protected_templates
    ):
        return False
    if lower_name.startswith("iter_"):
        return True
    if template_name in policy.protected_templates:
        return True

    if CHECK_LOW_TURNOVER in dominant_names:
        if "ts_mean(" in lower_expr and "-" not in lower_expr and "/" not in lower_expr:
            return False
        if (
            "ts_backfill(" in lower_expr
            and "ts_delta" not in lower_expr
            and "ts_zscore" not in lower_expr
        ):
            return False

    if (
        CHECK_HIGH_TURNOVER in dominant_names
        and CHECK_CONCENTRATED_WEIGHT in dominant_names
        and family in {"rank_spread", "mean_spread"}
        and "zscore" in lower_name
        and "spread" in lower_name
    ):
        return False

    return priority >= get_runtime_config().feedback.feedback_template_min_priority


def should_skip_field_template_family(
    field_name: str,
    template_name: str,
    expression: str,
    *,
    use_dataset_heuristics: bool | None = None,
    dataset_id: str = "",
    expression_policy: DatasetExpressionPolicy | None = None,
    template_metadata: TemplateMetadata | None = None,
) -> bool:
    """对已经证明偏弱的字段-模板家族组合做先验剪枝。"""
    policy = expression_policy or get_dataset_expression_policy(
        dataset_id,
        use_curated_heuristics=use_dataset_heuristics,
    )
    if not policy.use_curated_heuristics:
        return False

    return _is_blacklisted_template(
        template_name,
        expression,
        template_metadata=template_metadata,
        policy=policy,
    )
