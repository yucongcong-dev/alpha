"""
模板结构分类逻辑。

本模块负责把模板/表达式归类到结构家族和执行阶段，供排序、
黑名单匹配和自适应优先级调整复用。
"""

from __future__ import annotations

from ...config import (
    TEMPLATE_STAGE_EVENT_CONDITIONED,
    TEMPLATE_STAGE_FIRST_ORDER,
    TEMPLATE_STAGE_GROUP_SECOND_ORDER,
    UNKNOWN_FAMILY,
)
from ...models.domain_types import TemplateMetadata


def classify_expression_family(
    template_name: str,
    expression: str,
    metadata: TemplateMetadata | None = None,
) -> str:
    """
    将表达式归类到粗粒度家族，用于剪枝与排序。

    Args:
        template_name: 模板名称。
        expression: 表达式字符串。
        metadata: 可选模板元数据。存在 explicit family 时优先使用。

    Returns:
        str: 表达式结构家族名称。
    """
    if metadata:
        explicit_family = metadata.get("family")
        if isinstance(explicit_family, str) and explicit_family.strip():
            return explicit_family.strip().lower()
    lower_name = template_name.lower()
    lower_expr = expression.lower()
    if "group_rank(ts_delta(rank(" in lower_expr:
        return "group_rank_delta"
    if "rank(ts_delta(rank(" in lower_expr:
        return "rank_delta"
    if lower_name in {"raw_field", "neg_raw_field", "rank_raw_field"}:
        return "legacy_level"
    if lower_name.startswith(("raw_ratio_", "ratio_", "rank_ratio_")):
        return "legacy_ratio"
    if lower_name.startswith("neg_ratio_"):
        return "legacy_neg_ratio"
    if lower_name.startswith("group_rank_ratio_"):
        return "group_ratio_level"
    if lower_name.startswith("group_rank_") or "group_rank(" in lower_expr:
        if "ts_zscore" in lower_expr:
            return "group_zscore"
        if "ts_delta" in lower_expr and "ts_std_dev" in lower_expr:
            return "group_vol_scaled_delta"
        if "ts_mean" in lower_expr and "-" in lower_expr:
            return "group_mean_spread"
        return "legacy_group_level"
    if "group_neutralize" in lower_expr and "ts_decay_linear" in lower_expr:
        return "neutralize_decay"
    if "ts_decay_linear" in lower_expr and "ts_delta" not in lower_expr and "/" not in lower_expr:
        return "decay_level"
    if "ts_rank" in lower_expr:
        return "ts_rank"
    if "ts_delta" in lower_expr and "ts_std_dev" in lower_expr:
        return "vol_scaled_delta"
    if "ts_mean" in lower_expr and "-" in lower_expr:
        return "mean_spread"
    if "ts_rank" in lower_expr and "-" in lower_expr:
        return "rank_spread"
    if "ts_zscore" in lower_expr:
        return "zscore_time"
    if "ts_decay_linear" in lower_expr and "ts_delta" in lower_expr:
        return "decayed_delta"
    if "/" in lower_expr and "ts_decay_linear" in lower_expr:
        return "decayed_ratio"
    if "ts_mean" in lower_expr and "/" in lower_expr:
        return "mean_ratio"
    prefix = lower_name.split("_", 1)[0]
    return prefix or UNKNOWN_FAMILY


def classify_template_stage(
    template_name: str,
    expression: str,
    metadata: TemplateMetadata | None = None,
) -> str:
    """
    将模板归类到 first_order / group_second_order / event_conditioned 三层。

    Args:
        template_name: 模板名称。
        expression: 表达式字符串。
        metadata: 可选模板元数据。存在 explicit stage 时优先使用。

    Returns:
        str: 模板阶段名称。
    """
    if metadata:
        explicit_stage = str(metadata.get("stage", "")).strip().lower()
        if explicit_stage:
            return explicit_stage
        layer = str(metadata.get("layer", "")).strip().lower()
        if layer in {"group", "composite", "set", "account"}:
            return TEMPLATE_STAGE_GROUP_SECOND_ORDER
        if "event" in layer:
            return TEMPLATE_STAGE_EVENT_CONDITIONED
    lower_name = template_name.lower()
    lower_expr = expression.lower()
    if "event" in lower_name or "event" in lower_expr:
        return TEMPLATE_STAGE_EVENT_CONDITIONED
    family = classify_expression_family(template_name, expression, metadata)
    if family in {
        "group_rank_delta",
        "group_vol_scaled_delta",
        "group_mean_spread",
        "group_zscore",
        "group_ratio_level",
        "legacy_group_level",
        "neutralize_decay",
    }:
        return TEMPLATE_STAGE_GROUP_SECOND_ORDER
    if "group_rank(" in lower_expr or "group_neutralize(" in lower_expr:
        return TEMPLATE_STAGE_GROUP_SECOND_ORDER
    return TEMPLATE_STAGE_FIRST_ORDER


def is_legacy_family(
    template_name: str,
    expression: str,
    metadata: TemplateMetadata | None = None,
) -> bool:
    """
    判断模板是否属于历史上较易过度使用的 legacy 家族。

    Args:
        template_name: 模板名称。
        expression: 表达式字符串。
        metadata: 可选模板元数据。

    Returns:
        bool: 属于 legacy 家族返回 True，否则返回 False。
    """
    return classify_expression_family(template_name, expression, metadata) in {
        "legacy_level",
        "legacy_group_level",
        "legacy_ratio",
        "legacy_neg_ratio",
        "group_ratio_level",
    }
