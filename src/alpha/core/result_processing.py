"""
结果消费辅助模块。

承载 future 完成后的结果入状态、落盘与拥塞信号识别，
避免 scheduler 同时承担编排与细粒度状态处理职责。
"""

from __future__ import annotations

import logging

from ..analysis.result_identity import (
    is_informative_result,
    is_queue_timeout_result,
    result_identity,
)
from ..analysis.template_stats import update_template_stats_with_result
from ..config.constants import STATUS_ERROR, STATUS_SKIPPED
from ..models.domain import FieldTestResult
from ..runtime import ExecutionState, FutureCompletionContext
from ..policy import auto_update_blacklist_incremental, build_blacklist_runtime_stats

logger = logging.getLogger(__name__)


def detect_result_congestion(
    result: FieldTestResult,
) -> tuple[bool, str | None]:
    """识别单条结果中的拥塞信号和应跳过的字段。"""
    congestion_detected = False
    if "CONCURRENT_SIMULATION_LIMIT_EXCEEDED" in result.message:
        congestion_detected = True
    if isinstance(result.message, str) and "queued too long" in result.message.lower():
        congestion_detected = True
    if (
        result.failed_stage == "simulation"
        and isinstance(result.message, str)
        and "rate limited" in result.message.lower()
    ):
        congestion_detected = True
    queue_busy_field_id = None
    if result.failed_stage == "simulation" and isinstance(result.message, str):
        lowered = result.message.lower()
        if "queued too long" in lowered or "queue budget" in lowered:
            queue_busy_field_id = result.field_id
    return congestion_detected, queue_busy_field_id


def apply_result_state_updates(
    result: FieldTestResult,
    *,
    execution_state: ExecutionState,
    is_informative_result_fn,
    is_queue_timeout_result_fn,
    result_identity_fn,
    update_template_stats_with_result_fn,
) -> dict[str, dict[str, int]]:
    """Apply one completed result to execution counters and template stats."""
    execution_state.results.append(result)
    execution_state.unique_field_ids.add(result.field_id)
    if result.submittable:
        execution_state.submittable_count += 1
    if result.submitted:
        execution_state.submitted_count += 1
    if result.status == STATUS_ERROR:
        execution_state.error_count += 1
    if is_queue_timeout_result_fn(result):
        execution_state.queue_timeout_count += 1
    if is_informative_result_fn(result):
        execution_state.attempted_keys.add(result_identity_fn(result))
    template_stats = update_template_stats_with_result_fn(execution_state.template_stats, result)
    execution_state.template_stats = template_stats
    return template_stats


def log_completed_result(result: FieldTestResult) -> None:
    """Emit the canonical log line for one completed result."""
    if result.status == STATUS_ERROR:
        logger.error(
            "[result] field=%s template=%s status=ERROR message=%s",
            result.field_id,
            result.template_name,
            result.message,
        )
    elif result.status == STATUS_SKIPPED:
        logger.info(
            "[result] field=%s template=%s status=SKIPPED message=%s",
            result.field_id,
            result.template_name,
            result.message,
        )
    elif not result.submittable:
        logger.debug(
            "[result] field=%s template=%s status=%s submittable=%s message=%s",
            result.field_id,
            result.template_name,
            result.status,
            result.submittable,
            result.message,
        )
    else:
        logger.info(
            "[result] field=%s template=%s status=%s submittable=%s submitted=%s message=%s",
            result.field_id,
            result.template_name,
            result.status,
            result.submittable,
            result.submitted,
            result.message,
        )


def maybe_update_blacklist_incrementally(
    result: FieldTestResult,
    *,
    execution_state: ExecutionState,
    dataset_id: str,
    auto_update_enabled: bool,
    build_blacklist_runtime_stats_fn,
    auto_update_blacklist_incremental_fn,
) -> None:
    """Apply incremental blacklist side effects for one completed result if enabled."""
    if not auto_update_enabled:
        return
    if not execution_state.blacklist_runtime_stats and len(execution_state.results) > 1:
        execution_state.blacklist_runtime_stats = build_blacklist_runtime_stats_fn(
            execution_state.results[:-1]
        )
    auto_update_blacklist_incremental_fn(
        execution_state.blacklist_runtime_stats,
        execution_state.blacklisted_template_keys,
        result,
        dataset_id,
    )


