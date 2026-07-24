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
from pathlib import Path
from typing import Any

from ..config.constants import FEEDBACK_STAGE_GENERATE, FEEDBACK_STAGE_RESIMULATE
from ..config.models import DatasetExpressionPolicy
from ..config.runtime_values import get_runtime_config
from ..generators.field_transforms import build_field_view
from ..models.domain import FieldView, TemplateCandidate, TemplateField, TemplateLibraryItem
from ..models.runtime_protocols import TemplateFeedback
from ..runtime import TemplateBuildContext
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


def _is_explicit_refine_library(template_library_file: str) -> bool:
    """显式 refine 模板库使用 refine/ 子目录路径。"""
    if not template_library_file:
        return False
    parts = {part.strip().lower() for part in Path(template_library_file).parts}
    return "refine" in parts


def _is_dataset_default_library(template_library_file: str, dataset_id: str) -> bool:
    """判断是否正在使用 templates/<dataset>/library.json 这类默认主模板库。"""
    if not template_library_file or not dataset_id:
        return False
    path = Path(template_library_file)
    if path.name.lower() != "library.json":
        return False
    parts = [part.strip().lower() for part in path.parts]
    if len(parts) < 2:
        return False
    return parts[-2] == dataset_id.strip().lower()


def _resolve_activation_scope(candidate: TemplateCandidate) -> str:
    """模板激活范围，默认 broad。"""
    raw_scope = str(candidate.metadata.get("activation_scope", "")).strip().lower()
    if raw_scope in {"broad", "refine", "diagnostic"}:
        return raw_scope
    return "broad"


def _template_scope_allowed(
    candidate: TemplateCandidate,
    *,
    feedback_stage: str,
    template_library_file: str,
) -> bool:
    """按模板激活范围和当前运行阶段决定是否放行模板。"""
    activation_scope = _resolve_activation_scope(candidate)
    if activation_scope == "broad":
        return True

    explicit_refine_library = _is_explicit_refine_library(template_library_file)
    if activation_scope == "refine":
        return explicit_refine_library or feedback_stage != FEEDBACK_STAGE_GENERATE
    if activation_scope == "diagnostic":
        return explicit_refine_library or feedback_stage == FEEDBACK_STAGE_RESIMULATE
    return True


def _is_closed_candidate_library(
    template_library_file: str,
    *,
    dataset_id: str,
    policy: DatasetExpressionPolicy,
) -> bool:
    """判断当前模板库是否应被视为闭合集，不再自动外扩默认候选。"""
    if _is_explicit_refine_library(template_library_file):
        return True
    return bool(
        policy.closed_default_template_library
        and _is_dataset_default_library(template_library_file, dataset_id)
    )



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
    backfill_window = get_runtime_config().expression.backfill_window

    closed_candidate_library = _is_closed_candidate_library(
        build_ctx.template_library_file,
        dataset_id=policy.dataset_id,
        policy=policy,
    )
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
                backfill_window=backfill_window,
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
    if not closed_candidate_library:
        templates.extend(
            build_feedback_mutations(
                field_name,
                field_feedback,
                expression_policy=policy,
                feedback_stage=feedback_stage,
            )
        )

    # Closed candidate libraries are expected to remain compact and explicit.
    # Do not silently re-expand them with auto-generated MATRIX neighbors.
    if field_type == "MATRIX" and not closed_candidate_library:
        diversified, legacy = build_matrix_templates(
            field_view,
            all_fields,
            policy,
        )
        templates.extend(diversified)
        templates.extend(legacy)

    if is_event_field:
        templates = [item for item in templates if _event_template_allowed(item, policy)]
    templates = [
        item
        for item in templates
        if _template_scope_allowed(
            item,
            feedback_stage=feedback_stage,
            template_library_file=build_ctx.template_library_file,
        )
    ]
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
