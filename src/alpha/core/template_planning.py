"""
模板队列构建辅助模块。

承载模板候选解析与 settings 变体展开等可复用逻辑，
避免 executor 模块同时承担流程编排和细粒度队列构建职责。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from ..analysis.feedback_history import choose_settings_variant_budget
from ..analysis.field_stats import decay_field_feedback
from ..config.models import DatasetExpressionPolicy
from ..config.static_config import get_static_config
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
from ..generators.templates.metadata import (
    normalize_activation_scope,
    normalize_template_role,
)
from ..generators.templates.priority import cap_templates_per_family
from ..generators.variants import build_setting_variants
from ..models.domain import (
    SettingsVariant,
    TemplateCandidate,
    TemplateField,
)
from ..models.runtime_options import TemplateBuildOptions
from ..models.runtime_protocols import TemplateFeedback
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage
from ..runtime.contexts import PendingTemplateEntry, TemplateBuildContext
from ..utils.helpers import first_non_empty, is_event_field_name


class ExpressionCandidateBuilder(Protocol):
    """Broad expression candidate generation port."""

    def __call__(
        self,
        field: TemplateField,
        build_ctx: TemplateBuildContext,
        *,
        max_templates_per_field: int,
        max_templates_per_family: int,
        field_feedback: TemplateFeedback | None = None,
        expression_policy: DatasetExpressionPolicy | None = None,
    ) -> list[TemplateCandidate]: ...


class SettingVariantsBuilder(Protocol):
    """Settings variant expansion port."""

    def __call__(
        self,
        args: TemplateBuildOptions,
        template_name: str,
        expression: str,
        *,
        field_feedback: TemplateFeedback | None = None,
    ) -> list[SettingsVariant]: ...


@dataclass(frozen=True)
class TemplatePlanningServices:
    """Typed dependencies used while planning templates and settings variants."""

    build_expression_candidates: ExpressionCandidateBuilder
    build_setting_variants: SettingVariantsBuilder
    build_settings_fingerprint: Callable[[object], str]


def build_template_planning_services() -> TemplatePlanningServices:
    """Resolve current planning dependencies so runtime overrides remain effective."""
    return TemplatePlanningServices(
        build_expression_candidates=build_expression_candidates,
        build_setting_variants=build_setting_variants,
        build_settings_fingerprint=build_settings_fingerprint_from_payload,
    )


def _limit_template_candidates(
    templates: Sequence[TemplateCandidate],
    *,
    max_templates_per_family: int,
    max_templates_per_field: int,
) -> list[TemplateCandidate]:
    """Apply the shared family/field caps after sorting by priority."""
    return limit_templates(
        cap_templates_per_family(
            sort_templates_by_priority(list(templates)),
            max_templates_per_family,
        ),
        max_templates_per_field,
    )


def _resolve_field_planning_policy(
    build_ctx: TemplateBuildContext,
    field: TemplateField,
) -> tuple[str, str, TemplateFeedback | None, DatasetExpressionPolicy]:
    """Resolve the stable policy inputs shared by candidate and variant planning."""
    options = build_ctx.source.options
    field_id = str(first_non_empty(field.field_id, get_static_config().sentinel_unknown))
    field_name = choose_field_name(field)
    expression_policy = build_ctx.source.expression_policy or get_dataset_expression_policy(
        options.dataset_id,
        default_backfill_window=options.backfill_window,
    )
    field_feedback = decay_field_feedback(
        build_ctx.feedback.field_feedback.get(field_id),
        half_life_days=expression_policy.field_feedback_half_life_days,
    )
    return field_id, field_name, field_feedback, expression_policy


def _resolve_template_limits(
    *,
    field_name: str,
    options: TemplateBuildOptions,
    expression_policy: DatasetExpressionPolicy,
) -> tuple[int, int]:
    """Resolve the effective field/family template caps for one field."""
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
    return max_templates_per_field, max_templates_per_family


def _resolve_feedback_stage(
    field_feedback: TemplateFeedback | None,
    expression_policy: DatasetExpressionPolicy,
) -> str:
    """Resolve the feedback stage using the active dataset expression policy."""
    return resolve_feedback_stage(
        field_feedback,
        expression_policy.feedback_loop_policy,
    )


def resolve_field_template_candidates(
    build_ctx: TemplateBuildContext,
    field: TemplateField,
    *,
    services: TemplatePlanningServices | None = None,
) -> tuple[list[TemplateCandidate], TemplateFeedback, DatasetExpressionPolicy]:
    """为单个字段解析模板候选、字段反馈和表达式策略。"""
    active_services = services or build_template_planning_services()
    options = build_ctx.source.options
    _field_id, field_name, field_feedback, expression_policy = _resolve_field_planning_policy(
        build_ctx,
        field,
    )
    max_templates_per_field, max_templates_per_family = _resolve_template_limits(
        field_name=field_name,
        options=options,
        expression_policy=expression_policy,
    )
    is_exploration = not field_feedback and not options.preset_mode
    build_max_templates_per_field = 0 if is_exploration else max_templates_per_field
    build_max_templates_per_family = 0 if is_exploration else max_templates_per_family
    templates = active_services.build_expression_candidates(
        field,
        build_ctx,
        max_templates_per_field=build_max_templates_per_field,
        max_templates_per_family=build_max_templates_per_family,
        field_feedback=field_feedback,
        expression_policy=expression_policy,
    )
    templates = _limit_template_candidates(
        templates,
        max_templates_per_family=build_max_templates_per_family,
        max_templates_per_field=build_max_templates_per_field,
    )
    return templates, field_feedback or {}, expression_policy


def build_pending_template_variants(
    build_ctx: TemplateBuildContext,
    field: TemplateField,
    *,
    templates: Sequence[TemplateCandidate],
    attempted_keys: set[tuple[str, str, str, str]],
    reserved_keys: set[tuple[str, str, str, str]],
    field_feedback: TemplateFeedback | None,
    services: TemplatePlanningServices | None = None,
) -> list[PendingTemplateEntry]:
    """把模板候选展开为真正待执行的 settings 变体队列。"""
    active_services = services or build_template_planning_services()
    options = build_ctx.source.options
    field_id, _field_name, _policy_feedback, expression_policy = _resolve_field_planning_policy(
        build_ctx,
        field,
    )
    pending_templates: list[PendingTemplateEntry] = []
    all_reserved_keys = attempted_keys | reserved_keys
    reserved_expression_variant_keys = {
        (reserved_field_id, reserved_expression, reserved_variant_fingerprint)
        for reserved_field_id, _reserved_template_name, reserved_expression, reserved_variant_fingerprint in all_reserved_keys
    }
    seen_expression_variant_keys: set[tuple[str, str, str]] = set()
    seen_resimulate_expressions: set[tuple[str, str]] = set()
    max_setting_variants = (
        1
        if build_ctx.source.options.preset_mode
        else choose_settings_variant_budget(
            field_feedback,
            expression_policy=expression_policy,
        )
    )
    feedback_stage = _resolve_feedback_stage(field_feedback, expression_policy)
    for template in templates:
        template_name = template.name
        expression = template.expression
        priority = template.priority
        template_metadata = template.metadata
        expression_key = (field_id, expression)
        if (
            feedback_stage == get_static_config().feedback_stage_resimulate
            and expression_key in seen_resimulate_expressions
        ):
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
        template_role = normalize_template_role(template_metadata.get("role"))
        template_activation_scope = normalize_activation_scope(
            template_metadata.get("activation_scope")
        )
        appended_expression_variant = False
        for settings_variant in active_services.build_setting_variants(
            options,
            template_name,
            expression,
            field_feedback=field_feedback,
        )[: max(1, int(max_setting_variants or 1))]:
            variant_fingerprint = active_services.build_settings_fingerprint(settings_variant)
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
                    template_role=template_role,
                    template_activation_scope=template_activation_scope,
                    policy_version=str(template_metadata.get("policy_version", "")),
                    expression=expression,
                    priority=priority,
                    settings_variant=settings_variant,
                    variant_fingerprint=variant_fingerprint,
                )
            )
            appended_expression_variant = True
        if (
            feedback_stage == get_static_config().feedback_stage_resimulate
            and appended_expression_variant
        ):
            seen_resimulate_expressions.add(expression_key)
    pending_templates.sort(
        key=lambda item: (
            -item.priority,
            item.template_name,
            item.expression,
            item.variant_fingerprint,
        )
    )
    return pending_templates
