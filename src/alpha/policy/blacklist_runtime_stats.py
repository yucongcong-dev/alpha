"""Runtime aggregation helpers for learned blacklist signals."""

from __future__ import annotations

from ..config.constants import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
)
from ..models.domain import FieldTestResult
from ..models.result_predicates import is_informative_result
from .types import (
    BlacklistRuntimeStats,
    BlacklistRuntimeSummary,
    build_blacklist_entry_key,
)


def _get_runtime_summary(
    stats: BlacklistRuntimeStats,
    result: FieldTestResult,
) -> BlacklistRuntimeSummary:
    entry_key = build_blacklist_entry_key(
        result.template_name,
        result.field_type,
        result.template_stage,
        result.template_family,
    )
    if entry_key not in stats:
        stats[entry_key] = BlacklistRuntimeSummary(
            template_name=result.template_name,
            field_type=result.field_type,
            template_family=result.template_family,
            template_stage=result.template_stage,
            template_role=str(result.template_role or "").strip().lower(),
            template_activation_scope=str(result.template_activation_scope or "").strip().lower(),
        )
    return stats[entry_key]


def _record_failed_check(summary: BlacklistRuntimeSummary, check: object) -> None:
    get_value = getattr(check, "get", None)
    if not callable(get_value):
        return
    name = str(get_value("name", ""))
    value = get_value("value", None)
    if name == CHECK_LOW_SHARPE:
        summary.low_sharpe += 1
        if isinstance(value, (int, float)):
            summary.sharpe_sum += float(value)
            summary.sharpe_count += 1
    elif name == CHECK_LOW_FITNESS:
        summary.low_fitness += 1
        if isinstance(value, (int, float)):
            summary.fitness_sum += float(value)
            summary.fitness_count += 1
    elif name == CHECK_CONCENTRATED_WEIGHT:
        summary.concentrated_weight += 1


def update_blacklist_runtime_stats_with_result(
    stats: BlacklistRuntimeStats,
    result: FieldTestResult,
) -> BlacklistRuntimeSummary | None:
    """Merge one informative result into runtime blacklist summary stats."""
    if not is_informative_result(result):
        return None
    summary = _get_runtime_summary(stats, result)
    if not summary.template_role and result.template_role:
        summary.template_role = str(result.template_role).strip().lower()
    if not summary.template_activation_scope and result.template_activation_scope:
        summary.template_activation_scope = str(result.template_activation_scope).strip().lower()
    field_name = str(result.field_name or "")
    if field_name and field_name not in summary._field_names_seen:
        summary._field_names_seen.add(field_name)
        summary.fields_tested.append(field_name)
    if result.submittable:
        summary.submittable += 1
    for check in result.failed_checks or []:
        _record_failed_check(summary, check)
    return summary


def build_blacklist_runtime_stats(results: list[FieldTestResult]) -> BlacklistRuntimeStats:
    """Aggregate all informative results into blacklist runtime stats."""
    stats: BlacklistRuntimeStats = {}
    for result in results:
        update_blacklist_runtime_stats_with_result(stats, result)
    return stats
