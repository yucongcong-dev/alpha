"""Field ranking and selection helpers for bootstrap."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from ..analysis.field_stats import decay_field_feedback, field_priority
from ..config.constants import PREFERRED_FIELD_RANK_SENTINEL, SENTINEL_UNKNOWN, STATS_DEFAULT_SCORE
from ..config.models import DatasetExpressionPolicy
from ..generators.fields import choose_field_name
from ..models.domain import TemplateField
from ..models.runtime_options import FieldSelectionOptions
from ..runtime.contexts import HistoricalRunState
from ..utils.helpers import first_non_empty
from .bootstrap_field_families import field_window_rank, infer_field_family, preferred_field_rank

FieldSortKey = tuple[int, int, int, int, int, float, int, str]


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clamp_unit(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _feedback_priority(
    field_id: str,
    *,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> float:
    """Return feedback priority after optional age decay."""
    feedback = decay_field_feedback(
        historical_state.field_feedback.get(field_id),
        half_life_days=expression_policy.field_feedback_half_life_days,
    )
    if feedback is None:
        return field_priority(field_id, historical_state.field_feedback)
    return float(feedback.get("best_score", STATS_DEFAULT_SCORE) or STATS_DEFAULT_SCORE)


def _is_promising_feedback(
    field_id: str,
    *,
    priority: float,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> bool:
    """Require both score and a minimum sample count for strong pinning."""
    feedback = historical_state.field_feedback.get(field_id)
    if feedback is None:
        return False
    if _safe_int(feedback.get("submittable_templates")) > 0:
        return priority > STATS_DEFAULT_SCORE
    if priority < expression_policy.promising_field_min_priority:
        return False
    attempted = _safe_int(feedback.get("attempted_templates"))
    minimum = expression_policy.field_feedback_min_attempts_for_promising
    return minimum <= 0 or attempted >= minimum


def _selection_reason(
    field: TemplateField | dict[str, Any],
    *,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
    explicit: bool = False,
) -> str:
    if explicit:
        return "explicit"
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
    feedback = historical_state.field_feedback.get(field_id)
    if feedback is not None:
        priority = _feedback_priority(
            field_id,
            historical_state=historical_state,
            expression_policy=expression_policy,
        )
        if _is_promising_feedback(
            field_id,
            priority=priority,
            historical_state=historical_state,
            expression_policy=expression_policy,
        ):
            return "historical_promising"
        return "historical_feedback"
    field_name = choose_field_name(field)
    if field_name in expression_policy.preferred_field_order:
        return "preferred_unexplored"
    return "unexplored"


def _attach_selection_metadata(
    field: TemplateField | dict[str, Any],
    *,
    rank: int,
    score: float,
    family: str,
    reason: str,
) -> TemplateField | dict[str, Any]:
    updates = {
        "selection_rank": rank,
        "selection_score": round(score, 6),
        "selection_family": family,
        "selection_reason": reason,
    }
    if isinstance(field, TemplateField):
        metadata = dict(field.metadata)
        metadata.update(updates)
        return TemplateField(
            field_id=field.field_id,
            field_name=field.field_name,
            field_type=field.field_type,
            metadata=metadata,
        )
    field_copy = dict(field)
    field_copy.update(updates)
    return field_copy


def _append_with_family_cap(
    candidates: Sequence[TemplateField | dict[str, Any]],
    selected: list[TemplateField | dict[str, Any]],
    selected_ids: set[str],
    family_counts: dict[str, int],
    *,
    target: int,
    max_per_family: int,
) -> None:
    for field in candidates:
        if len(selected) >= target:
            return
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        if field_id in selected_ids:
            continue
        family = infer_field_family(choose_field_name(field))
        if max_per_family > 0 and family_counts.get(family, 0) >= max_per_family:
            continue
        selected.append(field)
        selected_ids.add(field_id)
        family_counts[family] = family_counts.get(family, 0) + 1


def _select_diverse_fields(
    fields: Sequence[TemplateField | dict[str, Any]],
    *,
    target: int,
    max_per_family: int,
    exploration_ratio: float,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> list[TemplateField | dict[str, Any]]:
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
            str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
            priority=_feedback_priority(
                str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
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
        if historical_state.field_feedback.get(
            str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        )
        is None
    ]

    selected: list[TemplateField | dict[str, Any]] = []
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


def rank_by_id(fields: Sequence[TemplateField | dict[str, Any]]) -> dict[str, int]:
    return {
        str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)): index
        for index, field in enumerate(fields, start=1)
    }


def apply_offset_limit(
    fields: Sequence[TemplateField | dict[str, Any]],
    *,
    offset: int,
    limit: int,
) -> list[TemplateField | dict[str, Any]]:
    window = list(fields)
    if offset > 0:
        window = window[offset:]
    if limit > 0:
        window = window[:limit]
    return window


def attach_selection_to_fields(
    fields: Sequence[TemplateField | dict[str, Any]],
    *,
    rank_by_field_id: dict[str, int],
    field_scores: dict[str, float],
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
    explicit: bool,
) -> list[TemplateField]:
    selected_fields: list[TemplateField | dict[str, Any]] = []
    for field in fields:
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
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
    return cast(list[TemplateField], selected_fields)


def field_selection_scores(
    fields: Sequence[TemplateField | dict[str, Any]],
    *,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for field in fields:
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        if historical_state.field_feedback.get(field_id) is None:
            scores[field_id] = 0.0
        else:
            scores[field_id] = _feedback_priority(
                field_id,
                historical_state=historical_state,
                expression_policy=expression_policy,
            )
    return scores


def _field_sort_key(
    item: TemplateField,
    *,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> FieldSortKey:
    field_id = str(first_non_empty(item.get("id"), SENTINEL_UNKNOWN))
    field_name = choose_field_name(item)
    field_type = str(item.get("type", "UNKNOWN")).upper()
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
        fields = [
            field
            for field in fields
            if _feedback_priority(
                str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
                historical_state=historical_state,
                expression_policy=expression_policy,
            )
            > -999.0
        ][:top_fields_by_feedback]

    ranked_field_count = len(fields)
    if limit > 0 and top_fields_by_feedback <= 0:
        fields = cast(
            list[TemplateField],
            _select_diverse_fields(
                fields,
                target=offset + limit,
                max_per_family=expression_policy.field_max_per_family,
                exploration_ratio=expression_policy.field_exploration_ratio,
                historical_state=historical_state,
                expression_policy=expression_policy,
            ),
        )
    fields = cast(list[TemplateField], apply_offset_limit(fields, offset=offset, limit=limit))
    return fields, rank_by_field_id, ranked_field_count
