"""模板层统计与模板表现汇总。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..config.static_config import get_static_config
from ..models.domain import FieldTestResult
from ..models.result_predicates import has_pending_checks, is_queue_timeout_result


def _failed_check_counters() -> dict[str, str]:
    return {
        get_static_config().check_low_sharpe: get_static_config().stat_field_low_sharpe,
        get_static_config().check_low_fitness: get_static_config().stat_field_low_fitness,
        get_static_config().check_concentrated_weight: get_static_config().stat_field_concentrated_weight,
        get_static_config().check_low_sub_universe_sharpe: get_static_config().stat_field_low_sub_universe_sharpe,
    }


def _new_template_stat() -> dict[str, Any]:
    return {
        get_static_config().stat_field_attempted: 0,
        get_static_config().stat_field_submittable: 0,
        get_static_config().stat_field_errors: 0,
        get_static_config().stat_field_simulated: 0,
        get_static_config().stat_field_queue_timeouts: 0,
        get_static_config().stat_field_low_sharpe: 0,
        get_static_config().stat_field_low_fitness: 0,
        get_static_config().stat_field_concentrated_weight: 0,
        get_static_config().stat_field_low_sub_universe_sharpe: 0,
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
    failed_check_names = {check.name for check in result.failed_checks or []}
    for check_name, counter_name in _failed_check_counters().items():
        if check_name in failed_check_names:
            stat[counter_name] += 1


def _update_template_outcome_counts(stat: dict[str, Any], result: FieldTestResult) -> None:
    if is_queue_timeout_result(result):
        stat[get_static_config().stat_field_queue_timeouts] += 1
        return
    if result.status == get_static_config().status_skipped:
        return

    stat[get_static_config().stat_field_attempted] += 1
    if result.submittable:
        stat[get_static_config().stat_field_submittable] += 1
    if result.status == get_static_config().status_simulated:
        stat[get_static_config().stat_field_simulated] += 1
    if result.status == get_static_config().status_error:
        stat[get_static_config().stat_field_errors] += 1
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
                get_static_config().stat_field_template_name: result.template_name,
                get_static_config().stat_field_attempted: 0,
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

        summary[get_static_config().stat_field_attempted] += 1
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
            -row[get_static_config().stat_field_attempted],
            row[get_static_config().stat_field_template_name],
        ),
    )
