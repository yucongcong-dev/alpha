"""
Expression candidate construction.

表达式候选构建模块。

This module owns the orchestration flow that turns a field, template library,
dataset policy, and feedback into ordered alpha expression candidates.

本模块只负责编排：把字段、模板库、数据集策略和反馈转换为有序 Alpha 表达式
候选。具体 MATRIX/ratio 模板、分类、优先级和变体构造放在各自子模块中。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config.getters import get_backfill_window
from ..config.models import DatasetExpressionPolicy
from ..generators.field_transforms import build_field_view
from ..models.domain import FieldView, TemplateCandidate, TemplateField, TemplateLibraryItem
from ..models.runtime import TemplateBuildContext, TemplateFeedback
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage
from ..policy.template_blacklist import load_default_avoid_rules
from .templates.variation_common import is_blacklisted_template as _is_blacklisted_template
from ..utils.helpers import is_event_field_name
from .fields import choose_field_name, choose_field_type
from .matrix_templates import build_matrix_templates
from .templates.candidates import (
    _coerce_template_candidate,
    _make_template_candidate,
)
from .templates.classification import classify_expression_family, classify_template_stage
from .templates.metadata import _runtime_template_metadata, _select_template_items
from .templates.priority import (
    apply_adaptive_priority,
    apply_similarity_penalty,
    cap_templates_per_family,
)
from .templates.variations import build_feedback_mutations


def _load_default_avoid_rules() -> list[dict[str, str]]:
    """兼容导出：加载跨数据集默认规避规则。"""
    return list(load_default_avoid_rules())


def _policy_template_priority_adjustment(
    template_name: str,
    policy: DatasetExpressionPolicy,
) -> int:
    """按数据集策略调整模板优先级。"""
    lower_name = template_name.lower()
    adjustment = policy.account_template_boost if lower_name.startswith("account_") else 0
    if lower_name in policy.template_priority_penalties:
        adjustment += policy.template_priority_penalties[lower_name]
        return adjustment
    for prefixes, penalty in policy.template_prefix_penalties.items():
        if lower_name.startswith(prefixes):
            adjustment += penalty
            return adjustment
    return adjustment


def _is_event_field(field_name: str, policy: DatasetExpressionPolicy) -> bool:
    """按策略前缀判断字段是否属于事件类字段。"""
    return is_event_field_name(field_name, policy.event_field_prefixes)


def _event_template_allowed(
    candidate: TemplateCandidate,
    policy: DatasetExpressionPolicy,
) -> bool:
    """事件字段只保留更窄的模板池，避免高噪音模板占预算。"""
    if not (
        policy.event_allowed_template_stages
        or policy.event_allowed_template_prefixes
        or policy.event_allowed_template_families
    ):
        return True
    name = candidate.name
    family = classify_expression_family(name, candidate.expression, candidate.metadata)
    stage = classify_template_stage(name, candidate.expression, candidate.metadata)
    if policy.event_allowed_template_stages and stage in policy.event_allowed_template_stages:
        return True
    if policy.event_allowed_template_families and family in policy.event_allowed_template_families:
        return True
    return bool(
        policy.event_allowed_template_prefixes
        and any(name.startswith(prefix) for prefix in policy.event_allowed_template_prefixes)
    )


def _template_supports_field_tags(
    candidate: TemplateCandidate,
    field: FieldView,
) -> bool:
    raw_tags = candidate.metadata.get("field_tags")
    if not raw_tags:
        return True
    if not isinstance(raw_tags, (list, tuple, set)):
        return True
    field_tags = field.metadata.get("runtime_field_tags") or ()
    if not isinstance(field_tags, (list, tuple, set)):
        return True
    allowed_tags = {str(tag) for tag in raw_tags}
    current_tags = {str(tag) for tag in field_tags}
    return bool(allowed_tags & current_tags)



def sort_templates_by_priority(
    templates: Sequence[TemplateCandidate | tuple[str, str, int]],
) -> list[TemplateCandidate]:
    """按有效优先级从高到低排序候选模板。"""
    normalized = [_coerce_template_candidate(template) for template in templates]
    return sorted(normalized, key=lambda item: (-item.priority, item.name, item.expression))


def limit_templates(
    templates: Sequence[TemplateCandidate | tuple[str, str, int]],
    max_templates_per_field: int,
) -> list[TemplateCandidate]:
    """应用字段级模板数量上限；小于等于 0 表示不限制。"""
    normalized = [_coerce_template_candidate(template) for template in templates]
    if max_templates_per_field <= 0:
        return normalized
    return normalized[:max_templates_per_field]


def build_expression_candidates(
    field: TemplateField,
    build_ctx: TemplateBuildContext,
    *,
    max_templates_per_field: int,
    max_templates_per_family: int,
    field_feedback: TemplateFeedback | None = None,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> list[TemplateCandidate]:
    """为单个字段构建、变异、多样化并排序表达式候选。"""
    options = build_ctx.options
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    all_fields = list(build_ctx.all_fields)
    global_failed_check_counts = dict(build_ctx.global_failed_check_counts)
    policy = expression_policy or get_dataset_expression_policy(
        options.dataset_id,
        use_curated_heuristics=build_ctx.use_dataset_heuristics,
    )
    feedback_stage = resolve_feedback_stage(field_feedback, policy.feedback_loop_policy)
    field_view = build_field_view(field, policy)
    is_event_field = _is_event_field(field_name, policy)

    raw_templates = _select_template_items(build_ctx.template_library, field_type, policy.dataset_id)
    templates = [
        _make_template_candidate(
            item.name,
            item.expression.format(
                field=field_view.raw_expression,
                field_preprocessed=field_view.preprocessed_expression,
                field_groupfill=field_view.groupfill_expression,
                ratio_numerator=field_view.ratio_numerator_expression,
                ratio_denominator=field_view.ratio_denominator_expression,
                backfill_window=get_backfill_window(),
            ),
            item.priority + _policy_template_priority_adjustment(item.name, policy),
            metadata=_runtime_template_metadata(item),
        )
        for item in raw_templates
        if isinstance(item, TemplateLibraryItem)
        and item.name not in policy.disabled_templates
        and not _is_blacklisted_template(
            item.name,
            item.expression,
            template_metadata=_runtime_template_metadata(item),
            policy=policy,
        )
    ]
    templates.extend(
        build_feedback_mutations(
            field_name,
            field_feedback,
            expression_policy=policy,
            feedback_stage=feedback_stage,
        )
    )

    if field_type == "MATRIX":
        diversified, legacy = build_matrix_templates(
            field_view,
            all_fields,
            policy,
        )
        templates.extend(diversified)
        templates.extend(legacy)

    if is_event_field:
        templates = [item for item in templates if _event_template_allowed(item, policy)]
    templates = [item for item in templates if _template_supports_field_tags(item, field_view)]

    templates = apply_similarity_penalty(templates, options.legacy_similarity_penalty)
    templates = apply_adaptive_priority(
        templates,
        field_feedback=field_feedback,
        global_failed_check_counts=global_failed_check_counts,
    )
    templates = sort_templates_by_priority(templates)
    return limit_templates(
        cap_templates_per_family(templates, max_templates_per_family),
        max_templates_per_field,
    )
