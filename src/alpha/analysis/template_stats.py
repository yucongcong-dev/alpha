"""模板层统计与模板表现汇总。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config._constants_strings import (
    SENTINEL_UNKNOWN_CHECK,
    STAT_FIELD_ATTEMPTED,
    STAT_FIELD_CONCENTRATED_WEIGHT,
    STAT_FIELD_ERRORS,
    STAT_FIELD_FAILED_CHECK_COUNTS,
    STAT_FIELD_LOW_FITNESS,
    STAT_FIELD_LOW_SHARPE,
    STAT_FIELD_LOW_SUB_UNIVERSE_SHARPE,
    STAT_FIELD_QUEUE_TIMEOUTS,
    STAT_FIELD_SIMULATED,
    STAT_FIELD_SUBMITTABLE,
    STAT_FIELD_TEMPLATE_NAME,
    STAT_FIELD_TOP_FAILED_CHECKS,
    STATUS_ERROR,
    STATUS_SIMULATED,
    STATUS_SKIPPED,
)
from ..config._constants_thresholds import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
    STATS_PERFORMANCE_TOP_N,
)
from ..models.domain import FieldTestResult
from ..models.result_predicates import has_pending_checks, is_queue_timeout_result

_FAILED_CHECK_COUNTERS = {
    CHECK_LOW_SHARPE: STAT_FIELD_LOW_SHARPE,
    CHECK_LOW_FITNESS: STAT_FIELD_LOW_FITNESS,
    CHECK_CONCENTRATED_WEIGHT: STAT_FIELD_CONCENTRATED_WEIGHT,
    CHECK_LOW_SUB_UNIVERSE_SHARPE: STAT_FIELD_LOW_SUB_UNIVERSE_SHARPE,
}


def _new_template_stat() -> dict[str, Any]:
    return {
        STAT_FIELD_ATTEMPTED: 0,
        STAT_FIELD_SUBMITTABLE: 0,
        STAT_FIELD_ERRORS: 0,
        STAT_FIELD_SIMULATED: 0,
        STAT_FIELD_QUEUE_TIMEOUTS: 0,
        STAT_FIELD_LOW_SHARPE: 0,
        STAT_FIELD_LOW_FITNESS: 0,
        STAT_FIELD_CONCENTRATED_WEIGHT: 0,
        STAT_FIELD_LOW_SUB_UNIVERSE_SHARPE: 0,
        "template_stage": "",
        "template_role": "",
        "template_activation_scope": "",
        "role_counts": {},
        "scope_counts": {},
    }


def _increment_grouped_value(stat: dict[str, Any], counter_name: str, value: str) -> None:
    counters = stat.setdefault(counter_name, {})
    counters[value] = int(counters.get(value, 0)) + 1


def _update_template_metadata(stat: dict[str, Any], result: FieldTestResult) -> None:
    if result.template_family and "template_family" not in stat:
        stat["template_family"] = result.template_family
    if result.template_stage:
        stat["template_stage"] = result.template_stage
    if result.template_role:
        stat["template_role"] = result.template_role
        _increment_grouped_value(stat, "role_counts", result.template_role)
    if result.template_activation_scope:
        stat["template_activation_scope"] = result.template_activation_scope
        _increment_grouped_value(stat, "scope_counts", result.template_activation_scope)


def _update_failed_check_counts(stat: dict[str, Any], result: FieldTestResult) -> None:
    failed_check_names = {str(check.get("name", "")) for check in result.failed_checks or []}
    for check_name, counter_name in _FAILED_CHECK_COUNTERS.items():
        if check_name in failed_check_names:
            stat[counter_name] += 1


def _update_template_outcome_counts(stat: dict[str, Any], result: FieldTestResult) -> None:
    if is_queue_timeout_result(result):
        stat[STAT_FIELD_QUEUE_TIMEOUTS] += 1
        return
    if result.status == STATUS_SKIPPED:
        return

    stat[STAT_FIELD_ATTEMPTED] += 1
    if result.submittable:
        stat[STAT_FIELD_SUBMITTABLE] += 1
    if result.status == STATUS_SIMULATED:
        stat[STAT_FIELD_SIMULATED] += 1
    if result.status == STATUS_ERROR:
        stat[STAT_FIELD_ERRORS] += 1
    _update_failed_check_counts(stat, result)


def compile_template_stats(results: Sequence[FieldTestResult]) -> dict[str, dict[str, Any]]:
    """按模板名聚合历史上的粗粒度统计信息。"""
    stats: dict[str, dict[str, Any]] = {}
    for result in results:
        update_template_stats_with_result(stats, result)
    return stats


def update_template_stats_with_result(
    stats: dict[str, dict[str, Any]],
    result: FieldTestResult,
) -> dict[str, dict[str, Any]]:
    """将单条结果增量合并到模板统计中。"""
    if has_pending_checks(result):
        return stats
    stat = stats.setdefault(result.template_name, _new_template_stat())
    _update_template_metadata(stat, result)
    _update_template_outcome_counts(stat, result)
    return stats


def compile_template_performance_summary(
    results: Sequence[FieldTestResult],
) -> list[dict[str, Any]]:
    """构建适合写入 JSON 的模板层表现汇总。"""
    grouped: dict[str, dict[str, Any]] = {}
    for result in results:
        if has_pending_checks(result):
            continue
        summary = grouped.setdefault(
            result.template_name,
            {
                STAT_FIELD_TEMPLATE_NAME: result.template_name,
                STAT_FIELD_ATTEMPTED: 0,
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

        summary[STAT_FIELD_ATTEMPTED] += 1
        if result.submittable:
            summary[STAT_FIELD_SUBMITTABLE] += 1
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
            -row[STAT_FIELD_ATTEMPTED],
            row[STAT_FIELD_TEMPLATE_NAME],
        ),
    )
