"""Batch draining helpers for completed scheduler futures."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import Future
import logging
from typing import NamedTuple, Protocol

from ..models.domain import FieldTestResult
from ..models.runtime_options import ResultWriteOptions, SchedulerControlOptions
from ..models.runtime_protocols import RunConfig, TemplateStats
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import FutureCompletionContext
from ..runtime.queue_retry import QueueRetryKey
from ..runtime.state import ExecutionState
from . import scheduler_concurrency as _concurrency
from . import scheduler_queue as _queue
from .result_processing import apply_completed_result
from .scheduler_completion import build_completion_context, resolve_completed_future_result

logger = logging.getLogger(__name__)


class DrainResult(NamedTuple):
    """Result returned after one completed future is persisted."""

    template_stats: TemplateStats
    congestion_detected: bool
    queue_busy_key: QueueRetryKey | None


class CompletedFutureHandler(Protocol):
    """Persist one completed future and return its scheduler signals."""

    def __call__(
        self,
        future: Future[FieldTestResult],
        *,
        completion_ctx: FutureCompletionContext,
        execution_state: ExecutionState,
    ) -> DrainResult: ...


def handle_completed_future(
    future: Future[FieldTestResult],
    *,
    completion_ctx: FutureCompletionContext,
    execution_state: ExecutionState,
) -> DrainResult:
    """Persist one completed worker future and return scheduler signals.

    This is the canonical completion handler used by the draining helpers.
    Keeping it beside the batch drain logic avoids a second forwarding entry
    point in ``core.scheduler_draining`` and makes the callback dependency explicit for
    tests or alternative persistence implementations.
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


def drain_completed_futures(
    *,
    completed_futures: Sequence[Future[FieldTestResult]],
    execution_state: ExecutionState,
    scheduler_options: SchedulerControlOptions,
    result_write_options: ResultWriteOptions,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    run_config: RunConfig | None,
    runtime_state: RuntimeConcurrencyState,
    handle_completed: CompletedFutureHandler = handle_completed_future,
    log: logging.Logger = logger,
) -> TemplateStats:
    """Build completion context and consume completed worker futures."""
    completion_ctx = build_completion_context(
        result_write_options=result_write_options,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
    )
    return drain_completed_futures_with_context(
        completed_futures=completed_futures,
        execution_state=execution_state,
        scheduler_options=scheduler_options,
        completion_ctx=completion_ctx,
        runtime_state=runtime_state,
        handle_completed=handle_completed,
        log=log,
    )


def drain_completed_futures_with_context(
    *,
    completed_futures: Sequence[Future[FieldTestResult]],
    execution_state: ExecutionState,
    scheduler_options: SchedulerControlOptions,
    completion_ctx: FutureCompletionContext,
    runtime_state: RuntimeConcurrencyState,
    handle_completed: CompletedFutureHandler = handle_completed_future,
    log: logging.Logger = logger,
) -> TemplateStats:
    """Consume completed futures using a prebuilt immutable completion context."""
    for done_future in completed_futures:
        drain_result = handle_completed(
            done_future,
            completion_ctx=completion_ctx,
            execution_state=execution_state,
        )
        execution_state.template_stats = drain_result.template_stats
        if drain_result.congestion_detected:
            _concurrency.apply_congestion_cooldown(scheduler_options, runtime_state, log=log)
        _queue.register_queue_busy_template(
            drain_result.queue_busy_key, scheduler_options, execution_state
        )
    return execution_state.template_stats
