"""字段反馈画像与全局失败检查计数。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config.constants import (
    SENTINEL_UNKNOWN_CHECK,
    STAT_FIELD_ATTEMPTED_TEMPLATES,
    STAT_FIELD_FAILED_CHECK_COUNTS,
    STAT_FIELD_FIELD_NAME,
    STATS_DEFAULT_SCORE,
    STATUS_SIMULATED,
)
from ..models.domain import FieldFeedbackMap, FieldTestResult
from .failed_checks import score_failed_checks
from .result_identity import is_queue_timeout_result


def compile_field_feedback(results: Sequence[FieldTestResult]) -> FieldFeedbackMap:
    """将历史接近通过的结果转为按字段组织的优化反馈。"""
    feedback: FieldFeedbackMap = {}
    for result in results:
        update_field_feedback_with_result(feedback, result)
    return feedback


def update_field_feedback_with_result(
    feedback: FieldFeedbackMap,
    result: FieldTestResult,
) -> FieldFeedbackMap:
    """将单条结果增量合并到字段反馈画像中。"""
    if is_queue_timeout_result(result):
        return feedback
    summary: dict[str, Any] = feedback.setdefault(
        result.field_id,
        {
            STAT_FIELD_FIELD_NAME: result.field_name,
            "best_score": STATS_DEFAULT_SCORE,
            "best_expression": "",
            "best_template_name": "",
            "best_template_family": "",
            "best_template_stage": "",
            STAT_FIELD_ATTEMPTED_TEMPLATES: 0,
            STAT_FIELD_FAILED_CHECK_COUNTS: {},
        },
    )
    current_attempted = summary.get(STAT_FIELD_ATTEMPTED_TEMPLATES, 0)
    summary[STAT_FIELD_ATTEMPTED_TEMPLATES] = int(current_attempted or 0) + 1
    for check in result.failed_checks or []:
        name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
        current_count = summary[STAT_FIELD_FAILED_CHECK_COUNTS].get(name, 0)
        summary[STAT_FIELD_FAILED_CHECK_COUNTS][name] = int(current_count or 0) + 1
    if result.status != STATUS_SIMULATED or not result.failed_checks:
        return feedback
    score = score_failed_checks(result.failed_checks)
    if score > summary["best_score"]:
        summary["best_score"] = score
        summary["best_expression"] = result.expression
        summary["best_template_name"] = result.template_name
        summary["best_template_family"] = result.template_family
        summary["best_template_stage"] = result.template_stage
    return feedback


def compile_global_failed_check_counts(results: Sequence[FieldTestResult]) -> dict[str, int]:
    """汇总所有历史结果中的失败检查计数，作为全局搜索方向。"""
    counts: dict[str, int] = {}
    for result in results:
        update_global_failed_check_counts_with_result(counts, result)
    return counts


def update_global_failed_check_counts_with_result(
    counts: dict[str, int],
    result: FieldTestResult,
) -> dict[str, int]:
    """将单条结果增量合并到全局失败检查计数中。"""
    if is_queue_timeout_result(result):
        return counts
    for check in result.failed_checks or []:
        name = str(check.get("name", SENTINEL_UNKNOWN_CHECK))
        counts[name] = counts.get(name, 0) + 1
    return counts


def dominant_failed_check_names(counts: dict[str, int], limit: int = 4) -> set[str]:
    """返回失败检查计数最高的若干名称。"""
    return {
        name
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        if count > 0
    }


def merge_failed_check_counts(*count_maps: dict[str, object]) -> dict[str, int]:
    """合并多个失败检查计数字典。"""
    merged: dict[str, int] = {}
    for count_map in count_maps:
        for name, count in count_map.items():
            if not isinstance(count, int):
                continue
            merged[str(name)] = merged.get(str(name), 0) + count
    return merged
