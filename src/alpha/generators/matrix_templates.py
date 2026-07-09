"""
MATRIX field template generation.

MATRIX 字段模板生成模块。

This module keeps field-level diversified, ratio, bucket, trade_when, and
legacy MATRIX template construction out of the generic expression builder.

本模块把 MATRIX 字段的多样化、ratio、bucket、trade_when 和 legacy 模板构建
从通用表达式编排流程中拆出，降低主流程复杂度。
"""

from __future__ import annotations

from collections.abc import Sequence

from ..config.constants import (
    DELTA_STD_PRIORITY_BOOST,
    LEGACY_MATRIX_GROUP_RANK_INDUSTRY_PRIORITY,
    LEGACY_MATRIX_GROUP_RANK_SUBINDUSTRY_PRIORITY,
    LEGACY_MATRIX_NEG_DEFAULT_PRIORITY,
    LEGACY_MATRIX_NEG_NEGATIVE_RAW_PRIORITY,
    LEGACY_MATRIX_NEG_POSITIVE_RAW_PRIORITY,
    LEGACY_MATRIX_RANK_RAW_FIELD_PRIORITY,
    LEGACY_MATRIX_RAW_FIELD_PRIORITY,
    TEMPLATE_STAGE_FIRST_ORDER,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
)
from ..config.models import DatasetExpressionPolicy
from ..config.runtime_values import get_runtime_config
from ..models.domain import FieldView, TemplateCandidate, TemplateField
from .ratio_templates import extend_ratio_templates
from .templates.candidates import (
    _candidate_metadata,
    _make_template_candidate,
    _render_template_specs,
)
from .templates.variations import build_bucket_group_templates, build_trade_when_templates


def build_matrix_templates(
    field_view: FieldView,
    all_fields: Sequence[TemplateField],
    expression_policy: DatasetExpressionPolicy,
) -> tuple[list[TemplateCandidate], list[TemplateCandidate]]:
    """为 MATRIX 类型字段构建多样化和 legacy 模板候选。"""
    field_name = field_view.field_name
    preprocessed_expression = field_view.preprocessed_expression
    default_backfill_window = get_runtime_config().expression.backfill_window
    backfill_window = expression_policy.matrix_field_transform.backfill_window or default_backfill_window

    diversified: list[TemplateCandidate] = []
    for delta, std, pri in expression_policy.matrix_delta_over_std_windows:
        diversified.append(
            _make_template_candidate(
                f"group_delta_over_std_subindustry_{delta}_{std}",
                f"group_rank(ts_delta({preprocessed_expression}, {delta}) / ts_std_dev({preprocessed_expression}, {std}), subindustry)",
                pri + DELTA_STD_PRIORITY_BOOST,
                metadata=_candidate_metadata(
                    family="group_vol_scaled_delta",
                    layer="group",
                    stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
                ),
            )
        )

    diversified.extend(
        [
            _make_template_candidate(
                candidate.name,
                candidate.expression,
                candidate.priority + DELTA_STD_PRIORITY_BOOST
                if "delta_over_std" in candidate.name
                else candidate.priority,
                metadata=candidate.metadata,
            )
            for candidate in _render_template_specs(
                expression_policy.matrix_diversified_template_specs,
                field=field_name,
                field_preprocessed=preprocessed_expression,
                backfill_window=backfill_window,
            )
        ]
    )
    diversified.extend(build_bucket_group_templates(preprocessed_expression, name_prefix="bucket"))
    diversified.extend(
        build_trade_when_templates(
            f"rank({preprocessed_expression})",
            name_prefix="event",
        )
    )

    legacy = _build_legacy_matrix_templates(field_name, preprocessed_expression, expression_policy)
    extend_ratio_templates(
        diversified,
        legacy,
        field_view,
        all_fields,
        expression_policy,
        backfill_window,
    )
    return diversified, legacy


def _build_legacy_matrix_templates(
    field_name: str,
    preprocessed_expression: str,
    expression_policy: DatasetExpressionPolicy,
) -> list[TemplateCandidate]:
    """构建 MATRIX 字段的基础 legacy 模板。"""
    legacy: list[TemplateCandidate] = [
        _make_template_candidate(
            "raw_field",
            preprocessed_expression,
            LEGACY_MATRIX_RAW_FIELD_PRIORITY,
            metadata=_candidate_metadata(
                family="legacy_level",
                layer="first_order",
                stage=TEMPLATE_STAGE_FIRST_ORDER,
            ),
        ),
        _make_template_candidate(
            "group_rank_subindustry",
            f"group_rank({preprocessed_expression}, subindustry)",
            LEGACY_MATRIX_GROUP_RANK_SUBINDUSTRY_PRIORITY,
            metadata=_candidate_metadata(
                family="legacy_group_level",
                layer="group",
                stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
            ),
        ),
        _make_template_candidate(
            "group_rank_industry",
            f"group_rank({preprocessed_expression}, industry)",
            LEGACY_MATRIX_GROUP_RANK_INDUSTRY_PRIORITY,
            metadata=_candidate_metadata(
                family="legacy_group_level",
                layer="group",
                stage=TEMPLATE_STAGE_GROUP_SECOND_ORDER,
            ),
        ),
        _make_template_candidate(
            "rank_raw_field",
            f"rank({preprocessed_expression})",
            LEGACY_MATRIX_RANK_RAW_FIELD_PRIORITY,
            metadata=_candidate_metadata(
                family="legacy_level",
                layer="first_order",
                stage=TEMPLATE_STAGE_FIRST_ORDER,
            ),
        ),
    ]
    if expression_policy.use_curated_heuristics and field_name in expression_policy.positive_raw_fields:
        priority = LEGACY_MATRIX_NEG_POSITIVE_RAW_PRIORITY
    elif expression_policy.use_curated_heuristics and field_name in expression_policy.negative_raw_fields:
        priority = LEGACY_MATRIX_NEG_NEGATIVE_RAW_PRIORITY
    elif expression_policy.use_curated_heuristics:
        priority = LEGACY_MATRIX_NEG_DEFAULT_PRIORITY
    else:
        return legacy

    legacy.append(
        _make_template_candidate(
            "neg_raw_field",
            f"-{preprocessed_expression}",
            priority,
            metadata=_candidate_metadata(
                family="legacy_level",
                layer="first_order",
                stage=TEMPLATE_STAGE_FIRST_ORDER,
            ),
        )
    )
    return legacy
