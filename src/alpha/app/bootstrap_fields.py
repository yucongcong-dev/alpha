"""Field metadata, filtering, ranking, selection, and family helpers for bootstrap."""

from __future__ import annotations

from collections.abc import Sequence

from ..config.models import DatasetExpressionPolicy
from ..models.domain import TemplateField
from ..models.io_types import RunFilters
from ..models.runtime_options import FieldSelectionOptions
from ..runtime.contexts import HistoricalRunState
from .bootstrap_field_quality import (
    field_with_runtime_metadata,
    metadata_values,
    passes_quality_filters,
    quality_thresholds,
)
from .bootstrap_field_selection import (
    apply_offset_limit,
    attach_selection_to_fields,
    field_selection_scores,
    infer_field_family,
    rank_and_select_exploration_fields,
    rank_by_id,
    resolve_field_selection,
)

__all__ = [
    "infer_field_family",
    "prepare_fields_for_execution",
    "resolve_field_selection",
]


def field_identity(field: TemplateField) -> tuple[str, str]:
    return field.field_id, field.field_name


def base_field_stats(cached_field_count: int) -> dict[str, int]:
    return {
        "cached_field_count": cached_field_count,
        "filtered_field_count": 0,
        "ranked_field_count": 0,
        "prefiltered_count": 0,
        "low_coverage_count": 0,
        "low_date_coverage_count": 0,
        "low_alpha_count": 0,
        "low_user_count": 0,
        "high_alpha_count": 0,
        "high_user_count": 0,
        "unknown_coverage_count": 0,
        "unknown_date_coverage_count": 0,
        "unknown_alpha_count": 0,
        "unknown_user_count": 0,
        "selected_family_count": 0,
        "selected_unexplored_count": 0,
    }


def _is_explicitly_included(field_id: str, field_name: str, filters_dict: RunFilters) -> bool:
    return bool(
        filters_dict.include_fields
        and (field_id in filters_dict.include_fields or field_name in filters_dict.include_fields)
    )


def _finish_field_stats(
    stats: dict[str, int],
    *,
    filtered_fields: Sequence[TemplateField],
    ranked_field_count: int,
    selected_fields: Sequence[TemplateField],
) -> dict[str, int]:
    stats["filtered_field_count"] = len(filtered_fields)
    stats["ranked_field_count"] = ranked_field_count
    stats["selected_family_count"] = len(
        {str(field.get("selection_family", "")) for field in selected_fields}
    )
    stats["selected_unexplored_count"] = sum(
        1
        for field in selected_fields
        if str(field.get("selection_reason", "")).endswith("unexplored")
    )
    return stats


def _prepare_explicit_fields_for_execution(
    fields: list[TemplateField],
    *,
    filters_dict: RunFilters,
    expression_policy: DatasetExpressionPolicy,
    historical_state: HistoricalRunState,
    offset: int,
    limit: int,
) -> tuple[list[TemplateField], dict[str, int]]:
    """Prepare an explicit include-fields run without metadata or feedback ranking."""
    stats = base_field_stats(len(fields))
    filtered_fields: list[TemplateField] = []
    for field in fields:
        field_id, field_name = field_identity(field)
        values = metadata_values(field)
        if not _is_explicitly_included(field_id, field_name, filters_dict):
            stats["prefiltered_count"] += 1
            continue
        if field_id in filters_dict.exclude_fields or field_name in filters_dict.exclude_fields:
            stats["prefiltered_count"] += 1
            continue
        filtered_fields.append(
            field_with_runtime_metadata(
                field,
                expression_policy=expression_policy,
                coverage=values.coverage_for_tags,
            )
        )

    if not filtered_fields:
        return [], stats

    rank_by_field_id = rank_by_id(filtered_fields)
    fields_window = apply_offset_limit(list(filtered_fields), offset=offset, limit=limit)
    selected_fields = attach_selection_to_fields(
        fields_window,
        rank_by_field_id=rank_by_field_id,
        field_scores={},
        historical_state=historical_state,
        expression_policy=expression_policy,
        explicit=True,
    )
    return selected_fields, _finish_field_stats(
        stats,
        filtered_fields=filtered_fields,
        ranked_field_count=len(filtered_fields),
        selected_fields=selected_fields,
    )


def prepare_fields_for_execution(
    fields: list[TemplateField],
    *,
    filters_dict: RunFilters,
    expression_policy: DatasetExpressionPolicy,
    historical_state: HistoricalRunState,
    selection_options: FieldSelectionOptions,
) -> tuple[list[TemplateField], dict[str, int]]:
    """对字段做过滤、排序并最终应用 offset/limit。"""
    top_fields_by_feedback, offset, limit = resolve_field_selection(selection_options)
    cached_field_count = len(fields)
    if filters_dict.include_fields:
        return _prepare_explicit_fields_for_execution(
            fields,
            filters_dict=filters_dict,
            expression_policy=expression_policy,
            historical_state=historical_state,
            offset=offset,
            limit=limit,
        )

    filtered_fields: list[TemplateField] = []
    stats = base_field_stats(cached_field_count)

    for field in fields:
        field_id, field_name = field_identity(field)
        if field_id in filters_dict.exclude_fields or field_name in filters_dict.exclude_fields:
            stats["prefiltered_count"] += 1
            continue
        values = metadata_values(field)
        if not passes_quality_filters(
            values,
            quality_thresholds(field_name, expression_policy),
            stats,
        ):
            continue
        filtered_fields.append(
            field_with_runtime_metadata(
                field,
                expression_policy=expression_policy,
                coverage=values.coverage_for_tags,
            )
        )

    fields = filtered_fields
    if not fields:
        return [], stats

    field_scores = field_selection_scores(
        fields,
        historical_state=historical_state,
        expression_policy=expression_policy,
    )
    fields, rank_by_field_id, ranked_field_count = rank_and_select_exploration_fields(
        fields,
        top_fields_by_feedback=top_fields_by_feedback,
        offset=offset,
        limit=limit,
        historical_state=historical_state,
        expression_policy=expression_policy,
    )
    selected_fields = attach_selection_to_fields(
        fields,
        rank_by_field_id=rank_by_field_id,
        field_scores=field_scores,
        historical_state=historical_state,
        expression_policy=expression_policy,
        explicit=False,
    )
    return selected_fields, _finish_field_stats(
        stats,
        filtered_fields=filtered_fields,
        ranked_field_count=ranked_field_count,
        selected_fields=selected_fields,
    )