def persist_incremental_result(
    result: FieldTestResult,
    *,
    completion_ctx: FutureCompletionContext,
    execution_state: ExecutionState,
    dump_results_incremental_fn,
) -> None:
    """Persist one completed result and updated counters to the journal/results store."""
    result_write_options = completion_ctx.result_write_options
    execution_state.persisted_result_count = dump_results_incremental_fn(
        result_write_options.output_path,
        result_write_options.dataset_id,
        [result],
        persisted_result_count=execution_state.persisted_result_count,
        tested=len(execution_state.results),
        unique_fields_tested=len(execution_state.unique_field_ids),
        submittable_count=execution_state.submittable_count,
        submitted_count=execution_state.submitted_count,
        error_count=execution_state.error_count,
        queue_timeout_count=execution_state.queue_timeout_count,
        settings_fingerprint=completion_ctx.settings_fingerprint,
        template_library_fingerprint=completion_ctx.template_library_fingerprint,
        run_config=completion_ctx.run_config,
        template_stats=execution_state.template_stats,
    )


def log_congestion_signals(result: FieldTestResult) -> None:
    """Emit warning logs for congestion-like failure patterns."""
    if "CONCURRENT_SIMULATION_LIMIT_EXCEEDED" in result.message:
        logger.warning(
            "[congestion] concurrent simulation limit exceeded for field=%s",
            result.field_id,
        )
    if isinstance(result.message, str) and "queued too long" in result.message.lower():
        logger.warning(
            "[congestion] queue timeout for field=%s template=%s",
            result.field_id,
            result.template_name,
        )


def apply_completed_result(
    result: FieldTestResult,
    *,
    completion_ctx: FutureCompletionContext,
    execution_state: ExecutionState,
    is_informative_result_fn=is_informative_result,
    is_queue_timeout_result_fn=is_queue_timeout_result,
    result_identity_fn=result_identity,
    update_template_stats_with_result_fn=update_template_stats_with_result,
    build_blacklist_runtime_stats_fn=build_blacklist_runtime_stats,
    auto_update_blacklist_incremental_fn=auto_update_blacklist_incremental,
    dump_results_incremental_fn=None,
) -> tuple[dict[str, dict[str, int]], bool, str | None]:
    """把单条结果并入执行状态，并执行增量持久化与策略副作用。"""
    result_write_options = completion_ctx.result_write_options
    template_stats = apply_result_state_updates(
        result,
        execution_state=execution_state,
        is_informative_result_fn=is_informative_result_fn,
        is_queue_timeout_result_fn=is_queue_timeout_result_fn,
        result_identity_fn=result_identity_fn,
        update_template_stats_with_result_fn=update_template_stats_with_result_fn,
    )
    log_completed_result(result)
    maybe_update_blacklist_incrementally(
        result,
        execution_state=execution_state,
        dataset_id=result_write_options.dataset_id,
        auto_update_enabled=result_write_options.auto_update_blacklist,
        build_blacklist_runtime_stats_fn=build_blacklist_runtime_stats_fn,
        auto_update_blacklist_incremental_fn=auto_update_blacklist_incremental_fn,
    )

    if dump_results_incremental_fn is None:
        from ..io.results_store import dump_results_incremental

        dump_results_incremental_fn = dump_results_incremental
    persist_incremental_result(
        result,
        completion_ctx=completion_ctx,
        execution_state=execution_state,
        dump_results_incremental_fn=dump_results_incremental_fn,
    )
    congestion_detected, queue_busy_field_id = detect_result_congestion(result)
    log_congestion_signals(result)
    return template_stats, congestion_detected, queue_busy_field_id
