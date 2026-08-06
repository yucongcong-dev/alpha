"""Field ranking and selection helpers for bootstrap."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config.constants import PREFERRED_FIELD_RANK_SENTINEL, SENTINEL_UNKNOWN, STATS_DEFAULT_SCORE
from ..config.models import DatasetExpressionPolicy
from ..generators.fields import choose_field_name
from ..models.domain import TemplateField
from ..models.runtime_options import FieldSelectionOptions
from ..runtime.contexts import HistoricalRunState
from . import bootstrap_field_feedback as _feedback
from .bootstrap_field_families import field_window_rank, infer_field_family, preferred_field_rank

__all__ = [
    "apply_offset_limit",
    "attach_selection_to_fields",
    "field_selection_scores",
    "infer_field_family",
    "rank_and_select_exploration_fields",
    "rank_by_id",
    "resolve_field_selection",
]

FieldSortKey = tuple[int, int, int, int, int, float, int, str]

_feedback_priority = _feedback.feedback_priority
field_selection_scores = _feedback.field_selection_scores
_is_promising_feedback = _feedback.is_promising_feedback
_selection_reason = _feedback.selection_reason


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clamp_unit(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _attach_selection_metadata(
    field: TemplateField,
    *,
    rank: int,
    score: float,
    family: str,
    reason: str,
) -> TemplateField:
    updates = {
        "selection_rank": rank,
        "selection_score": round(score, 6),
        "selection_family": family,
        "selection_reason": reason,
    }
    metadata = dict(field.metadata)
    metadata.update(updates)
    return TemplateField(
        field_id=field.field_id,
        field_name=field.field_name,
        field_type=field.field_type,
        metadata=metadata,
    )


def _append_with_family_cap(
    candidates: Sequence[TemplateField],
    selected: list[TemplateField],
    selected_ids: set[str],
    family_counts: dict[str, int],
    *,
    target: int,
    max_per_family: int,
) -> None:
    for field in candidates:
        if len(selected) >= target:
            return
        field_id = field.field_id or SENTINEL_UNKNOWN
        if field_id in selected_ids:
            continue
        family = infer_field_family(choose_field_name(field))
        if max_per_family > 0 and family_counts.get(family, 0) >= max_per_family:
            continue
        selected.append(field)
        selected_ids.add(field_id)
        family_counts[family] = family_counts.get(family, 0) + 1


def _select_diverse_fields(
    fields: Sequence[TemplateField],
    *,
    target: int,
    max_per_family: int,
    exploration_ratio: float,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> list[TemplateField]:
    """Select a bounded exploit/explore mix while avoiding tenor-family monopolies."""
    if target <= 0 or len(fields) <= target:
        return list(fields)

    exploration_target = int(target * _clamp_unit(exploration_ratio))
    if target >= 2 and exploration_ratio > 0 and exploration_target == 0:
        exploration_target = 1
    exploitation_target = target - exploration_target
    promising = [
        field
        for field in fields
        if _is_promising_feedback(
            field.field_id or SENTINEL_UNKNOWN,
            priority=_feedback_priority(
                field.field_id or SENTINEL_UNKNOWN,
                historical_state=historical_state,
                expression_policy=expression_policy,
            ),
            historical_state=historical_state,
            expression_policy=expression_policy,
        )
    ]
    unexplored = [
        field
        for field in fields
        if historical_state.field_feedback.get(field.field_id or SENTINEL_UNKNOWN) is None
    ]

    selected: list[TemplateField] = []
    selected_ids: set[str] = set()
    family_counts: dict[str, int] = {}
    _append_with_family_cap(
        promising,
        selected,
        selected_ids,
        family_counts,
        target=exploitation_target,
        max_per_family=max_per_family,
    )
    _append_with_family_cap(
        unexplored,
        selected,
        selected_ids,
        family_counts,
        target=target,
        max_per_family=max_per_family,
    )
    _append_with_family_cap(
        fields,
        selected,
        selected_ids,
        family_counts,
        target=target,
        max_per_family=max_per_family,
    )

    if len(selected) < target:
        _append_with_family_cap(
            fields,
            selected,
            selected_ids,
            family_counts,
            target=target,
            max_per_family=0,
        )
    return selected


def resolve_field_selection(selection_options: FieldSelectionOptions) -> tuple[int, int, int]:
    """Extract top-N/offset/limit knobs from field selection options."""
    return (
        _safe_int(selection_options.top_fields_by_feedback),
        _safe_int(selection_options.offset),
        _safe_int(selection_options.limit),
    )


def rank_by_id(fields: Sequence[TemplateField]) -> dict[str, int]:
    return {field.field_id: index for index, field in enumerate(fields, start=1)}


def apply_offset_limit(
    fields: Sequence[TemplateField],
    *,
    offset: int,
    limit: int,
) -> list[TemplateField]:
    window = list(fields)
    if offset > 0:
        window = window[offset:]
    if limit > 0:
        window = window[:limit]
    return window


def attach_selection_to_fields(
    fields: Sequence[TemplateField],
    *,
    rank_by_field_id: dict[str, int],
    field_scores: dict[str, float],
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
    explicit: bool,
) -> list[TemplateField]:
    selected_fields: list[TemplateField] = []
    for field in fields:
        field_id = field.field_id or SENTINEL_UNKNOWN
        selected_fields.append(
            _attach_selection_metadata(
                field,
                rank=rank_by_field_id.get(field_id, 0),
                score=field_scores.get(field_id, 0.0),
                family=infer_field_family(choose_field_name(field)),
                reason=_selection_reason(
                    field,
                    historical_state=historical_state,
                    expression_policy=expression_policy,
                    explicit=explicit,
                ),
            )
        )
    return selected_fields


def _field_sort_key(
    item: TemplateField,
    *,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> FieldSortKey:
    field_id = item.field_id or SENTINEL_UNKNOWN
    field_name = item.field_name
    field_type = item.field_type.upper()
    feedback = historical_state.field_feedback.get(field_id)
    priority = _feedback_priority(
        field_id,
        historical_state=historical_state,
        expression_policy=expression_policy,
    )
    is_promising_seen = _is_promising_feedback(
        field_id,
        priority=priority,
        historical_state=historical_state,
        expression_policy=expression_policy,
    )
    is_unexplored = feedback is None
    preferred_rank = preferred_field_rank(field_name, expression_policy.preferred_field_order)
    preferred_type_rank = expression_policy.preferred_field_type_order.get(
        field_type, PREFERRED_FIELD_RANK_SENTINEL
    )
    is_preferred_direction = preferred_rank < PREFERRED_FIELD_RANK_SENTINEL
    feedback_rank = (
        0
        if is_promising_seen
        else 1
        if feedback is not None and priority > STATS_DEFAULT_SCORE
        else 2
        if is_unexplored
        else 3
    )
    return (
        -int(is_promising_seen),
        -int(is_preferred_direction),
        preferred_rank,
        feedback_rank,
        preferred_type_rank,
        -priority if feedback is not None else 0.0,
        field_window_rank(field_name),
        field_name,
    )


def rank_and_select_exploration_fields(
    fields: list[TemplateField],
    *,
    top_fields_by_feedback: int,
    offset: int,
    limit: int,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> tuple[list[TemplateField], dict[str, int], int]:
    fields.sort(
        key=lambda item: _field_sort_key(
            item,
            historical_state=historical_state,
            expression_policy=expression_policy,
        )
    )
    ranked_fields = list(fields)
    rank_by_field_id = rank_by_id(ranked_fields)
    if top_fields_by_feedback > 0:
        feedback_fields = [
            field
            for field in fields
            if _feedback_priority(
                field.field_id or SENTINEL_UNKNOWN,
                historical_state=historical_state,
                expression_policy=expression_policy,
            )
            > -999.0
        ]
        fields = _select_diverse_fields(
            feedback_fields,
            target=top_fields_by_feedback,
            max_per_family=expression_policy.field_max_per_family,
            exploration_ratio=0.0,
            historical_state=historical_state,
            expression_policy=expression_policy,
        )

    ranked_field_count = len(fields)
    if limit > 0 and top_fields_by_feedback <= 0:
        fields = _select_diverse_fields(
            fields,
            target=offset + limit,
            max_per_family=expression_policy.field_max_per_family,
            exploration_ratio=expression_policy.field_exploration_ratio,
            historical_state=historical_state,
            expression_policy=expression_policy,
        )
    fields = apply_offset_limit(fields, offset=offset, limit=limit)
    return fields, rank_by_field_id, ranked_field_count
