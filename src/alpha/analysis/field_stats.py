"""字段层表现汇总与字段优先级。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from math import pow
from typing import Any

from ..config.static_config import get_static_config
from ..models.domain import FieldFeedbackMap, FieldTestResult
from ..models.result_predicates import has_pending_checks, is_queue_timeout_result


def compile_field_performance_summary(results: Sequence[FieldTestResult]) -> list[dict[str, Any]]:
    """构建适合写入 JSON 的字段层表现汇总。"""
    grouped: dict[str, dict[str, Any]] = {}
    for result in results:
        if has_pending_checks(result):
            continue
        summary = grouped.setdefault(
            result.field_id,
            {
                get_static_config().stat_field_field_id: result.field_id,
                get_static_config().stat_field_field_name: result.field_name,
                get_static_config().stat_field_field_type: result.field_type,
                get_static_config().stat_field_attempted_templates: 0,
                get_static_config().stat_field_submittable: 0,
                get_static_config().stat_field_errors: 0,
                get_static_config().stat_field_queue_timeouts: 0,
                get_static_config().stat_field_failed_check_counts: {},
            },
        )
        if is_queue_timeout_result(result):
            summary[get_static_config().stat_field_queue_timeouts] += 1
            continue
        if result.status == get_static_config().status_skipped:
            continue

        summary[get_static_config().stat_field_attempted_templates] += 1
        if result.submittable:
            summary[get_static_config().stat_field_submittable] += 1
        if result.status == get_static_config().status_error:
            summary[get_static_config().stat_field_errors] += 1
        for check in result.failed_checks or []:
            name = check.name or get_static_config().sentinel_unknown_check
            summary[get_static_config().stat_field_failed_check_counts][name] = (
                summary[get_static_config().stat_field_failed_check_counts].get(name, 0) + 1
            )

    rows = list(grouped.values())
    for row in rows:
        counts = row[get_static_config().stat_field_failed_check_counts]
        row[get_static_config().stat_field_top_failed_checks] = sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[: get_static_config().stats_performance_top_n]
    return sorted(
        rows,
        key=lambda row: (
            -row[get_static_config().stat_field_submittable],
            -row[get_static_config().stat_field_attempted_templates],
            row[get_static_config().stat_field_field_id],
        ),
    )


def field_priority(field_id: str, field_feedback: FieldFeedbackMap) -> float:
    """返回字段在续跑排序中使用的历史优先级分数。"""
    summary: dict[str, Any] | None = field_feedback.get(field_id)
    if not summary:
        return get_static_config().stats_default_score
    best_score = float(summary.get("best_score", get_static_config().stats_default_score))
    attempted_templates = int(
        summary.get(get_static_config().stat_field_attempted_templates, 0) or 0
    )
    if (
        attempted_templates >= get_static_config().field_priority_attempted_high
        and best_score < get_static_config().field_priority_score_high
    ):
        return get_static_config().stats_default_score - float(attempted_templates)
    if (
        attempted_templates >= get_static_config().field_priority_attempted_low
        and best_score < get_static_config().field_priority_score_low
    ):
        return get_static_config().stats_default_score - float(attempted_templates)
    return best_score


def decay_field_feedback(
    summary: dict[str, Any] | None,
    *,
    half_life_days: int,
) -> dict[str, Any] | None:
    """Return a copy of feedback with stale best scores attenuated.

    The original summary remains unchanged so persisted history is lossless;
    callers can pass the returned view into template-stage decisions.
    """
    if summary is None:
        return None
    result = dict(summary)
    raw_score = float(
        result.get("best_score", get_static_config().stats_default_score)
        or get_static_config().stats_default_score
    )
    latest = result.get("latest_result_at")
    if half_life_days <= 0 or not latest:
        result["effective_best_score"] = raw_score
        return result
    try:
        observed = datetime.fromisoformat(str(latest).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        result["effective_best_score"] = raw_score
        return result
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    age_days = max(
        (datetime.now(timezone.utc) - observed).total_seconds() / 86400.0,
        0.0,
    )
    multiplier = pow(0.5, age_days / half_life_days)
    result["feedback_recency_multiplier"] = multiplier
    result["effective_best_score"] = raw_score * multiplier
    result["best_score"] = result["effective_best_score"]
    return result
