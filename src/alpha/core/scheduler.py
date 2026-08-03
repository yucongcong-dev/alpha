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
from typing import NamedTuple

from ..api.timing import wait_seconds
from ..models.domain import FieldTestResult
from ..models.runtime_options import ResultWriteOptions, SchedulerControlOptions
from ..models.runtime_protocols import RunConfig, SchedulerRuntimeArgs, TemplateStats
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import FutureCompletionContext
from ..runtime.queue_retry import QueueRetryKey
from ..runtime.state import ExecutionState
from . import scheduler_concurrency as _concurrency
from . import scheduler_queue as _queue
from .result_processing import apply_completed_result
from .scheduler_completion import (
    build_completion_context,
    resolve_completed_future_result,
)
from .scheduler_decisions import (
    DrainStateDecision,
    decide_drain_state_updates,
)

__all__ = [
    "apply_congestion_cooldown",
    "drain_completed_futures",
    "drain_completed_futures_with_context",
    "handle_completed_future",
    "maybe_restore_runtime_concurrency",
    "register_queue_busy_field",
    "register_queue_busy_template",
    "throttle_before_submission",
]

logger = logging.getLogger(__name__)

_apply_queue_busy_decision = _queue.apply_queue_busy_decision
_scheduler_control_options = _queue.scheduler_control_options
register_queue_busy_field = _queue.register_queue_busy_field
register_queue_busy_template = _queue.register_queue_busy_template


def _stop_after_submittable_threshold(options: SchedulerControlOptions) -> int:
    try:
        return int(options.stop_after_submittable or 0)
    except (TypeError, ValueError):
        return 0


def _cancel_unstarted_pending_futures(execution_state: ExecutionState) -> None:
    for future, context in list(execution_state.future_queue.pending_futures.items()):
        if future.cancel():
            execution_state.future_queue.pending_futures.pop(future, None)
            logger.info(
                "[stop] cancelled queued future field=%s template=%s after stop-after-submittable",
                context.field_id,
                context.template_name,
            )


class DrainResult(NamedTuple):
    """批量结果消费的结果对象（不可变）"""

    template_stats: TemplateStats
    congestion_detected: bool
    queue_busy_key: QueueRetryKey | None


# ============================================================================
# 并发度、拥塞与节流兼容入口
# ============================================================================


def maybe_restore_runtime_concurrency(state: RuntimeConcurrencyState) -> None:
    """在拥塞冷却结束后恢复正常并发度。"""
    _concurrency.maybe_restore_runtime_concurrency(state, log=logger)


def apply_congestion_cooldown(
    args: SchedulerRuntimeArgs | SchedulerControlOptions,
    state: RuntimeConcurrencyState,
) -> None:
    """检测到拥塞后，临时切换到单 worker 运行模式。"""
    options = _scheduler_control_options(args)
    _concurrency.apply_congestion_cooldown(options, state, log=logger)


def throttle_before_submission(
    args: SchedulerRuntimeArgs | SchedulerControlOptions,
    execution_state: ExecutionState,
) -> None:
    """在提交新任务前控制节奏，避免阻塞已完成任务处理。"""
    options = _scheduler_control_options(args)
    _concurrency.throttle_before_submission(options, execution_state, wait=wait_seconds)


def _apply_drain_state_decision(
    decision: DrainStateDecision,
    *,
    scheduler_options: SchedulerControlOptions,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
) -> None:
    """Apply a previously computed post-persistence scheduler decision."""
    if decision.activate_stop_signal:
        execution_state.future_queue.stop_signal.set()
        _cancel_unstarted_pending_futures(execution_state)

    _apply_queue_busy_decision(
        decision.queue_busy,
        skip_after=scheduler_options.field_queue_busy_skip_after,
        field_queue_busy_counts=execution_state.field_queue.busy_counts,
        skipped_fields_due_to_queue=execution_state.field_queue.skipped_fields,
    )

    if decision.apply_congestion_cooldown:
        apply_congestion_cooldown(scheduler_options, runtime_state)


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
        DrainResult: 返回已更新的模板统计和拥塞信息：
            - template_stats: 更新后的模板统计数据
            - congestion_detected: 是否检测到拥塞
            - queue_busy_key: 队列超时的候选身份（如果有）

    Note:
        - 结果立即落盘以防止中断丢失
        - 检测拥塞信号并返回给调用方
    """
    context = execution_state.future_queue.pending_futures[future]
    result = resolve_completed_future_result(
        future,
        context=context,
        template_library_fingerprint=completion_ctx.template_library_fingerprint,
    )

    template_stats, congestion_detected, queue_busy_key = apply_completed_result(
        result,
        completion_ctx=completion_ctx,
        execution_state=execution_state,
    )
    execution_state.future_queue.pop_completed(future)
    return DrainResult(template_stats, congestion_detected, queue_busy_key)


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
) -> TemplateStats:
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
    scheduler_options = SchedulerControlOptions.from_args(args)
    return drain_completed_futures_with_context(
        completed_futures=completed_futures,
        execution_state=execution_state,
        args=scheduler_options,
        completion_ctx=completion_ctx,
        runtime_state=runtime_state,
    )


def drain_completed_futures_with_context(
    *,
    completed_futures: Sequence[Future[FieldTestResult]],
    execution_state: ExecutionState,
    args: SchedulerRuntimeArgs | SchedulerControlOptions,
    completion_ctx: FutureCompletionContext,
    runtime_state: RuntimeConcurrencyState,
) -> TemplateStats:
    """Consume completed futures using a prebuilt immutable completion context."""
    scheduler_options = _scheduler_control_options(args)
    for done_future in completed_futures:
        drain_result = handle_completed_future(
            done_future,
            completion_ctx=completion_ctx,
            execution_state=execution_state,
        )
        execution_state.template_stats = drain_result.template_stats
        current_submittable_count = execution_state.result_ledger.current_run_submittable_count
        # Queue timeouts are tracked per candidate below. Keep the shared
        # decision helper focused here on stop/cooldown state only.
        decision = decide_drain_state_updates(
            stop_threshold=_stop_after_submittable_threshold(scheduler_options),
            current_submittable_count=current_submittable_count,
            congestion_detected=drain_result.congestion_detected,
            queue_busy_field_id=None,
            current_queue_busy_count=0,
            queue_busy_skip_after=scheduler_options.field_queue_busy_skip_after,
        )
        _apply_drain_state_decision(
            decision,
            scheduler_options=scheduler_options,
            execution_state=execution_state,
            runtime_state=runtime_state,
        )
        register_queue_busy_template(
            drain_result.queue_busy_key, scheduler_options, execution_state
        )
    return execution_state.template_stats
