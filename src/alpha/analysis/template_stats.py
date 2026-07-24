"""模板层统计、历史优先级和模板表现汇总。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config.constants import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_SUB_UNIVERSE_SHARPE,
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
    STAT_FIELD_SUBMITTED,
    STAT_FIELD_TEMPLATE_NAME,
    STAT_FIELD_TOP_FAILED_CHECKS,
    STATS_PERFORMANCE_TOP_N,
    STATUS_ERROR,
    STATUS_SKIPPED,
    STATUS_SIMULATED,

    TEMPLATE_HISTORY_CONCENTRATED_PENALTY,
    TEMPLATE_HISTORY_ERROR_PENALTY,
    TEMPLATE_HISTORY_LOW_PERF_PENALTY,
    TEMPLATE_HISTORY_SIMULATED_BASE,
    TEMPLATE_HISTORY_SIMULATED_CAP,
    TEMPLATE_HISTORY_SIMULATED_STEP,
    TEMPLATE_HISTORY_SUBMITTABLE_BONUS,
)
from ..models.domain import FieldTestResult
from .result_identity import is_queue_timeout_result


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
    stat = stats.setdefault(
        result.template_name,
        {
            STAT_FIELD_ATTEMPTED: 0,
            STAT_FIELD_SUBMITTABLE: 0,
            STAT_FIELD_SUBMITTED: 0,
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
        },
    )

    if result.template_family and "template_family" not in stat:
        stat["template_family"] = result.template_family
    if result.template_stage:
        stat["template_stage"] = result.template_stage
    if result.template_role:
        stat["template_role"] = result.template_role
        role_counts = stat.setdefault("role_counts", {})
        role_counts[result.template_role] = int(role_counts.get(result.template_role, 0)) + 1
    if result.template_activation_scope:
        stat["template_activation_scope"] = result.template_activation_scope
        scope_counts = stat.setdefault("scope_counts", {})
        scope_counts[result.template_activation_scope] = (
            int(scope_counts.get(result.template_activation_scope, 0)) + 1
        )
    if is_queue_timeout_result(result):
        stat[STAT_FIELD_QUEUE_TIMEOUTS] += 1
        return stats
    if result.status == STATUS_SKIPPED:
        return stats
    stat[STAT_FIELD_ATTEMPTED] += 1
    if result.submittable:
        stat[STAT_FIELD_SUBMITTABLE] += 1
    if result.submitted:
        stat[STAT_FIELD_SUBMITTED] += 1
    if result.status == STATUS_SIMULATED:
        stat[STAT_FIELD_SIMULATED] += 1
    if result.status == STATUS_ERROR:
        stat[STAT_FIELD_ERRORS] += 1
    failed_check_names = {str(check.get("name", "")) for check in result.failed_checks or []}
    if CHECK_LOW_SHARPE in failed_check_names:
        stat[STAT_FIELD_LOW_SHARPE] += 1
    if CHECK_LOW_FITNESS in failed_check_names:
        stat[STAT_FIELD_LOW_FITNESS] += 1
    if CHECK_CONCENTRATED_WEIGHT in failed_check_names:
        stat[STAT_FIELD_CONCENTRATED_WEIGHT] += 1
    if CHECK_LOW_SUB_UNIVERSE_SHARPE in failed_check_names:
        stat[STAT_FIELD_LOW_SUB_UNIVERSE_SHARPE] += 1
    return stats


def historical_template_priority_bonus(
    template_name: str,
    template_stats: dict[str, dict[str, int]],
    multiplier: int = 1,
) -> int:
    """为历史上模拟成功或通过检查的模板提供优先级奖励。"""
    stat = template_stats.get(template_name)
    if not stat:
        return 0
    if stat[STAT_FIELD_SUBMITTABLE] > 0:
        return TEMPLATE_HISTORY_SUBMITTABLE_BONUS * multiplier
    if stat[STAT_FIELD_SIMULATED] > 0:
        bonus = TEMPLATE_HISTORY_SIMULATED_BASE + min(stat[STAT_FIELD_SIMULATED], TEMPLATE_HISTORY_SIMULATED_CAP) * TEMPLATE_HISTORY_SIMULATED_STEP
        if stat.get(STAT_FIELD_SUBMITTABLE, 0) == 0 and stat.get(STAT_FIELD_SIMULATED, 0) >= 3:
            if stat.get(STAT_FIELD_LOW_SHARPE, 0) >= 3 and stat.get(STAT_FIELD_LOW_FITNESS, 0) >= 3:
                bonus += TEMPLATE_HISTORY_LOW_PERF_PENALTY
            if stat.get(STAT_FIELD_CONCENTRATED_WEIGHT, 0) >= 2:
                bonus += TEMPLATE_HISTORY_CONCENTRATED_PENALTY
        return bonus * multiplier
    if stat[STAT_FIELD_ERRORS] >= 3 and stat[STAT_FIELD_SIMULATED] == 0:
        return TEMPLATE_HISTORY_ERROR_PENALTY * multiplier
    return 0


def compile_template_performance_summary(
    results: Sequence[FieldTestResult],
) -> list[dict[str, Any]]:
    """构建适合写入 JSON 的模板层表现汇总。"""
    grouped: dict[str, dict[str, Any]] = {}
    for result in results:
        summary = grouped.setdefault(
            result.template_name,
            {
                STAT_FIELD_TEMPLATE_NAME: result.template_name,
                STAT_FIELD_ATTEMPTED: 0,
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
        if result.status == STATUS_SKIPPED:
            continue

        summary[STAT_FIELD_ATTEMPTED] += 1
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
            -row[STAT_FIELD_ATTEMPTED],
            row[STAT_FIELD_TEMPLATE_NAME],
        ),
    )
