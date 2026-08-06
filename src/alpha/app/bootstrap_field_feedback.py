"""Field feedback scoring helpers for bootstrap selection."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..analysis.field_stats import decay_field_feedback, field_priority
from ..config.constants import SENTINEL_UNKNOWN, STATS_DEFAULT_SCORE
from ..config.models import DatasetExpressionPolicy
from ..models.domain import TemplateField
from ..runtime.contexts import HistoricalRunState


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def feedback_priority(
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


def is_promising_feedback(
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


def selection_reason(
    field: TemplateField,
    *,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
    explicit: bool = False,
) -> str:
    if explicit:
        return "explicit"
    field_id = field.field_id or SENTINEL_UNKNOWN
    feedback = historical_state.field_feedback.get(field_id)
    if feedback is not None:
        priority = feedback_priority(
            field_id,
            historical_state=historical_state,
            expression_policy=expression_policy,
        )
        if is_promising_feedback(
            field_id,
            priority=priority,
            historical_state=historical_state,
            expression_policy=expression_policy,
        ):
            return "historical_promising"
        return "historical_feedback"
    field_name = field.field_name
    if field_name in expression_policy.preferred_field_order:
        return "preferred_unexplored"
    return "unexplored"


def field_selection_scores(
    fields: Sequence[TemplateField],
    *,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for field in fields:
        field_id = field.field_id or SENTINEL_UNKNOWN
        if historical_state.field_feedback.get(field_id) is None:
            scores[field_id] = 0.0
        else:
            scores[field_id] = feedback_priority(
                field_id,
                historical_state=historical_state,
                expression_policy=expression_policy,
            )
    return scores
