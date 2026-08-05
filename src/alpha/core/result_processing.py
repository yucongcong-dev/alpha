"""
结果消费辅助模块。

承载 future 完成后的结果入状态、落盘与拥塞信号识别，
避免 scheduler 同时承担编排与细粒度状态处理职责。
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
import logging
from typing import Any, Protocol

from ..analysis.result_identity import result_identity
from ..analysis.template_stats import update_template_stats_with_result
from ..config.constants import STATUS_ERROR, STATUS_SKIPPED
from ..models.domain import FieldTestResult
from ..models.result_predicates import is_attempted_result
from ..models.runtime_protocols import TemplateStats
from ..policy.blacklist_runtime_stats import build_blacklist_runtime_stats
from ..policy.blacklist_runtime_updates import auto_update_blacklist_incremental
from ..policy.types import BlacklistEntryKey, BlacklistRuntimeStats
from ..runtime.contexts import FutureCompletionContext
from ..runtime.state import ExecutionState

logger = logging.getLogger(__name__)

ResultIdentity = tuple[str, str, str, str]


class IncrementalResultsWriter(Protocol):
    """Persistence port for one incremental result batch."""

    def __call__(
        self,
        path: str,
        dataset_id: str,
        new_results: list[FieldTestResult],
        *,
        persisted_result_count: int,
        tested: int,
        unique_fields_tested: int,
        submittable_count: int,
        submitted_count: int,
        error_count: int,
        queue_timeout_count: int,
        settings_fingerprint: str,
        template_library_fingerprint: str,
        run_config: dict[str, Any] | None = None,
        template_registry_summary: list[dict[str, Any]] | None = None,
        template_stats: TemplateStats | None = None,
        pending_check_count: int = 0,
    ) -> int: ...


class IncrementalBlacklistUpdater(Protocol):
    """Policy side-effect port for one incremental blacklist candidate."""

    def __call__(
        self,
        runtime_stats: BlacklistRuntimeStats,
        blacklisted_template_keys: set[BlacklistEntryKey],
        result: FieldTestResult,
        dataset_id: str,
        *,
        update_mode: str = "repository",
    ) -> bool: ...


@dataclass(frozen=True)
class ResultProcessingServices:
    """Typed dependencies for state updates, policy effects, and persistence."""

    is_attempted_result: Callable[[FieldTestResult], bool]
    result_identity: Callable[[FieldTestResult], ResultIdentity]
    update_template_stats_with_result: Callable[[TemplateStats, FieldTestResult], TemplateStats]
    build_blacklist_runtime_stats: Callable[[list[FieldTestResult]], BlacklistRuntimeStats]
    auto_update_blacklist_incremental: IncrementalBlacklistUpdater
    dump_results_incremental: IncrementalResultsWriter


def build_result_processing_services() -> ResultProcessingServices:
    """Resolve current module/I/O dependencies so runtime overrides remain effective."""
    from ..analysis.results_persistence import dump_results_incremental

    return ResultProcessingServices(
        is_attempted_result=is_attempted_result,
        result_identity=result_identity,
        update_template_stats_with_result=update_template_stats_with_result,
        build_blacklist_runtime_stats=build_blacklist_runtime_stats,
        auto_update_blacklist_incremental=auto_update_blacklist_incremental,
        dump_results_incremental=dump_results_incremental,
    )


def detect_result_congestion(
    result: FieldTestResult,
) -> tuple[bool, ResultIdentity | None]:
    """识别单条结果中的全局拥塞信号和候选级队列超时。"""
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
    queue_busy_key = None
    if result.failed_stage == "simulation" and isinstance(result.message, str):
        lowered = result.message.lower()
        if "queued too long" in lowered or "queue budget" in lowered:
            queue_busy_key = result_identity(result)
    return congestion_detected, queue_busy_key


def apply_result_state_updates(
    result: FieldTestResult,
    *,
    execution_state: ExecutionState,
    services: ResultProcessingServices,
    template_stats: TemplateStats,
    persisted_result_count: int,
) -> TemplateStats:
    """Commit one result after its durable write has completed."""
    execution_state.result_ledger.append(result)
    execution_state.result_ledger.persisted_result_count = persisted_result_count
    if services.is_attempted_result(result):
        execution_state.attempted_keys.add(services.result_identity(result))
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
    auto_update_mode: str,
    services: ResultProcessingServices,
) -> None:
    """Apply incremental blacklist side effects for one completed result if enabled."""
    if not auto_update_enabled:
        return
    try:
        ledger = execution_state.result_ledger
        if not execution_state.blacklist_runtime_stats and len(ledger.results) > 1:
            execution_state.blacklist_runtime_stats = services.build_blacklist_runtime_stats(
                ledger.results[:-1]
            )
        services.auto_update_blacklist_incremental(
            execution_state.blacklist_runtime_stats,
            execution_state.blacklisted_template_keys,
            result,
            dataset_id,
            update_mode=auto_update_mode,
        )
    except Exception as exc:
        logger.warning(
            "[blacklist] incremental update failed for dataset=%s field=%s template=%s: %s",
            dataset_id,
            result.field_id,
            result.template_name,
            exc,
            exc_info=True,
        )


def persist_incremental_result(
    result: FieldTestResult,
    *,
    completion_ctx: FutureCompletionContext,
    execution_state: ExecutionState,
    services: ResultProcessingServices,
) -> tuple[int, TemplateStats]:
    """Persist one result using prospective counters without mutating runtime state."""
    result_write_options = completion_ctx.result_write_options
    ledger = execution_state.result_ledger
    metrics = ledger.metrics.with_result(result)
    prospective_template_stats = dict(execution_state.template_stats)
    existing_template_stats = prospective_template_stats.get(result.template_name)
    if existing_template_stats is not None:
        prospective_template_stats[result.template_name] = deepcopy(existing_template_stats)
    services.update_template_stats_with_result(prospective_template_stats, result)
    persisted_result_count = services.dump_results_incremental(
        result_write_options.output_path,
        result_write_options.dataset_id,
        [result],
        persisted_result_count=ledger.persisted_result_count,
        tested=len(ledger.results) + 1,
        unique_fields_tested=len(metrics.unique_field_ids),
        submittable_count=metrics.submittable_count,
        submitted_count=metrics.submitted_count,
        error_count=metrics.error_count,
        queue_timeout_count=metrics.queue_timeout_count,
        pending_check_count=metrics.pending_check_count,
        settings_fingerprint=completion_ctx.settings_fingerprint,
        template_library_fingerprint=completion_ctx.template_library_fingerprint,
        run_config=completion_ctx.run_config,
        template_stats=prospective_template_stats,
    )
    return persisted_result_count, prospective_template_stats


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
    services: ResultProcessingServices | None = None,
) -> tuple[TemplateStats, bool, ResultIdentity | None]:
    """把单条结果并入执行状态，并执行增量持久化与策略副作用。"""
    active_services = services or build_result_processing_services()
    result_write_options = completion_ctx.result_write_options
    persisted_result_count, prospective_template_stats = persist_incremental_result(
        result,
        completion_ctx=completion_ctx,
        execution_state=execution_state,
        services=active_services,
    )
    template_stats = apply_result_state_updates(
        result,
        execution_state=execution_state,
        services=active_services,
        template_stats=prospective_template_stats,
        persisted_result_count=persisted_result_count,
    )
    log_completed_result(result)
    maybe_update_blacklist_incrementally(
        result,
        execution_state=execution_state,
        dataset_id=result_write_options.dataset_id,
        auto_update_enabled=result_write_options.auto_update_blacklist,
        auto_update_mode=result_write_options.auto_update_blacklist_mode,
        services=active_services,
    )

    congestion_detected, queue_busy_key = detect_result_congestion(result)
    log_congestion_signals(result)
    return template_stats, congestion_detected, queue_busy_key
