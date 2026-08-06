"""结果身份、续跑去重与有效反馈判断。

核心谓词已移至 models.result_predicates 以打破 policy ↔ analysis 循环依赖。
本模块保留旧导入路径兼容，并补充仅 analysis 内部使用的聚合函数。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from ..models.domain import FieldTestResult
from ..models.result_predicates import (
    is_attempted_result,
    is_retryable_infrastructure_result,
)
from ..models.result_predicates import (
    is_informative_result as is_informative_result,
)
from ..models.result_predicates import (
    is_queue_timeout_result as is_queue_timeout_result,
)


def result_identity(result: FieldTestResult) -> tuple[str, str, str, str]:
    """返回单次字段-模板-settings 尝试的稳定去重键。"""
    return (
        result.field_id,
        result.template_name,
        result.expression,
        result.settings_fingerprint,
    )


def attempted_template_keys(results: Sequence[FieldTestResult]) -> set[tuple[str, str, str, str]]:
    """收集已经持久化记录过的模板尝试键集合。"""
    return {result_identity(result) for result in results if is_attempted_result(result)}


def merge_results_by_identity(
    *result_groups: Sequence[FieldTestResult],
) -> list[FieldTestResult]:
    """Compatibility wrapper for latest-authoritative history merging."""
    return merge_latest_results_by_identity(*result_groups)


def merge_latest_results_by_identity(
    *result_groups: Sequence[FieldTestResult],
) -> list[FieldTestResult]:
    """Merge histories using the latest authoritative observation per identity."""
    merged: dict[tuple[str, str, str, str], FieldTestResult] = {}
    for group in result_groups:
        for result in group:
            identity = result_identity(result)
            existing = merged.get(identity)
            if existing is None or _should_replace_with_observation(existing, result):
                merged[identity] = result
    return list(merged.values())


def merge_results_for_update(
    existing_results: Sequence[FieldTestResult],
    updates: Sequence[FieldTestResult],
) -> list[FieldTestResult]:
    """Apply new records and advance revision only for persisted replacements."""
    merged = {result_identity(result): result for result in existing_results}
    for update in updates:
        identity = result_identity(update)
        existing = merged.get(identity)
        if existing is None:
            merged[identity] = update
            continue
        if is_retryable_infrastructure_result(update) and not is_retryable_infrastructure_result(
            existing
        ):
            continue
        merged[identity] = replace(
            update,
            revision=max(update.revision, existing.revision + 1),
        )
    return list(merged.values())


def _parse_timestamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _terminal_rank(result: FieldTestResult) -> int:
    """Rank durable outcomes above transient or incomplete observations."""
    if result.submittable is True:
        return 40
    status = result.status.strip().lower()
    if status == "simulated" and result.submittable is False:
        return 30
    if status == "simulated":
        return 25
    if status == "error":
        return 20
    if status == "skipped":
        return 0
    return 10


def _observation_preference(result: FieldTestResult) -> tuple[float, int, int]:
    return (
        max(_parse_timestamp(result.updated_at), _parse_timestamp(result.created_at)),
        max(1, int(result.revision or 1)),
        _terminal_rank(result),
    )


def _should_replace_with_observation(
    existing: FieldTestResult,
    candidate: FieldTestResult,
) -> bool:
    existing_retryable = is_retryable_infrastructure_result(existing)
    candidate_retryable = is_retryable_infrastructure_result(candidate)
    if candidate_retryable != existing_retryable:
        return not candidate_retryable
    return _observation_preference(candidate) >= _observation_preference(existing)
