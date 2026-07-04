"""
bootstrap 字段准备辅助模块。
"""

from __future__ import annotations

from datetime import date
from math import log1p
from typing import Any, cast

from ..analysis.stats import field_priority
from ..config.constants import PREFERRED_FIELD_RANK_SENTINEL, SENTINEL_UNKNOWN, STATS_DEFAULT_SCORE
from ..config.models import DatasetExpressionPolicy
from ..models.io_types import RunFilters
from ..models.runtime import FieldSelectionArgs, HistoricalRunState, TemplateField
from ..generators.fields import choose_field_name
from ..utils.helpers import first_non_empty, is_event_field_name


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_date_ordinal(value: Any) -> int:
    if not value:
        return 0
    try:
        return date.fromisoformat(str(value)).toordinal()
    except (TypeError, ValueError):
        return 0


def _normalize_range(values: list[float]) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high <= low:
        return [0.0 for _ in values]
    span = high - low
    return [(value - low) / span for value in values]


def prepare_fields_for_execution(
    fields: list[TemplateField],
    *,
    filters_dict: RunFilters,
    expression_policy: DatasetExpressionPolicy,
    historical_state: HistoricalRunState,
    args: FieldSelectionArgs,
) -> tuple[list[TemplateField], dict[str, int]]:
    """对字段做过滤、排序并最终应用 offset/limit。"""
    cached_field_count = len(fields)
    filtered_fields: list[TemplateField] = []
    prefiltered_count = 0
    low_coverage_count = 0
    low_date_coverage_count = 0
    low_alpha_count = 0
    low_user_count = 0

    for field in fields:
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        field_name = choose_field_name(field)
        is_event_field = is_event_field_name(field_name, expression_policy.event_field_prefixes)
        min_coverage = (
            expression_policy.event_field_min_coverage
            if is_event_field and expression_policy.event_field_min_coverage > 0
            else expression_policy.field_min_coverage
        )
        min_date_coverage = (
            expression_policy.event_field_min_date_coverage
            if is_event_field and expression_policy.event_field_min_date_coverage > 0
            else expression_policy.field_min_date_coverage
        )
        min_alpha_count = (
            expression_policy.event_field_min_alpha_count
            if is_event_field and expression_policy.event_field_min_alpha_count > 0
            else expression_policy.field_min_alpha_count
        )
        min_user_count = (
            expression_policy.event_field_min_user_count
            if is_event_field and expression_policy.event_field_min_user_count > 0
            else expression_policy.field_min_user_count
        )
        if (
            filters_dict.include_fields
            and field_id not in filters_dict.include_fields
            and field_name not in filters_dict.include_fields
        ):
            prefiltered_count += 1
            continue
        if field_id in filters_dict.exclude_fields or field_name in filters_dict.exclude_fields:
            prefiltered_count += 1
            continue
        if _safe_float(field.get("coverage")) < min_coverage:
            low_coverage_count += 1
            continue
        if _safe_float(field.get("dateCoverage")) < min_date_coverage:
            low_date_coverage_count += 1
            continue
        if _safe_int(field.get("alphaCount")) < min_alpha_count:
            low_alpha_count += 1
            continue
        if _safe_int(field.get("userCount")) < min_user_count:
            low_user_count += 1
            continue
        filtered_fields.append(field)

    fields = filtered_fields
    if not fields:
        return [], {
            "cached_field_count": cached_field_count,
            "filtered_field_count": 0,
            "ranked_field_count": 0,
            "prefiltered_count": prefiltered_count,
            "low_coverage_count": low_coverage_count,
            "low_date_coverage_count": low_date_coverage_count,
            "low_alpha_count": low_alpha_count,
            "low_user_count": low_user_count,
        }

    coverage_values = [_safe_float(field.get("coverage")) for field in fields]
    date_coverage_values = [_safe_float(field.get("dateCoverage")) for field in fields]
    alpha_validation_values = [log1p(_safe_int(field.get("alphaCount"))) for field in fields]
    user_validation_values = [log1p(_safe_int(field.get("userCount"))) for field in fields]
    recency_values = [_safe_date_ordinal(field.get("dateCreated")) for field in fields]
    theme_values = [float(len(field.get("themes") or [])) for field in fields]

    norm_coverage_values = _normalize_range(coverage_values)
    norm_date_coverage_values = _normalize_range(date_coverage_values)
    norm_alpha_validation_values = _normalize_range(alpha_validation_values)
    norm_user_validation_values = _normalize_range(user_validation_values)
    norm_recency_values = _normalize_range([float(value) for value in recency_values])
    norm_theme_values = _normalize_range(theme_values)

    field_metadata_scores: dict[str, float] = {}
    for idx, field in enumerate(fields):
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        validation_score = (
            expression_policy.field_coverage_weight * norm_coverage_values[idx]
            + expression_policy.field_date_coverage_weight * norm_date_coverage_values[idx]
            + expression_policy.field_alpha_validation_weight * norm_alpha_validation_values[idx]
            + expression_policy.field_user_validation_weight * norm_user_validation_values[idx]
            + expression_policy.field_recency_weight * norm_recency_values[idx]
            + expression_policy.field_theme_bonus_weight * norm_theme_values[idx]
        )
        crowding_penalty = (
            expression_policy.field_alpha_crowding_penalty_weight * norm_alpha_validation_values[idx]
            + expression_policy.field_user_crowding_penalty_weight * norm_user_validation_values[idx]
        )
        field_metadata_scores[field_id] = validation_score - crowding_penalty

    def field_sort_key(item: TemplateField) -> tuple[Any, ...]:
        field_id = str(first_non_empty(item.get("id"), SENTINEL_UNKNOWN))
        field_name = choose_field_name(item)
        feedback = historical_state.field_feedback.get(field_id)
        priority = field_priority(field_id, historical_state.field_feedback)
        is_promising_seen = (
            feedback is not None and priority >= expression_policy.promising_field_min_priority
        )
        is_unexplored = feedback is None
        preferred_rank = expression_policy.preferred_field_order.get(field_name, PREFERRED_FIELD_RANK_SENTINEL)
        is_preferred_direction = preferred_rank < PREFERRED_FIELD_RANK_SENTINEL
        is_overtested_weak = (
            field_name in expression_policy.overtested_weak_fields and feedback is not None
        )
        metadata_score = field_metadata_scores.get(field_id, 0.0)
        effective_priority = priority
        if is_unexplored:
            effective_priority = min(
                expression_policy.promising_field_min_priority - 0.01,
                max(
                    metadata_score
                    + (
                        expression_policy.field_preferred_unexplored_bonus
                        if is_preferred_direction
                        else 0.0
                    ),
                    STATS_DEFAULT_SCORE,
                ),
            )
        elif priority > STATS_DEFAULT_SCORE:
            effective_priority = priority + metadata_score
        return (
            -int(is_promising_seen),
            int(is_overtested_weak),
            -effective_priority,
            -int(is_preferred_direction),
            preferred_rank,
            -int(is_unexplored),
            -metadata_score,
            -_safe_float(item.get("coverage")),
            -_safe_float(item.get("dateCoverage")),
            field_name,
        )

    fields.sort(key=field_sort_key)
    top_fields_by_feedback = cast(int, args.top_fields_by_feedback)
    offset = cast(int, args.offset)
    limit = cast(int, args.limit)
    if top_fields_by_feedback > 0:
        focused_fields = [
            field
            for field in fields
            if field_priority(
                str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
                historical_state.field_feedback,
            )
            > -999.0
        ]
        fields = focused_fields[:top_fields_by_feedback]

    ranked_field_count = len(fields)
    if offset > 0:
        fields = fields[offset:]
    if limit > 0:
        fields = fields[:limit]

    return fields, {
        "cached_field_count": cached_field_count,
        "filtered_field_count": len(filtered_fields),
        "ranked_field_count": ranked_field_count,
        "prefiltered_count": prefiltered_count,
        "low_coverage_count": low_coverage_count,
        "low_date_coverage_count": low_date_coverage_count,
        "low_alpha_count": low_alpha_count,
        "low_user_count": low_user_count,
    }
