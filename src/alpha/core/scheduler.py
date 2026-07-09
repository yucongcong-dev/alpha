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
from dataclasses import dataclass
import logging
import time

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
from ..runtime import ExecutionState, FutureCompletionContext, PendingFutureContext, RuntimeConcurrencyState
from .result_processing import apply_completed_result
from .scheduler_completion import (
    apply_drain_feedback,
    build_completion_context,
    resolve_completed_future_result,
)

logger = logging.getLogger(__name__)


@dataclass
class DrainResult:
    """批量结果消费的结果对象（不可变）"""

    template_stats: dict[str, dict[str, int]]
    congestion_detected: bool
    queue_busy_field_id: str | None


# ============================================================================
# 并发度、拥塞与节流兼容入口
# ============================================================================


def maybe_restore_runtime_concurrency(state: RuntimeConcurrencyState) -> None:
    """在拥塞冷却结束后恢复正常并发度。"""
    if (
        state.cooldown_until
        and time.monotonic() >= state.cooldown_until
        and state.runtime_max_workers != state.max_workers
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
    state.cooldown_until = time.monotonic() + max(args.queue_busy_cooldown_seconds, 0.0)
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
    if not field_id or args.field_queue_busy_skip_after <= 0:
        return
    field_queue_busy_counts[field_id] = field_queue_busy_counts.get(field_id, 0) + 1
    if field_queue_busy_counts[field_id] >= args.field_queue_busy_skip_after:
        skipped_fields_due_to_queue.add(field_id)
        logger.info(
            "[skip] field=%s hit queue-busy limit %d/%d",
            field_id,
            field_queue_busy_counts[field_id],
            args.field_queue_busy_skip_after,
        )


def throttle_before_submission(args: SchedulerRuntimeArgs, execution_state: ExecutionState) -> None:
    """在提交新任务前控制节奏，避免阻塞已完成任务处理。"""
    if args.sleep_between_fields <= 0:
        return
    if execution_state.last_submission_at <= 0:
        return
    elapsed = time.monotonic() - execution_state.last_submission_at
    remaining = args.sleep_between_fields - elapsed
    if remaining > 0:
        wait_seconds(remaining, "before next template submission")


# ============================================================================
# 已完成任务处理函数
# ============================================================================


def handle_completed_future(
    future: Future[FieldTestResult],
    *,
    completion_ctx: FutureCompletionContext,
    execution_state: ExecutionState,
) -> tuple[dict[str, dict[str, int]], bool, str | None]:
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

    return apply_completed_result(
        result,
        completion_ctx=completion_ctx,
        execution_state=execution_state,
        is_informative_result_fn=is_informative_result,
        is_queue_timeout_result_fn=is_queue_timeout_result,
        result_identity_fn=result_identity,
        update_template_stats_with_result_fn=update_template_stats_with_result,
    )


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
    for done_future in completed_futures:
        execution_state.template_stats, congestion_detected, queue_busy_field_id = (
            handle_completed_future(
                done_future,
                completion_ctx=completion_ctx,
                execution_state=execution_state,
            )
        )
        apply_drain_feedback(
            args=args,
            execution_state=execution_state,
            runtime_state=runtime_state,
            congestion_detected=congestion_detected,
            queue_busy_field_id=queue_busy_field_id,
            register_queue_busy_field_fn=register_queue_busy_field,
            apply_congestion_cooldown_fn=apply_congestion_cooldown,
        )
    return execution_state.template_stats
