"""Ratio template generation helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config.constants import (
    ALLOWED_EXTERNAL_RATIO_PARTNERS,
    DELTA_STD_PRIORITY_BOOST,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
)
from ..config.getters import get_backfill_window
from ..config.models import DatasetExpressionPolicy
from ..generators.field_transforms import build_field_view, build_ratio_expression
from ..models.domain import FieldView, TemplateCandidate
from ..models.runtime import TemplateField
from ..policy.template_blacklist import (
    is_blacklisted_template as _policy_is_blacklisted_template,
)
from ..utils.helpers import choose_field_name
from .templates.candidates import (
    _candidate_metadata,
    _make_template_candidate,
    _render_template_specs,
)
from .templates.classification import classify_expression_family, classify_template_stage
from .templates.partner_fields import discover_partner_fields


def _is_blacklisted_template(
    template_name: str,
    expression: str = "",
    *,
    template_metadata: dict[str, Any] | None = None,
    policy: DatasetExpressionPolicy | None = None,
) -> bool:
    """判断 ratio 模板是否命中黑名单。"""
    return _policy_is_blacklisted_template(
        template_name,
        expression,
        template_metadata=template_metadata,
        policy=policy,
        current_family=classify_expression_family(template_name, expression, template_metadata),
        current_stage=classify_template_stage(template_name, expression, template_metadata),
    )


def build_high_conviction_ratio_templates(
    ratio_expr: str,
    ratio_label: str,
    *,
    priority_boost: int = 0,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> list[TemplateCandidate]:
    """为财务含义强的 ratio pair 生成专属长窗质量模板。"""
    bw = get_backfill_window()
    specs: tuple[tuple[str, str, int, str, str], ...] = (
        (
            "hc_ratio_group_level_{ratio_label}",
            "group_rank({ratio_expr}, subindustry)",
            228,
            "high_conviction_ratio",
            TEMPLATE_STAGE_GROUP_SECOND_ORDER,
        ),
        (
            "hc_ratio_group_zscore_252_{ratio_label}",
            "group_rank(ts_zscore({ratio_expr}, 252), subindustry)",
            226,
            "high_conviction_ratio",
            TEMPLATE_STAGE_GROUP_SECOND_ORDER,
        ),
        (
            "hc_ratio_decay_zscore_252_{ratio_label}",
            "ts_decay_linear(group_rank(ts_zscore({ratio_expr}, 252), subindustry), 20)",
            224,
            "high_conviction_ratio",
            TEMPLATE_STAGE_GROUP_SECOND_ORDER,
        ),
        (
            "hc_ratio_industry_zscore_252_{ratio_label}",
            "group_rank(ts_zscore({ratio_expr}, 252), industry)",
            222,
            "high_conviction_ratio",
            TEMPLATE_STAGE_GROUP_SECOND_ORDER,
        ),
    )
    templates: list[TemplateCandidate] = []
    for name_template, expr_template, priority, family, stage in specs:
        name = name_template.format(ratio_label=ratio_label)
        expr = expr_template.format(ratio_expr=ratio_expr, backfill_window=bw)
        template = _make_template_candidate(
            name,
            expr,
            priority + priority_boost,
            metadata=_candidate_metadata(
                family=family,
                layer="group",
                stage=stage,
                requires_partner_field=True,
            ),
        )
        if not _is_blacklisted_template(
            template.name,
            template.expression,
            template_metadata=template.metadata,
            policy=expression_policy,
        ):
            templates.append(template)
    return templates


def extend_ratio_templates(
    diversified: list[TemplateCandidate],
    legacy: list[TemplateCandidate],
    field_view: FieldView,
    all_fields: Sequence[TemplateField],
    expression_policy: DatasetExpressionPolicy,
    backfill_window: int,
) -> None:
    """根据字段配对扩展 ratio 模板。"""
    field_name = field_view.field_name
    preprocessed_expression = field_view.preprocessed_expression
    fields_by_name = {choose_field_name(item): item for item in all_fields}
    partner_names = discover_partner_fields(
        field_name,
        all_fields,
        expression_policy,
        limit=expression_policy.partner_limit,
    )

    for partner in partner_names:
        if partner not in fields_by_name and partner not in ALLOWED_EXTERNAL_RATIO_PARTNERS:
            continue
        denominator_view = (
            build_field_view(fields_by_name[partner], expression_policy)
            if partner in fields_by_name
            else None
        )
        ratio_expr = (
            build_ratio_expression(field_view, denominator_view)
            if denominator_view is not None
            else f"{field_view.ratio_numerator_expression}/{partner}"
        )
        ratio_label = f"{field_name}_over_{partner}"
        ratio_priority_boost = _extend_high_conviction_templates(
            diversified,
            field_name,
            partner,
            ratio_expr,
            ratio_label,
            expression_policy,
        )

        _extend_ratio_delta_rank_templates(
            diversified,
            ratio_expr,
            ratio_label,
            ratio_priority_boost,
            expression_policy,
        )
        _extend_ratio_delta_over_std_templates(
            diversified,
            ratio_expr,
            ratio_label,
            ratio_priority_boost,
            expression_policy,
        )
        _extend_rendered_ratio_templates(
            diversified,
            legacy,
            ratio_expr,
            ratio_label,
            preprocessed_expression,
            ratio_priority_boost,
            expression_policy,
            backfill_window,
        )


def _extend_high_conviction_templates(
    diversified: list[TemplateCandidate],
    field_name: str,
    partner: str,
    ratio_expr: str,
    ratio_label: str,
    expression_policy: DatasetExpressionPolicy,
) -> int:
    """扩展高信心 ratio 模板并返回优先级提升值。"""
    if (field_name, partner) not in expression_policy.high_conviction_ratio_pairs:
        return 0
    ratio_priority_boost = expression_policy.high_conviction_ratio_priority_boost
    diversified.extend(
        build_high_conviction_ratio_templates(
            ratio_expr,
            ratio_label,
            priority_boost=ratio_priority_boost,
            expression_policy=expression_policy,
        )
    )
    return ratio_priority_boost


def _extend_ratio_delta_rank_templates(
    diversified: list[TemplateCandidate],
    ratio_expr: str,
    ratio_label: str,
    ratio_priority_boost: int,
    expression_policy: DatasetExpressionPolicy,
) -> None:
    """扩展 ratio delta-rank 模板。"""
    for delta, pri in expression_policy.ratio_delta_rank_windows:
        name = f"group_ratio_delta_rank_{delta}_{ratio_label}"
        expr = f"group_rank(ts_delta(rank({ratio_expr}), {delta}), subindustry)"
        if not _is_blacklisted_template(name, expr, policy=expression_policy):
            diversified.append(
                _make_template_candidate(
                    name,
                    expr,
                    pri + DELTA_STD_PRIORITY_BOOST + ratio_priority_boost,
                    metadata=_candidate_metadata(
                        family="group_ratio_level",
                        layer="group",
                        stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                        requires_partner_field=True,
                    ),
                )
            )


def _extend_ratio_delta_over_std_templates(
    diversified: list[TemplateCandidate],
    ratio_expr: str,
    ratio_label: str,
    ratio_priority_boost: int,
    expression_policy: DatasetExpressionPolicy,
) -> None:
    """扩展 ratio delta/std 模板。"""
    for delta, std, pri in expression_policy.ratio_delta_over_std_windows:
        diversified.append(
            _make_template_candidate(
                f"group_ratio_delta_over_std_{delta}_{std}_{ratio_label}",
                f"group_rank(ts_delta({ratio_expr}, {delta}) / ts_std_dev({ratio_expr}, {std}), subindustry)",
                pri + DELTA_STD_PRIORITY_BOOST + ratio_priority_boost,
                metadata=_candidate_metadata(
                    family="group_vol_scaled_delta",
                    layer="group",
                    stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                    requires_partner_field=True,
                ),
            )
        )


def _extend_rendered_ratio_templates(
    diversified: list[TemplateCandidate],
    legacy: list[TemplateCandidate],
    ratio_expr: str,
    ratio_label: str,
    preprocessed_expression: str,
    ratio_priority_boost: int,
    expression_policy: DatasetExpressionPolicy,
    backfill_window: int,
) -> None:
    """扩展 JSON spec 渲染出来的 ratio 多样化和 legacy 模板。"""
    diversified.extend(
        [
            _make_template_candidate(
                candidate.name,
                candidate.expression,
                candidate.priority + ratio_priority_boost,
                metadata={
                    **candidate.metadata,
                    "requires_partner_field": True,
                },
            )
            for candidate in _render_template_specs(
                expression_policy.ratio_diversified_template_specs,
                ratio_expr=ratio_expr,
                ratio_label=ratio_label,
                field_preprocessed=preprocessed_expression,
                backfill_window=backfill_window,
            )
        ]
    )

    legacy.extend(
        [
            _make_template_candidate(
                candidate.name,
                candidate.expression,
                candidate.priority + ratio_priority_boost,
                metadata={
                    **candidate.metadata,
                    "requires_partner_field": True,
                },
            )
            for candidate in _render_template_specs(
                expression_policy.ratio_legacy_template_specs,
                ratio_expr=ratio_expr,
                ratio_label=ratio_label,
                field_preprocessed=preprocessed_expression,
                backfill_window=backfill_window,
            )
        ]
    )
