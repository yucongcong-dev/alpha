"""字段预处理与字段视图构建。"""

from __future__ import annotations

from typing import Any

from ..config import DatasetExpressionPolicy, FieldTransformSpec
from ..models.base import FieldView
from ..utils.helpers import choose_field_name, choose_field_type


def apply_transform_pipeline(expression: str, transform_spec: FieldTransformSpec) -> str:
    """按配置顺序应用字段级预处理。"""
    output = expression
    if transform_spec.backfill_window > 0:
        output = f"ts_backfill({output}, {transform_spec.backfill_window})"
    if transform_spec.winsorize_std is not None:
        winsorize_std = transform_spec.winsorize_std
        output = f"winsorize({output}, std={winsorize_std:g})"
    return output


def build_field_view(
    field: dict[str, Any],
    policy: DatasetExpressionPolicy,
) -> FieldView:
    """为字段构建统一视图。"""
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)

    if field_type == "VECTOR":
        raw_expression = f"vec_avg({field_name})"
        transform_spec = policy.vector_field_transform
    elif field_type == "MATRIX":
        raw_expression = field_name
        transform_spec = policy.matrix_field_transform
    else:
        raw_expression = field_name
        transform_spec = policy.default_field_transform

    preprocessed_expression = apply_transform_pipeline(raw_expression, transform_spec)
    ratio_numerator_expression = apply_transform_pipeline(
        raw_expression,
        policy.ratio_numerator_transform,
    )
    ratio_denominator_expression = apply_transform_pipeline(
        raw_expression,
        policy.ratio_denominator_transform,
    )

    return FieldView(
        field_id=str(field.get("id", field_name)),
        field_name=field_name,
        field_type=field_type,
        raw_expression=raw_expression,
        preprocessed_expression=preprocessed_expression,
        ratio_numerator_expression=ratio_numerator_expression,
        ratio_denominator_expression=ratio_denominator_expression,
        metadata=dict(field),
    )


def build_ratio_expression(numerator: FieldView, denominator: FieldView) -> str:
    """构建使用统一预处理视图的比率表达式。"""
    return f"{numerator.ratio_numerator_expression}/{denominator.ratio_denominator_expression}"
