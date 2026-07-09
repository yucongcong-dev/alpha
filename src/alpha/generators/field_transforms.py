"""字段预处理与字段视图构建。"""

from __future__ import annotations

from typing import Any

from ..config.models import DatasetExpressionPolicy, FieldTransformSpec, FieldTransformStage
from ..models.domain import FieldView, TemplateField
from ..models.domain_parsers import parse_template_field
from .fields import choose_field_name, choose_field_type


def iter_transform_stages(transform_spec: FieldTransformSpec) -> tuple[FieldTransformStage, ...]:
    """返回字段预处理的 stage 列表，兼容旧 backfill/winsorize 配置。"""
    if transform_spec.stages:
        return transform_spec.stages
    stages: list[FieldTransformStage] = []
    if transform_spec.backfill_window > 0:
        stages.append(FieldTransformStage(kind="backfill", window=transform_spec.backfill_window))
    if transform_spec.winsorize_std is not None:
        stages.append(FieldTransformStage(kind="winsorize", std=transform_spec.winsorize_std))
    return tuple(stages)


def apply_transform_stage(expression: str, stage: FieldTransformStage) -> str:
    """应用单个字段预处理 stage。"""
    if stage.kind == "backfill" and stage.window > 0:
        return f"ts_backfill({expression}, {stage.window})"
    if stage.kind == "winsorize" and stage.std is not None:
        return f"winsorize({expression}, std={stage.std:g})"
    return expression


def apply_transform_pipeline(expression: str, transform_spec: FieldTransformSpec) -> str:
    """按配置顺序应用字段级预处理。"""
    output = expression
    for stage in iter_transform_stages(transform_spec):
        output = apply_transform_stage(output, stage)
    return output


def build_field_view(
    field: TemplateField | dict[str, Any],
    policy: DatasetExpressionPolicy,
) -> FieldView:
    """为字段构建统一视图。"""
    if isinstance(field, dict):
        field = parse_template_field(field)
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)

    if field_type == "VECTOR":
        # vec_avg() 将整个 VECTOR 时间序列压缩为标量，丢弃了所有时序结构。
        # 对日频 VECTOR 字段（如 model51 风险指标），后续 ts_delta / ts_zscore 会失效。
        # 当前保守使用 vec_avg()；如果后续要探索 VECTOR 内部分量，应新增显式模板
        # 使用 vec_select_nth()，避免在通用字段视图里隐式改变所有 VECTOR 行为。
        raw_expression = f"vec_avg({field_name})"
        transform_spec = policy.vector_field_transform
    elif field_type == "MATRIX":
        raw_expression = field_name
        transform_spec = policy.matrix_field_transform
    else:
        raw_expression = field_name
        transform_spec = policy.default_field_transform

    preprocessed_expression = apply_transform_pipeline(raw_expression, transform_spec)
    groupfill_expression = f"group_backfill({raw_expression}, subindustry, 252, std=4)"
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
        groupfill_expression=groupfill_expression,
        ratio_numerator_expression=ratio_numerator_expression,
        ratio_denominator_expression=ratio_denominator_expression,
        metadata=field.metadata,
    )


def build_ratio_expression(numerator: FieldView, denominator: FieldView) -> str:
    """构建使用统一预处理视图的比率表达式。"""
    return f"{numerator.ratio_numerator_expression}/{denominator.ratio_denominator_expression}"
