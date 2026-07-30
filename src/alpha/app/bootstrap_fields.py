"""
bootstrap 字段准备辅助模块。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime, timezone
from math import log1p
from typing import Any, cast

from ..analysis.field_stats import decay_field_feedback, field_priority
from ..config.constants import PREFERRED_FIELD_RANK_SENTINEL, SENTINEL_UNKNOWN, STATS_DEFAULT_SCORE
from ..config.models import DatasetExpressionPolicy
from ..generators.fields import choose_field_name
from ..models.domain import TemplateField
from ..models.io_types import RunFilters
from ..runtime.contexts import HistoricalRunState
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


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_explicitly_included(field_id: str, field_name: str, filters_dict: RunFilters) -> bool:
    return bool(
        filters_dict.include_fields
        and (field_id in filters_dict.include_fields or field_name in filters_dict.include_fields)
    )


def _infer_runtime_field_tags(
    field_name: str,
    *,
    dataset_id: str,
    coverage: float,
) -> tuple[str, ...]:
    dataset_key = dataset_id.strip().lower()
    tags: list[str] = []
    if dataset_key == "model16":
        if field_name.startswith("fscore_bfl_"):
            tags.extend(["model16_sparse_bfl", "model16_sparse_score", "model16_fscore_family"])
        elif field_name.startswith("fscore_"):
            tags.extend(["model16_sparse_fscore", "model16_sparse_score", "model16_fscore_family"])
        elif field_name.endswith("_derivative"):
            tags.extend(["model16_dense_derivative", "model16_dense_score"])
    if coverage >= 0.95:
        tags.append("high_coverage")
    elif coverage <= 0.50:
        tags.append("sparse_coverage")
    return tuple(tags)


def _attach_runtime_metadata(
    field: TemplateField,
    *,
    runtime_field_tags: tuple[str, ...],
) -> TemplateField:
    if not runtime_field_tags:
        return field
    metadata = dict(field.metadata)
    metadata["runtime_field_tags"] = list(runtime_field_tags)
    return TemplateField(
        field_id=field.field_id,
        field_name=field.field_name,
        field_type=field.field_type,
        metadata=metadata,
    )


FieldSortKey = tuple[int, int, int, int, int, float, int, float, float, float, int, str]

_ALPHA_VALIDATION_TARGET = 100
_USER_VALIDATION_TARGET = 20
_ALPHA_CROWDING_START = 1000
_USER_CROWDING_START = 500
_ALPHA_CROWDING_SCALE = 10_000
_USER_CROWDING_SCALE = 5_000
_RECENCY_SCORE_HORIZON_DAYS = 3650
_FIELD_ALL_SUFFIX = re.compile(r"_all$")
_FIELD_WINDOW_TOKEN = re.compile(r"_(?:last_)?\d+(?:_days?)?(?=_|$)")
_FIELD_TRAILING_WINDOW = re.compile(r"(?:_last)?_(\d+)(?:_days?)?(?:_|$)")
_PREFERRED_FIELD_WINDOWS = (30, 60, 90, 20, 120, 180, 10, 150, 270, 360, 720, 1080)


def _clamp_unit(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _absolute_validation_score(value: int, target: int) -> float:
    """Reward external validation until a moderate target, then saturate."""
    if value <= 0 or target <= 0:
        return 0.0
    return _clamp_unit(log1p(value) / log1p(target))


def _absolute_crowding_score(value: int, start: int, scale: int) -> float:
    """Apply no crowding penalty below start and increase smoothly afterwards."""
    if value <= start or scale <= start:
        return 0.0
    numerator = log1p(value) - log1p(start)
    denominator = log1p(scale) - log1p(start)
    return _clamp_unit(numerator / denominator)


def _absolute_recency_score(value: Any) -> float:
    if not value:
        return 0.0
    try:
        created = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return 0.0
    age_days = max((date.today() - created).days, 0)
    return _clamp_unit(1.0 - age_days / _RECENCY_SCORE_HORIZON_DAYS)


def _feedback_recency_multiplier(value: Any, half_life_days: int) -> float:
    """Decay historical feedback as it becomes stale.

    Missing or malformed timestamps retain the legacy neutral multiplier so
    older result files remain usable while newly enriched results decay.
    """
    if not value or half_life_days <= 0:
        return 1.0
    try:
        observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 1.0
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    age_days = max((datetime.now(timezone.utc) - observed).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / half_life_days)


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


def infer_field_family(field_name: str) -> str:
    """Collapse repeated tenor/window variants into a stable semantic family.

    Window tokens may appear before an instrument suffix (for example
    ``correlation_last_30_days_spy``), not only at the end of a field name.
    Removing the token while retaining the suffix groups all tenor variants
    without merging unrelated fields such as ``*_fast_d1``.
    """
    normalized = field_name.strip().lower()
    family = _FIELD_ALL_SUFFIX.sub("", normalized)
    family = _FIELD_WINDOW_TOKEN.sub("", family)
    return family or normalized


def _preferred_field_rank(field_name: str, preferred_order: dict[str, int]) -> int:
    """Resolve exact and semantic aliases in preferred field ordering.

    Dataset policies historically used both concrete IDs (``cash_st``) and
    semantic labels (``value``, ``quality``).  Exact IDs win; otherwise a
    semantic label matching a field token is used as a fallback.
    """
    normalized = field_name.strip().lower()
    exact = preferred_order.get(normalized)
    if exact is not None:
        return exact
    semantic_matches = [
        rank
        for label, rank in preferred_order.items()
        if str(label).strip().lower() in normalized.split("_")
    ]
    return min(semantic_matches) if semantic_matches else PREFERRED_FIELD_RANK_SENTINEL


def _field_window_rank(field_name: str) -> int:
    match = _FIELD_TRAILING_WINDOW.search(field_name.strip().lower())
    if match is None:
        return 0
    window = int(match.group(1))
    try:
        return _PREFERRED_FIELD_WINDOWS.index(window) + 1
    except ValueError:
        return len(_PREFERRED_FIELD_WINDOWS) + 1


def _selection_reason(
    field: TemplateField | dict[str, Any],
    *,
    historical_state: HistoricalRunState,
    expression_policy: DatasetExpressionPolicy,
) -> str:
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

    # Family caps are soft: never return fewer fields solely because the dataset
    # contains only a handful of semantic families.
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


def resolve_field_selection(args: object) -> tuple[int, int, int]:
    """Extract top-N/offset/limit knobs from an args-like object."""
    return (
        _safe_int(getattr(args, "top_fields_by_feedback", 0)),
        _safe_int(getattr(args, "offset", 0)),
        _safe_int(getattr(args, "limit", 0)),
    )


def prepare_fields_for_execution(
    fields: list[TemplateField],
    *,
    filters_dict: RunFilters,
    expression_policy: DatasetExpressionPolicy,
    historical_state: HistoricalRunState,
    args: object,
) -> tuple[list[TemplateField], dict[str, int]]:
    """对字段做过滤、排序并最终应用 offset/limit。"""
    top_fields_by_feedback, offset, limit = resolve_field_selection(args)
    cached_field_count = len(fields)
    filtered_fields: list[TemplateField] = []
    prefiltered_count = 0
    low_coverage_count = 0
    low_date_coverage_count = 0
    low_alpha_count = 0
    low_user_count = 0
    high_alpha_count = 0
    high_user_count = 0
    unknown_coverage_count = 0
    unknown_date_coverage_count = 0
    unknown_alpha_count = 0
    unknown_user_count = 0

    for field in fields:
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        field_name = choose_field_name(field)
        explicitly_included = _is_explicitly_included(field_id, field_name, filters_dict)
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
        coverage_value = _optional_float(field.get("coverage"))
        date_coverage_value = _optional_float(field.get("dateCoverage"))
        alpha_count_value = _optional_int(field.get("alphaCount"))
        user_count_value = _optional_int(field.get("userCount"))
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
        if coverage_value is None:
            unknown_coverage_count += 1
        elif coverage_value < min_coverage:
            low_coverage_count += 1
            continue
        if date_coverage_value is None:
            unknown_date_coverage_count += 1
        elif date_coverage_value < min_date_coverage:
            low_date_coverage_count += 1
            continue
        if alpha_count_value is None:
            unknown_alpha_count += 1
        elif alpha_count_value < min_alpha_count:
            low_alpha_count += 1
            continue
        if user_count_value is None:
            unknown_user_count += 1
        elif user_count_value < min_user_count:
            low_user_count += 1
            continue
        if (
            not explicitly_included
            and expression_policy.field_max_alpha_count > 0
            and alpha_count_value is not None
            and alpha_count_value > expression_policy.field_max_alpha_count
        ):
            high_alpha_count += 1
            continue
        if (
            not explicitly_included
            and expression_policy.field_max_user_count > 0
            and user_count_value is not None
            and user_count_value > expression_policy.field_max_user_count
        ):
            high_user_count += 1
            continue
        runtime_field_tags = _infer_runtime_field_tags(
            field_name,
            dataset_id=expression_policy.dataset_id,
            coverage=coverage_value or 0.0,
        )
        if isinstance(field, TemplateField):
            filtered_fields.append(
                _attach_runtime_metadata(field, runtime_field_tags=runtime_field_tags)
            )
            continue
        # Compatibility for legacy dict-shaped test/plugin inputs; production
        # field loaders normalize rows to TemplateField before this boundary.
        field_copy = dict(field)  # type: ignore[unreachable]
        if runtime_field_tags:
            field_copy["runtime_field_tags"] = list(runtime_field_tags)
        filtered_fields.append(field_copy)

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
            "high_alpha_count": high_alpha_count,
            "high_user_count": high_user_count,
            "unknown_coverage_count": unknown_coverage_count,
            "unknown_date_coverage_count": unknown_date_coverage_count,
            "unknown_alpha_count": unknown_alpha_count,
            "unknown_user_count": unknown_user_count,
        }

    norm_coverage_values = [_clamp_unit(_safe_float(field.get("coverage"))) for field in fields]
    norm_date_coverage_values = [
        _clamp_unit(_safe_float(field.get("dateCoverage"))) for field in fields
    ]
    norm_alpha_validation_values = [
        _absolute_validation_score(
            _safe_int(field.get("alphaCount")), _ALPHA_VALIDATION_TARGET
        )
        for field in fields
    ]
    norm_user_validation_values = [
        _absolute_validation_score(_safe_int(field.get("userCount")), _USER_VALIDATION_TARGET)
        for field in fields
    ]
    norm_alpha_crowding_values = [
        _absolute_crowding_score(
            _safe_int(field.get("alphaCount")),
            _ALPHA_CROWDING_START,
            _ALPHA_CROWDING_SCALE,
        )
        for field in fields
    ]
    norm_user_crowding_values = [
        _absolute_crowding_score(
            _safe_int(field.get("userCount")),
            _USER_CROWDING_START,
            _USER_CROWDING_SCALE,
        )
        for field in fields
    ]
    norm_recency_values = [
        _absolute_recency_score(field.get("dateCreated")) for field in fields
    ]
    norm_theme_values = [
        _clamp_unit(float(len(field.get("themes") or [])) / 3.0) for field in fields
    ]
    unknown_metadata_counts = [
        sum(
            value is None
            for value in (
                _optional_float(field.get("coverage")),
                _optional_float(field.get("dateCoverage")),
                _optional_int(field.get("alphaCount")),
                _optional_int(field.get("userCount")),
            )
        )
        for field in fields
    ]

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
            expression_policy.field_alpha_crowding_penalty_weight
            * norm_alpha_crowding_values[idx]
            + expression_policy.field_user_crowding_penalty_weight
            * norm_user_crowding_values[idx]
        )
        unknown_metadata_penalty = expression_policy.field_unknown_metadata_penalty_weight * (
            unknown_metadata_counts[idx] / 4.0
        )
        field_metadata_scores[field_id] = (
            validation_score - crowding_penalty - unknown_metadata_penalty
        )

    def field_sort_key(item: TemplateField) -> FieldSortKey:
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
        preferred_rank = _preferred_field_rank(
            field_name, expression_policy.preferred_field_order
        )
        preferred_type_rank = expression_policy.preferred_field_type_order.get(
            field_type, PREFERRED_FIELD_RANK_SENTINEL
        )
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
        unexplored_type_rank = preferred_type_rank if is_unexplored else 0
        return (
            -int(is_promising_seen),
            int(is_overtested_weak),
            -int(is_preferred_direction),
            preferred_rank,
            unexplored_type_rank,
            -effective_priority,
            -int(is_unexplored),
            -metadata_score,
            -_safe_float(item.get("coverage")),
            -_safe_float(item.get("dateCoverage")),
            _field_window_rank(field_name),
            field_name,
        )

    fields.sort(key=field_sort_key)
    ranked_fields = list(fields)
    rank_by_id = {
        str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)): index
        for index, field in enumerate(ranked_fields, start=1)
    }
    if top_fields_by_feedback > 0:
        focused_fields = [
            field
            for field in fields
            if _feedback_priority(
                str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
                historical_state=historical_state,
                expression_policy=expression_policy,
            )
            > -999.0
        ]
        fields = focused_fields[:top_fields_by_feedback]

    ranked_field_count = len(fields)
    explicit_field_selection = bool(filters_dict.include_fields)
    if limit > 0 and not explicit_field_selection and top_fields_by_feedback <= 0:
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
    if offset > 0:
        fields = fields[offset:]
    if limit > 0:
        fields = fields[:limit]

    selected_fields: list[TemplateField | dict[str, Any]] = []
    for field in fields:
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        selected_fields.append(
            _attach_selection_metadata(
                field,
                rank=rank_by_id.get(field_id, 0),
                score=field_metadata_scores.get(field_id, 0.0),
                family=infer_field_family(choose_field_name(field)),
                reason=_selection_reason(
                    field,
                    historical_state=historical_state,
                    expression_policy=expression_policy,
                ),
            )
        )
    fields = cast(list[TemplateField], selected_fields)

    return fields, {
        "cached_field_count": cached_field_count,
        "filtered_field_count": len(filtered_fields),
        "ranked_field_count": ranked_field_count,
        "prefiltered_count": prefiltered_count,
        "low_coverage_count": low_coverage_count,
        "low_date_coverage_count": low_date_coverage_count,
        "low_alpha_count": low_alpha_count,
        "low_user_count": low_user_count,
        "high_alpha_count": high_alpha_count,
        "high_user_count": high_user_count,
        "unknown_coverage_count": unknown_coverage_count,
        "unknown_date_coverage_count": unknown_date_coverage_count,
        "unknown_alpha_count": unknown_alpha_count,
        "unknown_user_count": unknown_user_count,
        "selected_family_count": len(
            {str(field.get("selection_family", "")) for field in fields}
        ),
        "selected_unexplored_count": sum(
            1 for field in fields if str(field.get("selection_reason", "")).endswith("unexplored")
        ),
    }
