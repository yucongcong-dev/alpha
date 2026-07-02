"""字段层表现汇总与字段优先级。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config import (
    SENTINEL_UNKNOWN_CHECK,
    STAT_FIELD_ATTEMPTED_TEMPLATES,
    STAT_FIELD_ERRORS,
    STAT_FIELD_FAILED_CHECK_COUNTS,
    STAT_FIELD_FIELD_ID,
    STAT_FIELD_FIELD_NAME,
    STAT_FIELD_FIELD_TYPE,
    STAT_FIELD_QUEUE_TIMEOUTS,
    STAT_FIELD_SUBMITTABLE,
    STAT_FIELD_SUBMITTED,
    STAT_FIELD_TOP_FAILED_CHECKS,
    STATS_DEFAULT_SCORE,
    STATS_PERFORMANCE_TOP_N,
    STATUS_ERROR,
)
from ..models.base import FieldFeedbackMap, FieldTestResult
from .result_identity import is_queue_timeout_result


def compile_field_performance_summary(results: Sequence[FieldTestResult]) -> list[dict[str, Any]]:
    """构建适合写入 JSON 的字段层表现汇总。"""
    grouped: dict[str, dict[str, Any]] = {}
    for result in results:
        summary = grouped.setdefault(
            result.field_id,
            {
                STAT_FIELD_FIELD_ID: result.field_id,
                STAT_FIELD_FIELD_NAME: result.field_name,
                STAT_FIELD_FIELD_TYPE: result.field_type,
                STAT_FIELD_ATTEMPTED_TEMPLATES: 0,
                STAT_FIELD_SUBMITTABLE: 0,
                STAT_FIELD_SUBMITTED: 0,
                STAT_FIELD_ERRORS: 0,
                STAT_FIELD_QUEUE_TIMEOUTS: 0,
                STAT_FIELD_FAILED_CHECK_COUNTS: {},
            },
        )
        if is_queue_timeout_result(result):
            summary[STAT_FIELD_QUEUE_TIMEOUTS] += 1
            continue
        summary[STAT_FIELD_ATTEMPTED_TEMPLATES] += 1
        if result.submittable:
            summary[STAT_FIELD_SUBMITTABLE] += 1
        if result.submitted:
            summary[STAT_FIELD_SUBMITTED] += 1
        if result.status == STATUS_ERROR:
            summary[STAT_FIELD_ERRORS] += 1
        for check in result.failed_checks or []:
            name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
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
            -row[STAT_FIELD_SUBMITTED],
            -row[STAT_FIELD_ATTEMPTED_TEMPLATES],
            row[STAT_FIELD_FIELD_ID],
        ),
    )


def field_priority(field_id: str, field_feedback: FieldFeedbackMap) -> float:
    """返回字段在续跑排序中使用的历史优先级分数。"""
    summary = field_feedback.get(field_id)
    if not summary:
        return STATS_DEFAULT_SCORE
    best_score = float(summary.get("best_score", STATS_DEFAULT_SCORE))
    attempted_templates = int(summary.get(STAT_FIELD_ATTEMPTED_TEMPLATES, 0))
    if attempted_templates >= 8 and best_score < 0.70:
        return STATS_DEFAULT_SCORE - float(attempted_templates)
    if attempted_templates >= 5 and best_score < 0.40:
        return STATS_DEFAULT_SCORE - float(attempted_templates)
    return best_score


def current_submittable_count(results: Sequence[FieldTestResult]) -> int:
    """统计当前结果集中已经可提交的 Alpha 数量。"""
    return sum(1 for result in results if result.submittable)
