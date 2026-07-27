"""
并发调度与拥塞控制模块

本模块负责并发任务调度、队列拥塞控制和任务结果处理，
包括动态调整并发数、拥塞冷却、任务节流等功能。

模块内容：
    - 已完成任务处理函数
    - 并发度动态调整函数
    - 队列拥塞跟踪函数
    - 任务节流函数
    - 批量结果消费函数
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import Future
import logging
import time
from typing import NamedTuple

from ..analysis.result_identity import (
    is_informative_result,
    is_queue_timeout_result,
    result_identity,
)
from ..analysis.template_stats import update_template_stats_with_result
from ..api.timing import wait_seconds
from ..models.domain import FieldTestResult
from ..models.runtime_options import ResultWriteOptions
from ..models.runtime_protocols import RunConfig, SchedulerRuntimeArgs
from ..runtime.contexts import FutureCompletionContext
from ..runtime.state import ExecutionState, RuntimeConcurrencyState
from .result_processing import apply_completed_result
from .scheduler_completion import (
    build_completion_context,
    resolve_completed_future_result,
)
from .scheduler_decisions import (
    DrainStateDecision,
    QueueBusyDecision,
    decide_drain_state_updates,
    decide_queue_busy_update,
    resolve_congestion_cooldown_until,
    should_restore_runtime_concurrency,
    submission_throttle_delay,
)

logger = logging.getLogger(__name__)


def _stop_after_submittable_threshold(args: SchedulerRuntimeArgs) -> int:
    try:
        return int(getattr(args, "stop_after_submittable", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _cancel_unstarted_pending_futures(execution_state: ExecutionState) -> None:
    for future, context in list(execution_state.pending_futures.items()):
        if future.cancel():
            execution_state.pending_futures.pop(future, None)
            logger.info(
                "[stop] cancelled queued future field=%s template=%s after stop-after-submittable",
                context.field_id,
                context.template_name,
            )


def _apply_queue_busy_decision(
    decision: QueueBusyDecision,
    *,
    skip_after: int,
    field_queue_busy_counts: dict[str, int],
    skipped_fields_due_to_queue: set[str],
) -> None:
    """Apply one queue-busy state decision and emit its transition log."""
    if not decision.should_register or decision.field_id is None:
        return
    field_queue_busy_counts[decision.field_id] = decision.next_count
    if decision.should_skip:
        skipped_fields_due_to_queue.add(decision.field_id)
        logger.info(
            "[skip] field=%s hit queue-busy limit %d/%d",
            decision.field_id,
            decision.next_count,
            skip_after,
        )


class DrainResult(NamedTuple):
    """批量结果消费的结果对象（不可变）"""

    template_stats: dict[str, dict[str, int]]
    congestion_detected: bool
    queue_busy_field_id: str | None


# ============================================================================
# 并发度、拥塞与节流兼容入口
# ============================================================================


def maybe_restore_runtime_concurrency(state: RuntimeConcurrencyState) -> None:
    """在拥塞冷却结束后恢复正常并发度。"""
    if should_restore_runtime_concurrency(
        cooldown_until=state.cooldown_until,
        runtime_max_workers=state.runtime_max_workers,
        max_workers=state.max_workers,
        now=time.monotonic(),
    ):
        state.runtime_max_workers = state.max_workers
        state.cooldown_until = 0.0
        logger.info(
            "[cooldown] restored runtime concurrency to %d",
            state.runtime_max_workers,
        )


def apply_congestion_cooldown(args: SchedulerRuntimeArgs, state: RuntimeConcurrencyState) -> None:
    """检测到拥塞后，临时切换到单 worker 运行模式。"""
    state.runtime_max_workers = 1
    state.cooldown_until = resolve_congestion_cooldown_until(
        now=time.monotonic(),
        cooldown_seconds=args.queue_busy_cooldown_seconds,
    )
    logger.info(
        "[cooldown] detected queue congestion, runtime concurrency -> 1 for %.0fs",
        args.queue_busy_cooldown_seconds,
    )


def register_queue_busy_field(
    field_id: str | None,
    args: SchedulerRuntimeArgs,
    field_queue_busy_counts: dict[str, int],
    skipped_fields_due_to_queue: set[str],
) -> None:
    """记录重复的排队拥塞字段，并在达到阈值后跳过该字段。"""
    decision = decide_queue_busy_update(
        field_id,
        current_count=field_queue_busy_counts.get(field_id or "", 0),
        skip_after=args.field_queue_busy_skip_after,
    )
    _apply_queue_busy_decision(
        decision,
        skip_after=args.field_queue_busy_skip_after,
        field_queue_busy_counts=field_queue_busy_counts,
        skipped_fields_due_to_queue=skipped_fields_due_to_queue,
    )


def throttle_before_submission(args: SchedulerRuntimeArgs, execution_state: ExecutionState) -> None:
    """在提交新任务前控制节奏，避免阻塞已完成任务处理。"""
    remaining = submission_throttle_delay(
        interval_seconds=args.sleep_between_fields,
        last_submission_at=execution_state.last_submission_at,
        now=time.monotonic(),
    )
    if remaining > 0:
        wait_seconds(remaining, "before next template submission")


def _apply_drain_state_decision(
    decision: DrainStateDecision,
    *,
    args: SchedulerRuntimeArgs,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
) -> None:
    """Apply a previously computed post-persistence scheduler decision."""
    if decision.activate_stop_signal:
        execution_state.stop_signal.set()
        _cancel_unstarted_pending_futures(execution_state)

    _apply_queue_busy_decision(
        decision.queue_busy,
        skip_after=args.field_queue_busy_skip_after,
        field_queue_busy_counts=execution_state.field_queue_busy_counts,
        skipped_fields_due_to_queue=execution_state.skipped_fields_due_to_queue,
    )

    if decision.apply_congestion_cooldown:
        apply_congestion_cooldown(args, runtime_state)


# ============================================================================
# 已完成任务处理函数
# ============================================================================


def handle_completed_future(
    future: Future[FieldTestResult],
    *,
    completion_ctx: FutureCompletionContext,
    execution_state: ExecutionState,
) -> DrainResult:
    """
    收尾一个 worker future，落盘结果并回传拥塞信号。

    处理已完成的异步任务，保存结果、更新统计数据，
    并检测拥塞信号。使用 FutureCompletionContext 将只读配置收敛为单个参数。

    Args:
        future: 已完成的 Future 对象。
        completion_ctx: 包含 args、settings_fingerprint、template_library_fingerprint、run_config 的上下文。
        execution_state: 执行状态对象（会被修改）。

    Returns:
        tuple[dict[str, dict[str, int]], bool, str | None]: 返回一个元组，包含：
            - template_stats: 更新后的模板统计数据
            - congestion_detected: 是否检测到拥塞
            - queue_busy_field_id: 队列拥塞的字段 ID（如果有）

    Note:
        - 结果立即落盘以防止中断丢失
        - 检测拥塞信号并返回给调用方
    """
    context = execution_state.pending_futures.pop(future)
    result = resolve_completed_future_result(
        future,
        context=context,
        template_library_fingerprint=completion_ctx.template_library_fingerprint,
    )

    template_stats, congestion_detected, queue_busy_field_id = apply_completed_result(
        result,
        completion_ctx=completion_ctx,
        execution_state=execution_state,
        is_informative_result_fn=is_informative_result,
        is_queue_timeout_result_fn=is_queue_timeout_result,
        result_identity_fn=result_identity,
        update_template_stats_with_result_fn=update_template_stats_with_result,
    )
    return DrainResult(template_stats, congestion_detected, queue_busy_field_id)


# ============================================================================
# 批量结果消费函数
# ============================================================================


def drain_completed_futures(
    *,
    completed_futures: Sequence[Future[FieldTestResult]],
    execution_state: ExecutionState,
    args: SchedulerRuntimeArgs,
    result_write_options: ResultWriteOptions | None = None,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: RunConfig | None,
    runtime_state: RuntimeConcurrencyState,
) -> dict[str, dict[str, int]]:
    """
    消费已完成的 future，落盘结果并更新队列退避状态。

    处理所有已完成的异步任务，更新结果和状态。

    Args:
        completed_futures: 已完成的 Future 序列。
        execution_state: ExecutionState 实例（会被修改）。
        args: 命令行参数。
        settings_fingerprint: 设置配置指纹。
        template_library_fingerprint: 模板库指纹。
        run_config: 运行配置。
        runtime_state: RuntimeConcurrencyState 实例（会被修改）。

    Returns:
        dict[str, dict[str, int]]: 更新后的模板统计数据。

    Note:
        - 对每个完成的 future 调用 handle_completed_future
        - 检测拥塞并应用冷却
        - 注册队列拥塞字段
    """
    completion_ctx = build_completion_context(
        args=args,
        result_write_options=result_write_options,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
    )
    return drain_completed_futures_with_context(
        completed_futures=completed_futures,
        execution_state=execution_state,
        args=args,
        completion_ctx=completion_ctx,
        runtime_state=runtime_state,
    )


def drain_completed_futures_with_context(
    *,
    completed_futures: Sequence[Future[FieldTestResult]],
    execution_state: ExecutionState,
    args: SchedulerRuntimeArgs,
    completion_ctx: FutureCompletionContext,
    runtime_state: RuntimeConcurrencyState,
) -> dict[str, dict[str, int]]:
    """Consume completed futures using a prebuilt immutable completion context."""
    for done_future in completed_futures:
        drain_result = handle_completed_future(
            done_future,
            completion_ctx=completion_ctx,
            execution_state=execution_state,
        )
        execution_state.template_stats = drain_result.template_stats
        current_submittable_count = execution_state.refresh_metrics().submittable_count
        queue_busy_field_id = drain_result.queue_busy_field_id
        decision = decide_drain_state_updates(
            stop_threshold=_stop_after_submittable_threshold(args),
            current_submittable_count=current_submittable_count,
            congestion_detected=drain_result.congestion_detected,
            queue_busy_field_id=queue_busy_field_id,
            current_queue_busy_count=execution_state.field_queue_busy_counts.get(
                queue_busy_field_id or "", 0
            ),
            queue_busy_skip_after=args.field_queue_busy_skip_after,
        )
        _apply_drain_state_decision(
            decision,
            args=args,
            execution_state=execution_state,
            runtime_state=runtime_state,
        )
    return execution_state.template_stats
