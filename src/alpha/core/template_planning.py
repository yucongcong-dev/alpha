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
from ..analysis.template_registry_budget import (
    choose_field_cluster_settings_budget,
    choose_family_settings_budget,
    choose_registry_settings_budget,
)
from ..analysis.template_registry_rules import (
    normalize_activation_scope,
    normalize_template_role,
    recommend_template_role_transition,
)
from ..analysis.template_registry_store import resolve_registry_override
from ..analysis.template_stats import historical_template_priority_bonus
from ..config.constants import (
    FEEDBACK_STAGE_RESIMULATE,
    SENTINEL_UNKNOWN,
)
from ..config.models import DatasetExpressionPolicy
from ..generators.expression_builder import (
    build_expression_candidates,
    limit_templates,
    sort_templates_by_priority,
)
from ..generators.fields import choose_field_name
from ..generators.payload import build_settings_fingerprint_from_payload
from ..generators.templates.classification import (
    classify_expression_family,
    classify_template_stage,
)
from ..generators.templates.priority import cap_templates_per_family
from ..generators.templates.refine import build_refine_templates
from ..generators.variants import build_setting_variants
from ..models.domain import (
    FieldTestResult,
    NearPassCandidate,
    TemplateCandidate,
    TemplateField,
)
from ..models.domain_parsers import parse_failed_check
from ..models.runtime_protocols import TemplateFeedback
from ..runtime import PendingTemplateEntry, TemplateBuildContext
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage
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
            build_ctx,
            max_templates_per_field=max_templates_per_field,
            max_templates_per_family=max_templates_per_family,
            field_feedback=field_feedback,
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
) -> list[PendingTemplateEntry]:
    """把模板候选展开为真正待执行的 settings 变体队列。"""
    options = build_ctx.options
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
    field_name = choose_field_name(field)
    pending_templates: list[PendingTemplateEntry] = []
    all_reserved_keys = attempted_keys | reserved_keys
    reserved_expression_variant_keys = {
        (reserved_field_id, reserved_expression, reserved_variant_fingerprint)
        for reserved_field_id, _reserved_template_name, reserved_expression, reserved_variant_fingerprint in all_reserved_keys
    }
    seen_expression_variant_keys: set[tuple[str, str, str]] = set()
    seen_resimulate_expressions: set[tuple[str, str]] = set()
    max_setting_variants = choose_settings_variant_budget(
        field_feedback,
        expression_policy=build_ctx.expression_policy,
    )
    feedback_stage = resolve_feedback_stage(
        field_feedback,
        (build_ctx.expression_policy or get_dataset_expression_policy(options.dataset_id)).feedback_loop_policy,
    )
    for template in templates:
        template_name = template.name
        expression = template.expression
        priority = template.priority
        template_metadata = template.metadata
        expression_key = (field_id, expression)
        if feedback_stage == FEEDBACK_STAGE_RESIMULATE and expression_key in seen_resimulate_expressions:
            continue
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
        manual_override = resolve_registry_override(
            build_ctx.template_registry_overrides,
            template_name=template_name,
            template_family=template_family,
        )
        persisted_registry_entry = build_ctx.template_registry.get(template_name, {})
        template_role = normalize_template_role(
            manual_override.get("recommended_role")
            or persisted_registry_entry.get("recommended_role")
            or template_metadata.get("role")
        )
        template_activation_scope = normalize_activation_scope(
            manual_override.get("recommended_scope")
            or persisted_registry_entry.get("recommended_scope")
            or template_metadata.get("activation_scope")
        )
        role_recommendation = recommend_template_role_transition(
            template_name,
            template_stats,
            current_role=template_role,
            current_scope=template_activation_scope,
            feedback_stage=feedback_stage,
        )
        if manual_override:
            role_recommendation.update(
                recommended_role=normalize_template_role(
                    manual_override.get("recommended_role") or role_recommendation["recommended_role"]
                ),
                recommended_scope=normalize_activation_scope(
                    manual_override.get("recommended_scope") or role_recommendation["recommended_scope"]
                ),
                priority_adjustment=int(
                    manual_override.get("priority_adjustment", role_recommendation["priority_adjustment"]) or 0
                ),
                should_suppress=bool(
                    manual_override.get("should_suppress", role_recommendation["should_suppress"])
                ),
                reason=str(manual_override.get("reason", role_recommendation["reason"]) or ""),
            )
        if role_recommendation["should_suppress"]:
            continue
        recommended_role = normalize_template_role(role_recommendation["recommended_role"])
        recommended_scope = normalize_activation_scope(role_recommendation["recommended_scope"])
        template_metadata["registry_recommended_role"] = recommended_role
        template_metadata["registry_recommended_scope"] = recommended_scope
        template_metadata["registry_reason"] = role_recommendation["reason"]
        effective_priority = priority + historical_template_priority_bonus(
            template_name, template_stats
        ) + int(role_recommendation["priority_adjustment"])
        effective_variant_budget = choose_registry_settings_budget(
            max_setting_variants,
            role_recommendation,
            feedback_stage=feedback_stage,
        )
        effective_variant_budget = choose_family_settings_budget(
            effective_variant_budget,
            template_family,
            build_ctx.template_family_registry,
            feedback_stage=feedback_stage,
        )
        effective_variant_budget = choose_field_cluster_settings_budget(
            effective_variant_budget,
            field.get("runtime_field_tags", []),
            build_ctx.template_registry_overrides,
            feedback_stage=feedback_stage,
        )
        if effective_variant_budget <= 0:
            continue
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
                failed_checks=[parse_failed_check(check) for check in refine_failed_checks],
            )
        for settings_variant in build_setting_variants_fn(
            options,
            template_name,
            expression,
            field_feedback=field_feedback,
            refine_candidate=refine_candidate,
        )[:effective_variant_budget]:
            variant_fingerprint = build_settings_fingerprint_fn(settings_variant)
            expression_variant_key = (field_id, expression, variant_fingerprint)
            if expression_variant_key in reserved_expression_variant_keys:
                continue
            if expression_variant_key in seen_expression_variant_keys:
                continue
            if (field_id, template_name, expression, variant_fingerprint) in all_reserved_keys:
                continue
            seen_expression_variant_keys.add(expression_variant_key)
            pending_templates.append(
                PendingTemplateEntry(
                    template_name=template_name,
                    template_family=template_family,
                    template_stage=template_stage,
                    template_role=recommended_role,
                    template_activation_scope=recommended_scope,
                    expression=expression,
                    priority=effective_priority,
                    settings_variant=settings_variant,
                    variant_fingerprint=variant_fingerprint,
                )
            )
            if feedback_stage == FEEDBACK_STAGE_RESIMULATE:
                seen_resimulate_expressions.add(expression_key)
                break
    pending_templates.sort(key=lambda item: (-item.priority, item.template_name, item.expression, item.variant_fingerprint))
    return pending_templates
