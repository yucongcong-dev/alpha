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

from ..api.timing import wait_seconds
from ..models.domain import FieldTestResult
from ..models.runtime_options import ResultWriteOptions, SchedulerControlOptions
from ..models.runtime_protocols import RunConfig, SchedulerRuntimeArgs, TemplateStats
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import FutureCompletionContext
from ..runtime.state import ExecutionState
from . import scheduler_concurrency as _concurrency
from . import scheduler_draining as _draining
from . import scheduler_queue as _queue
from .result_processing import apply_completed_result
from .scheduler_completion import resolve_completed_future_result

__all__ = [
    "apply_congestion_cooldown",
    "drain_completed_futures",
    "drain_completed_futures_with_context",
    "handle_completed_future",
    "maybe_restore_runtime_concurrency",
    "register_queue_busy_template",
    "throttle_before_submission",
]

logger = logging.getLogger(__name__)

_scheduler_control_options = _queue.scheduler_control_options
register_queue_busy_template = _queue.register_queue_busy_template


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


# ============================================================================
# 已完成任务处理函数
# ============================================================================


def handle_completed_future(
    future: Future[FieldTestResult],
    *,
    completion_ctx: FutureCompletionContext,
    execution_state: ExecutionState,
) -> _draining.DrainResult:
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
    return _draining.DrainResult(template_stats, congestion_detected, queue_busy_key)


# ============================================================================
# 批量结果消费函数
# ============================================================================


def drain_completed_futures(
    *,
    completed_futures: Sequence[Future[FieldTestResult]],
    execution_state: ExecutionState,
    args: SchedulerRuntimeArgs,
    result_write_options: ResultWriteOptions,
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
    return _draining.drain_completed_futures(
        completed_futures=completed_futures,
        execution_state=execution_state,
        args=args,
        result_write_options=result_write_options,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
        runtime_state=runtime_state,
        handle_completed=handle_completed_future,
        log=logger,
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
    return _draining.drain_completed_futures_with_context(
        completed_futures=completed_futures,
        execution_state=execution_state,
        args=args,
        completion_ctx=completion_ctx,
        runtime_state=runtime_state,
        handle_completed=handle_completed_future,
        log=logger,
    )
