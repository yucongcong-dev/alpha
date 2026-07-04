"""
模板队列构建辅助模块。

承载模板候选解析与 settings 变体展开等可复用逻辑，
避免 executor 模块同时承担流程编排和细粒度队列构建职责。
"""

from __future__ import annotations

from collections.abc import Sequence

from ..analysis.feedback_history import (
    choose_settings_variant_budget,
    select_nearpass_candidates,
)
from ..analysis.stats import historical_template_priority_bonus
from ..config.constants import (
    FEEDBACK_STAGE_RESIMULATE,
    SENTINEL_UNKNOWN,
)
from ..config.models import DatasetExpressionPolicy
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage
from ..generators.expression_builder import (
    build_expression_candidates,
    limit_templates,
    sort_templates_by_priority,
)
from ..generators.payload import build_settings_fingerprint_from_payload
from ..generators.templates.classification import (
    classify_expression_family,
    classify_template_stage,
)
from ..generators.templates.priority import cap_templates_per_family
from ..generators.templates.refine import build_refine_templates
from ..generators.variants import build_setting_variants
from ..models.domain import (
    FailedCheck,
    FieldTestResult,
    NearPassCandidate,
    SettingsVariant,
    TemplateCandidate,
    TemplateField,
)
from ..models.runtime import TemplateBuildContext, TemplateFeedback
from ..generators.fields import choose_field_name
from ..utils.helpers import first_non_empty, is_event_field_name


def resolve_field_template_candidates(
    build_ctx: TemplateBuildContext,
    field: TemplateField,
    *,
    prior_results: Sequence[FieldTestResult],
    build_refine_templates_fn=build_refine_templates,
    build_expression_candidates_fn=build_expression_candidates,
) -> tuple[list[TemplateCandidate], TemplateFeedback, DatasetExpressionPolicy]:
    """为单个字段解析模板候选、字段反馈和表达式策略。"""
    options = build_ctx.options
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
    field_name = choose_field_name(field)
    field_feedback = build_ctx.field_feedback.get(field_id)
    expression_policy = build_ctx.expression_policy or get_dataset_expression_policy(options.dataset_id)
    is_event_field = is_event_field_name(field_name, expression_policy.event_field_prefixes)
    max_templates_per_field = (
        expression_policy.event_max_templates_per_field
        if is_event_field and expression_policy.event_max_templates_per_field > 0
        else options.max_templates_per_field
    )
    max_templates_per_family = (
        expression_policy.event_max_templates_per_family
        if is_event_field and expression_policy.event_max_templates_per_family > 0
        else options.max_templates_per_family
    )
    feedback_stage = resolve_feedback_stage(
        field_feedback,
        expression_policy.feedback_loop_policy,
    )
    nearpass_candidates = (
        select_nearpass_candidates(
            field_id,
            prior_results,
            expression_policy=expression_policy,
        )
        if feedback_stage == FEEDBACK_STAGE_RESIMULATE
        else []
    )
    if nearpass_candidates:
        templates = build_refine_templates_fn(
            field_name,
            nearpass_candidates,
            expression_policy=expression_policy,
        )
        templates = limit_templates(
            cap_templates_per_family(
                sort_templates_by_priority(templates),
                max_templates_per_family,
            ),
            max_templates_per_field,
        )
    else:
        templates = build_expression_candidates_fn(
            field,
            build_ctx.template_library,
            max_templates_per_field,
            max_templates_per_family,
            options.legacy_similarity_penalty,
            all_fields=build_ctx.all_fields,
            field_feedback=field_feedback,
            global_failed_check_counts=build_ctx.global_failed_check_counts,
            use_dataset_heuristics=build_ctx.use_dataset_heuristics,
            dataset_id=options.dataset_id,
            expression_policy=expression_policy,
        )
    templates = limit_templates(
        cap_templates_per_family(
            sort_templates_by_priority(templates),
            max_templates_per_family,
        ),
        max_templates_per_field,
    )
    return templates, field_feedback or {}, expression_policy


def build_pending_template_variants(
    build_ctx: TemplateBuildContext,
    field: TemplateField,
    *,
    templates: Sequence[TemplateCandidate],
    template_stats: dict[str, dict[str, int]],
    attempted_keys: set[tuple[str, str, str, str]],
    reserved_keys: set[tuple[str, str, str, str]],
    field_feedback: TemplateFeedback | None,
    build_setting_variants_fn=build_setting_variants,
    build_settings_fingerprint_fn=build_settings_fingerprint_from_payload,
) -> list[tuple[str, str, str, str, int, SettingsVariant, str]]:
    """把模板候选展开为真正待执行的 settings 变体队列。"""
    options = build_ctx.options
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
    field_name = choose_field_name(field)
    pending_templates: list[tuple[str, str, str, str, int, SettingsVariant, str]] = []
    all_reserved_keys = attempted_keys | reserved_keys
    max_setting_variants = choose_settings_variant_budget(
        field_feedback,
        expression_policy=build_ctx.expression_policy,
    )
    for template in templates:
        template_name = template.name
        expression = template.expression
        priority = template.priority
        template_metadata = template.metadata
        template_family = classify_expression_family(
            template_name,
            expression,
            template_metadata,
        )
        template_stage = classify_template_stage(
            template_name,
            expression,
            template_metadata,
        )
        effective_priority = priority + historical_template_priority_bonus(
            template_name, template_stats
        )
        refine_candidate = None
        refine_failed_checks = template_metadata.get("refine_failed_checks")
        if isinstance(refine_failed_checks, list):
            refine_candidate = NearPassCandidate(
                field_id=field_id,
                field_name=field_name,
                template_name=template_name,
                expression=expression,
                template_family=template_family,
                template_stage=template_stage,
                score=float(template_metadata.get("refine_score", 0.0) or 0.0),
                failed_checks=[
                    FailedCheck.from_dict(check) for check in refine_failed_checks
                ],
            )
        for settings_variant in build_setting_variants_fn(
            options,
            template_name,
            expression,
            field_feedback=field_feedback,
            refine_candidate=refine_candidate,
        )[:max_setting_variants]:
            variant_fingerprint = build_settings_fingerprint_fn(settings_variant)
            if (field_id, template_name, expression, variant_fingerprint) in all_reserved_keys:
                continue
            pending_templates.append(
                (
                    template_name,
                    template_family,
                    template_stage,
                    expression,
                    effective_priority,
                    settings_variant,
                    variant_fingerprint,
                )
            )
    pending_templates.sort(key=lambda item: (-item[4], item[0], item[3], item[6]))
    return pending_templates
