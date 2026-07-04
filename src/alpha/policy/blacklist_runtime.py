"""
黑名单运行态聚合与自动更新规则。
"""

from __future__ import annotations

import logging

from ..config.constants import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    DATE_FORMAT_ISO,
    DATE_FORMAT_ISO_MINUTES,
)
from ..config.models import DatasetExpressionPolicy
from ..models.domain import FieldTestResult
from .blacklist_store import (
    invalidate_blacklist_runtime_cache,
    read_blacklist_payload,
    write_blacklist_payload,
)
from .expression import get_dataset_expression_policy
from .types import BlacklistRuntimeStats, BlacklistRuntimeSummary, BlacklistTemplateEntry

logger = logging.getLogger(__name__)


def _update_blacklist_runtime_stats_with_result(
    stats: BlacklistRuntimeStats,
    result: FieldTestResult,
) -> BlacklistRuntimeSummary | None:
    from ..analysis.result_identity import is_informative_result

    if not is_informative_result(result):
        return None
    template_name = result.template_name
    if template_name not in stats:
        stats[template_name] = BlacklistRuntimeSummary(
            template_name=template_name,
            field_type=result.field_type,
            template_family=result.template_family,
            template_stage=result.template_stage,
        )
    summary = stats[template_name]
    field_name = str(result.field_name or "")
    if field_name and field_name not in summary._field_names_seen:
        summary._field_names_seen.add(field_name)
        summary.fields_tested.append(field_name)
    if result.submittable:
        summary.submittable += 1
    for check in result.failed_checks or []:
        name = str(check.get("name", "")) if isinstance(check, dict) else str(check.name)
        value = check.get("value") if isinstance(check, dict) else check.value
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
    return summary


def build_blacklist_runtime_stats(results: list[FieldTestResult]) -> BlacklistRuntimeStats:
    stats: BlacklistRuntimeStats = {}
    for result in results:
        _update_blacklist_runtime_stats_with_result(stats, result)
    return stats


def _build_blacklist_entry_from_runtime_summary(
    summary: BlacklistRuntimeSummary,
    *,
    dataset_id: str,
    policy: DatasetExpressionPolicy,
    min_fields_tested: int,
    min_fail_checks: int,
) -> BlacklistTemplateEntry | None:
    template_name = str(summary.template_name).strip()
    if not template_name or template_name in policy.protected_templates:
        return None
    fields_tested = list(summary.fields_tested)
    if len(fields_tested) < min_fields_tested:
        return None
    if summary.submittable > 0:
        return None
    low_sharpe_count = summary.low_sharpe
    low_fitness_count = summary.low_fitness
    concentrated_count = summary.concentrated_weight
    total_fails = low_sharpe_count + low_fitness_count
    if total_fails < min_fail_checks:
        return None
    sharpe_count = summary.sharpe_count
    fitness_count = summary.fitness_count
    avg_sharpe = (
        round(summary.sharpe_sum / sharpe_count, 3)
        if sharpe_count > 0
        else None
    )
    avg_fitness = (
        round(summary.fitness_sum / fitness_count, 3)
        if fitness_count > 0
        else None
    )
    if (
        policy.blacklist_min_fields_for_nearpass > 0
        and len(fields_tested) < policy.blacklist_min_fields_for_nearpass
        and (
            (avg_sharpe is not None and avg_sharpe >= policy.blacklist_protected_min_avg_sharpe)
            or (
                avg_fitness is not None
                and avg_fitness >= policy.blacklist_protected_min_avg_fitness
            )
        )
    ):
        return None
    reason_parts = [f"{len(fields_tested)}个字段测试均不通过"]
    if avg_sharpe is not None:
        reason_parts.append(f"平均 Sharpe {avg_sharpe:.3f}")
    if avg_fitness is not None:
        reason_parts.append(f"平均 Fitness {avg_fitness:.3f}")
    from datetime import datetime

    entry = BlacklistTemplateEntry(
        name=template_name,
        dataset_id=dataset_id,
        source="auto_detected",
        field_type=str(summary.field_type),
        template_family=str(summary.template_family),
        template_stage=str(summary.template_stage),
        reason="。".join(reason_parts) + "。",
        fields_tested=fields_tested,
        low_sharpe=low_sharpe_count,
        low_fitness=low_fitness_count,
        date_blacklisted=datetime.now().strftime(DATE_FORMAT_ISO),
        avg_sharpe=avg_sharpe,
        avg_fitness=avg_fitness,
        concentrated_weight=concentrated_count if concentrated_count else None,
    )
    return entry


