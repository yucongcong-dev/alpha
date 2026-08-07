"""字段层表现汇总与字段优先级。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from math import pow
from typing import Any

from ..config._constants_strings import (
    SENTINEL_UNKNOWN_CHECK,
    STAT_FIELD_ATTEMPTED_TEMPLATES,
    STAT_FIELD_ERRORS,
    STAT_FIELD_FAILED_CHECK_COUNTS,
    STAT_FIELD_FIELD_ID,
    STAT_FIELD_FIELD_NAME,
    STAT_FIELD_FIELD_TYPE,
    STAT_FIELD_QUEUE_TIMEOUTS,
    STAT_FIELD_SUBMITTABLE,
    STAT_FIELD_TOP_FAILED_CHECKS,
    STATUS_ERROR,
    STATUS_SKIPPED,
)
from ..config._constants_thresholds import (
    FIELD_PRIORITY_ATTEMPTED_HIGH,
    FIELD_PRIORITY_ATTEMPTED_LOW,
    FIELD_PRIORITY_SCORE_HIGH,
    FIELD_PRIORITY_SCORE_LOW,
    STATS_DEFAULT_SCORE,
    STATS_PERFORMANCE_TOP_N,
)
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
                STAT_FIELD_FIELD_ID: result.field_id,
                STAT_FIELD_FIELD_NAME: result.field_name,
                STAT_FIELD_FIELD_TYPE: result.field_type,
                STAT_FIELD_ATTEMPTED_TEMPLATES: 0,
                STAT_FIELD_SUBMITTABLE: 0,
                STAT_FIELD_ERRORS: 0,
                STAT_FIELD_QUEUE_TIMEOUTS: 0,
                STAT_FIELD_FAILED_CHECK_COUNTS: {},
            },
        )
        if is_queue_timeout_result(result):
            summary[STAT_FIELD_QUEUE_TIMEOUTS] += 1
            continue
        if result.status == STATUS_SKIPPED:
            continue

        summary[STAT_FIELD_ATTEMPTED_TEMPLATES] += 1
        if result.submittable:
            summary[STAT_FIELD_SUBMITTABLE] += 1
        if result.status == STATUS_ERROR:
            summary[STAT_FIELD_ERRORS] += 1
        for check in result.failed_checks or []:
            name = check.name or SENTINEL_UNKNOWN_CHECK
            summary[STAT_FIELD_FAILED_CHECK_COUNTS][name] = (
                summary[STAT_FIELD_FAILED_CHECK_COUNTS].get(name, 0) + 1
            )

    rows = list(grouped.values())
    for row in rows:
        counts = row[STAT_FIELD_FAILED_CHECK_COUNTS]
        row[STAT_FIELD_TOP_FAILED_CHECKS] = sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:STATS_PERFORMANCE_TOP_N]
    return sorted(
        rows,
        key=lambda row: (
            -row[STAT_FIELD_SUBMITTABLE],
            -row[STAT_FIELD_ATTEMPTED_TEMPLATES],
            row[STAT_FIELD_FIELD_ID],
        ),
    )


def field_priority(field_id: str, field_feedback: FieldFeedbackMap) -> float:
    """返回字段在续跑排序中使用的历史优先级分数。"""
    summary: dict[str, Any] | None = field_feedback.get(field_id)
    if not summary:
        return STATS_DEFAULT_SCORE
    best_score = float(summary.get("best_score", STATS_DEFAULT_SCORE))
    attempted_templates = int(summary.get(STAT_FIELD_ATTEMPTED_TEMPLATES, 0) or 0)
    if (
        attempted_templates >= FIELD_PRIORITY_ATTEMPTED_HIGH
        and best_score < FIELD_PRIORITY_SCORE_HIGH
    ):
        return STATS_DEFAULT_SCORE - float(attempted_templates)
    if (
        attempted_templates >= FIELD_PRIORITY_ATTEMPTED_LOW
        and best_score < FIELD_PRIORITY_SCORE_LOW
    ):
        return STATS_DEFAULT_SCORE - float(attempted_templates)
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
    raw_score = float(result.get("best_score", STATS_DEFAULT_SCORE) or STATS_DEFAULT_SCORE)
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
