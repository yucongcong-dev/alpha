"""
模板优先级与剪枝策略。

本模块负责候选模板排序前后的优先级调整、相似度惩罚和 family 级
数量限制，让 expressions.py 专注于表达式候选的构建流程。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ...config import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    CHECK_LOW_TURNOVER,
    DOMINANT_FAILED_CHECK_LIMIT,
    EXPR_ITER_BOOST_THRESHOLD,
    EXPR_NEARPASS_BOOST_THRESHOLD,
    EXPR_RATIO_PENALTY_THRESHOLD,
    PRIORITY_ADJ_ACCOUNT_TEMPLATES,
    PRIORITY_ADJ_DELTA_HIGH_TURNOVER,
    PRIORITY_ADJ_DELTA_LOW_FITNESS,
    PRIORITY_ADJ_DELTA_LOW_TURNOVER,
    PRIORITY_ADJ_GROUP_CONCENTRATED,
    PRIORITY_ADJ_GROUP_LOW_SHARPE,
    PRIORITY_ADJ_HIGH_TURNOVER_CONCENTRATED_RANK_SPREAD,
    PRIORITY_ADJ_HIGH_TURNOVER_CONCENTRATED_ZSCORE_SPREAD,
    PRIORITY_ADJ_ITER_BOOST,
    PRIORITY_ADJ_LEGACY_BASIC_LOW_FITNESS,
    PRIORITY_ADJ_LEGACY_LOW_SHARPE,
    PRIORITY_ADJ_LEGACY_MEAN_SPREAD_LOW_TURNOVER,
    PRIORITY_ADJ_LEGACY_RATIO_CONCENTRATED,
    PRIORITY_ADJ_LEGACY_RATIO_PENALTY,
    PRIORITY_ADJ_NEARPASS_BOOST,
    PRIORITY_ADJ_NEARPASS_GROUP_RANK_DELTA,
    PRIORITY_ADJ_SIGNAL_LOW_SHARPE,
    PRIORITY_ADJ_STABLE_HIGH_TURNOVER,
    PRIORITY_ADJ_VOL_SCALED_CONCENTRATED,
    PRIORITY_ADJ_VOL_SCALED_DELTA_BASE,
    PRIORITY_ADJ_VOL_SCALED_DELTA_CONCENTRATED,
    PRIORITY_ADJ_VOL_SCALED_DELTA_NEARPASS,
    PRIORITY_ADJ_VOL_SCALED_LOW_FITNESS,
    SIMILARITY_PENALTY_OFFSET_GROUP_RATIO_LEVEL,
    SIMILARITY_PENALTY_OFFSET_LEGACY_GROUP_LEVEL,
    SIMILARITY_PENALTY_OFFSET_LEGACY_LEVEL,
    SIMILARITY_PENALTY_OFFSET_LEGACY_NEG_RATIO,
    SIMILARITY_PENALTY_OFFSET_LEGACY_RATIO,
    STATS_DEFAULT_SCORE,
)
from ...models.base import TemplateCandidate
from .candidates import _coerce_template_candidate, _make_template_candidate
from .classification import classify_expression_family
from .metadata import TemplateMetadataMap

_SIMILARITY_PENALTY_OFFSETS: dict[str, int] = {
    "legacy_level": SIMILARITY_PENALTY_OFFSET_LEGACY_LEVEL,
    "legacy_group_level": SIMILARITY_PENALTY_OFFSET_LEGACY_GROUP_LEVEL,
    "legacy_ratio": SIMILARITY_PENALTY_OFFSET_LEGACY_RATIO,
    "legacy_neg_ratio": SIMILARITY_PENALTY_OFFSET_LEGACY_NEG_RATIO,
    "group_ratio_level": SIMILARITY_PENALTY_OFFSET_GROUP_RATIO_LEVEL,
}
"""家族名到相似度惩罚减免值的映射。"""


def apply_similarity_penalty(
    templates: Sequence[TemplateCandidate | tuple[str, str, int]],
    legacy_similarity_penalty: int,
    *,
    metadata_by_key: TemplateMetadataMap | None = None,
) -> list[TemplateCandidate]:
    """
    对 legacy 形态模板施加相似度惩罚，让多样化候选优先运行。

    Args:
        templates: 模板候选列表。
        legacy_similarity_penalty: legacy 家族基础惩罚分数。
        metadata_by_key: 可选模板元数据索引。

    Returns:
        list[TemplateCandidate]: 应用惩罚后的模板候选。
    """
    penalized: list[TemplateCandidate] = []
    for raw_template in templates:
        template = _coerce_template_candidate(raw_template, metadata_by_key=metadata_by_key)
        family = classify_expression_family(
            template.name,
            template.expression,
            template.metadata,
        )
        offset = _SIMILARITY_PENALTY_OFFSETS.get(family)
        penalty = max(legacy_similarity_penalty - offset, 0) if offset is not None else 0
        penalized.append(
            _make_template_candidate(
                template.name,
                template.expression,
                template.priority - penalty,
                metadata=template.metadata,
            )
        )
    return penalized


def dominant_failed_check_names(counts: dict[str, int], limit: int = DOMINANT_FAILED_CHECK_LIMIT) -> set[str]:
    """
    返回失败检查计数最高的若干名称。

    Args:
        counts: 失败检查计数字典。
        limit: 返回的名称数量上限。

    Returns:
        set[str]: 失败检查名称集合。
    """
    return {
        name
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        if count > 0
    }


def merge_failed_check_counts(*count_maps: dict[str, Any]) -> dict[str, int]:
    """
    合并多个失败检查计数字典。

    Args:
        *count_maps: 可变数量的失败检查计数字典。

    Returns:
        dict[str, int]: 合并后的计数字典。
    """
    merged: dict[str, int] = {}
    for count_map in count_maps:
        for name, count in count_map.items():
            if not isinstance(count, int):
                continue
            merged[str(name)] = merged.get(str(name), 0) + count
    return merged


_GROUP_FAMILIES = {
    "group_rank_delta",
    "group_zscore",
    "group_mean_spread",
    "group_vol_scaled_delta",
}
_SIGNAL_FAMILIES = {
    "neutralize_decay",
    "zscore_time",
    "ts_rank",
    "decay_level",
    "rank_spread",
    "mean_spread",
    "vol_scaled_delta",
    "rank_delta",
    "decayed_delta",
}
_LEGACY_FAMILIES = {
    "legacy_level",
    "legacy_group_level",
    "legacy_ratio",
    "legacy_neg_ratio",
    "group_ratio_level",
}
_LEGACY_BASIC = {"legacy_level", "legacy_group_level"}

_PRIORITY_RULES: list[tuple[set[str], Any, int]] = [
    (
        {CHECK_LOW_SHARPE, CHECK_LOW_SUB_UNIVERSE_SHARPE},
        lambda f, n: f.startswith("group_") or f in _GROUP_FAMILIES,
        PRIORITY_ADJ_GROUP_LOW_SHARPE,
    ),
    ({CHECK_LOW_SHARPE, CHECK_LOW_SUB_UNIVERSE_SHARPE}, lambda f, n: f in _SIGNAL_FAMILIES, PRIORITY_ADJ_SIGNAL_LOW_SHARPE),
    ({CHECK_LOW_SHARPE, CHECK_LOW_SUB_UNIVERSE_SHARPE}, lambda f, n: f in _LEGACY_FAMILIES, PRIORITY_ADJ_LEGACY_LOW_SHARPE),
    ({CHECK_LOW_FITNESS}, lambda f, n: "delta" in f or "spread" in f or n.startswith("iter_"), PRIORITY_ADJ_DELTA_LOW_FITNESS),
    ({CHECK_LOW_FITNESS}, lambda f, n: f in _LEGACY_BASIC, PRIORITY_ADJ_LEGACY_BASIC_LOW_FITNESS),
    ({CHECK_LOW_FITNESS}, lambda f, n: f in {"group_vol_scaled_delta", "vol_scaled_delta"}, PRIORITY_ADJ_VOL_SCALED_LOW_FITNESS),
    (
        {CHECK_LOW_TURNOVER},
        lambda f, n: "delta" in f or n.startswith(("iter_rank_delta", "iter_rank_then_delta")),
        PRIORITY_ADJ_DELTA_LOW_TURNOVER,
    ),
    (
        {CHECK_LOW_TURNOVER},
        lambda f, n: f in {"legacy_level", "legacy_group_level", "mean_spread"},
        PRIORITY_ADJ_LEGACY_MEAN_SPREAD_LOW_TURNOVER,
    ),
    (
        {CHECK_HIGH_TURNOVER},
        lambda f, n: f in {"mean_spread", "decayed_delta", "decayed_ratio"},
        PRIORITY_ADJ_STABLE_HIGH_TURNOVER,
    ),
    ({CHECK_HIGH_TURNOVER}, lambda f, n: "delta" in f, PRIORITY_ADJ_DELTA_HIGH_TURNOVER),
    (
        {CHECK_CONCENTRATED_WEIGHT},
        lambda f, n: f.startswith("group_") and f not in {"group_vol_scaled_delta", "vol_scaled_delta"},
        PRIORITY_ADJ_GROUP_CONCENTRATED,
    ),
    ({CHECK_CONCENTRATED_WEIGHT}, lambda f, n: f in {"group_vol_scaled_delta", "vol_scaled_delta"}, PRIORITY_ADJ_VOL_SCALED_CONCENTRATED),
    (
        {CHECK_CONCENTRATED_WEIGHT},
        lambda f, n: f in {"legacy_ratio", "legacy_neg_ratio", "group_ratio_level"},
        PRIORITY_ADJ_LEGACY_RATIO_CONCENTRATED,
    ),
]
"""失败检查触发条件到优先级调整值的声明式规则表。"""


def adaptive_template_priority_adjustment(
    template_name: str,
    expression: str,
    *,
    field_feedback: dict[str, Any] | None,
    global_failed_check_counts: dict[str, int],
    metadata: dict[str, Any] | None = None,
) -> int:
    """
    根据字段与全局失败分布动态调整模板优先级。

    Args:
        template_name: 模板名称。
        expression: 表达式字符串。
        field_feedback: 字段级历史反馈。
        global_failed_check_counts: 全局失败检查计数。
        metadata: 可选模板元数据。

    Returns:
        int: 优先级调整值，可正可负。
    """
    field_counts = field_feedback.get("failed_check_counts", {}) if field_feedback else {}
    dominant_names = dominant_failed_check_names(
        merge_failed_check_counts(global_failed_check_counts, field_counts)
    )
    family = classify_expression_family(template_name, expression, metadata)
    lower_name = template_name.lower()
    adjustment = 0

    for triggers, condition, adj in _PRIORITY_RULES:
        if triggers & dominant_names and condition(family, lower_name):
            adjustment += adj

    if {CHECK_HIGH_TURNOVER, CHECK_CONCENTRATED_WEIGHT} <= dominant_names:
        if family in {"rank_spread", "mean_spread"}:
            adjustment += PRIORITY_ADJ_HIGH_TURNOVER_CONCENTRATED_RANK_SPREAD
        if "zscore" in lower_name and "spread" in lower_name:
            adjustment += PRIORITY_ADJ_HIGH_TURNOVER_CONCENTRATED_ZSCORE_SPREAD

    if field_feedback:
        best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE))
        if best_score >= EXPR_NEARPASS_BOOST_THRESHOLD and lower_name.startswith("iter_nearpass_"):
            adjustment += PRIORITY_ADJ_NEARPASS_BOOST
        elif best_score >= EXPR_ITER_BOOST_THRESHOLD and lower_name.startswith("iter_"):
            adjustment += PRIORITY_ADJ_ITER_BOOST
        if best_score >= EXPR_RATIO_PENALTY_THRESHOLD and family in _LEGACY_FAMILIES:
            adjustment += PRIORITY_ADJ_LEGACY_RATIO_PENALTY
        if (
            best_score >= EXPR_NEARPASS_BOOST_THRESHOLD
            and family == "group_rank_delta"
            and "nearpass" in lower_name
        ):
            adjustment += PRIORITY_ADJ_NEARPASS_GROUP_RANK_DELTA
        if family in {"group_vol_scaled_delta", "vol_scaled_delta"}:
            adjustment += PRIORITY_ADJ_VOL_SCALED_DELTA_BASE
            if CHECK_CONCENTRATED_WEIGHT in dominant_names:
                adjustment += PRIORITY_ADJ_VOL_SCALED_DELTA_CONCENTRATED
            if "nearpass" in lower_name:
                adjustment += PRIORITY_ADJ_VOL_SCALED_DELTA_NEARPASS
        if (
            lower_name.startswith("account_rank_backfill_")
            or lower_name == "account_ir_60"
            or lower_name.startswith("account_group_ir_60")
            or lower_name.startswith("account_group_backfill_")
        ):
            adjustment += PRIORITY_ADJ_ACCOUNT_TEMPLATES

    return adjustment


def apply_adaptive_priority(
    templates: Sequence[TemplateCandidate | tuple[str, str, int]],
    *,
    field_feedback: dict[str, Any] | None,
    global_failed_check_counts: dict[str, int],
    metadata_by_key: TemplateMetadataMap | None = None,
) -> list[TemplateCandidate]:
    """对候选模板应用自适应优先级调整。"""
    return [
        _make_template_candidate(
            template.name,
            template.expression,
            template.priority
            + adaptive_template_priority_adjustment(
                template.name,
                template.expression,
                field_feedback=field_feedback,
                global_failed_check_counts=global_failed_check_counts,
                metadata=template.metadata,
            ),
            metadata=template.metadata,
        )
        for template in (
            _coerce_template_candidate(raw_template, metadata_by_key=metadata_by_key)
            for raw_template in templates
        )
    ]


def cap_templates_per_family(
    templates: Sequence[TemplateCandidate | tuple[str, str, int]],
    max_templates_per_family: int,
    *,
    metadata_by_key: TemplateMetadataMap | None = None,
) -> list[TemplateCandidate]:
    """
    限制每个结构家族仅保留前 N 个候选模板。

    Args:
        templates: 已排序的模板候选列表。
        max_templates_per_family: 每个家族的模板数量上限，<=0 表示不限制。
        metadata_by_key: 可选模板元数据索引。

    Returns:
        list[TemplateCandidate]: family 限制后的模板候选。
    """
    if max_templates_per_family <= 0:
        return [
            _coerce_template_candidate(template, metadata_by_key=metadata_by_key)
            for template in templates
        ]
    kept: list[TemplateCandidate] = []
    family_counts: dict[str, int] = {}
    for raw_template in templates:
        template = _coerce_template_candidate(raw_template, metadata_by_key=metadata_by_key)
        family = classify_expression_family(
            template.name,
            template.expression,
            template.metadata,
        )
        used = family_counts.get(family, 0)
        if used >= max_templates_per_family:
            continue
        kept.append(template)
        family_counts[family] = used + 1
    return kept