def auto_update_blacklist(
    results: list[FieldTestResult],
    dataset_id: str,
    *,
    data_dir: str = "",
    min_fields_tested: int = 2,
    min_fail_checks: int = 2,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> None:
    if not dataset_id or not results:
        return
    from datetime import datetime

    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    runtime_stats = build_blacklist_runtime_stats(results)
    new_entries: list[BlacklistTemplateEntry] = []
    for summary in runtime_stats.values():
        entry = _build_blacklist_entry_from_runtime_summary(
            summary,
            dataset_id=dataset_id,
            policy=policy,
            min_fields_tested=min_fields_tested,
            min_fail_checks=min_fail_checks,
        )
        if entry is not None:
            new_entries.append(entry)
    if not new_entries:
        return

    bl_data = read_blacklist_payload(dataset_id, data_dir=data_dir)
    existing_names = {
        item["name"]
        for item in bl_data["blacklisted_templates"]
        if isinstance(item, dict) and item.get("name")
    }
    added = 0
    for entry in new_entries:
        if entry.name not in existing_names:
            bl_data["blacklisted_templates"].append(entry.to_dict())
            existing_names.add(entry.name)
            added += 1
    if added == 0:
        return

    bl_data["_updated"] = datetime.now().strftime(DATE_FORMAT_ISO_MINUTES)
    blacklist_path = write_blacklist_payload(dataset_id, bl_data, data_dir=data_dir)
    invalidate_blacklist_runtime_cache(dataset_id)
    logger.info(
        "[blacklist] auto-updated %s: added %d new entries (total=%d)",
        blacklist_path,
        added,
        len(bl_data["blacklisted_templates"]),
    )


def auto_update_blacklist_incremental(
    runtime_stats: BlacklistRuntimeStats,
    blacklisted_template_names: set[str],
    result: FieldTestResult,
    dataset_id: str,
    *,
    data_dir: str = "",
    min_fields_tested: int = 2,
    min_fail_checks: int = 2,
    expression_policy: DatasetExpressionPolicy | None = None,
) -> bool:
    if not dataset_id:
        return False
    from datetime import datetime

    policy = expression_policy or get_dataset_expression_policy(dataset_id)
    summary = _update_blacklist_runtime_stats_with_result(runtime_stats, result)
    if summary is None:
        return False
    template_name = str(summary.template_name).strip()
    if not template_name or template_name in blacklisted_template_names:
        return False
    entry = _build_blacklist_entry_from_runtime_summary(
        summary,
        dataset_id=dataset_id,
        policy=policy,
        min_fields_tested=min_fields_tested,
        min_fail_checks=min_fail_checks,
    )
    if entry is None:
        return False
    bl_data = read_blacklist_payload(dataset_id, data_dir=data_dir)
    existing_names = {
        item["name"]
        for item in bl_data["blacklisted_templates"]
        if isinstance(item, dict) and item.get("name")
    }
    if entry.name in existing_names:
        blacklisted_template_names.add(entry.name)
        return False
    bl_data["blacklisted_templates"].append(entry.to_dict())
    bl_data["_updated"] = datetime.now().strftime(DATE_FORMAT_ISO_MINUTES)
    blacklist_path = write_blacklist_payload(dataset_id, bl_data, data_dir=data_dir)
    invalidate_blacklist_runtime_cache(dataset_id)
    blacklisted_template_names.add(entry.name)
    logger.info(
        "[blacklist] incrementally added %s to %s (total=%d)",
        entry.name,
        blacklist_path,
        len(bl_data["blacklisted_templates"]),
    )
    return True
