"""Batch draining helpers for completed scheduler futures."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import Future
import logging
from typing import NamedTuple, Protocol

from ..models.domain import FieldTestResult
from ..models.runtime_options import ResultWriteOptions, SchedulerControlOptions
from ..models.runtime_protocols import RunConfig, SchedulerRuntimeArgs, TemplateStats
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import FutureCompletionContext
from ..runtime.queue_retry import QueueRetryKey
from ..runtime.state import ExecutionState
from . import scheduler_drain_state as _drain_state
from . import scheduler_queue as _queue
from .scheduler_completion import build_completion_context
from .scheduler_decisions import decide_drain_state_updates

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
    handle_completed: CompletedFutureHandler,
    log: logging.Logger = logger,
) -> TemplateStats:
    """Build completion context and consume completed worker futures."""
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
        handle_completed=handle_completed,
        log=log,
    )


def drain_completed_futures_with_context(
    *,
    completed_futures: Sequence[Future[FieldTestResult]],
    execution_state: ExecutionState,
    args: SchedulerRuntimeArgs | SchedulerControlOptions,
    completion_ctx: FutureCompletionContext,
    runtime_state: RuntimeConcurrencyState,
    handle_completed: CompletedFutureHandler,
    log: logging.Logger = logger,
) -> TemplateStats:
    """Consume completed futures using a prebuilt immutable completion context."""
    scheduler_options = _queue.scheduler_control_options(args)
    for done_future in completed_futures:
        drain_result = handle_completed(
            done_future,
            completion_ctx=completion_ctx,
            execution_state=execution_state,
        )
        execution_state.template_stats = drain_result.template_stats
        current_submittable_count = execution_state.result_ledger.current_run_submittable_count
        # Queue timeouts are tracked per candidate below. Keep the shared
        # decision helper focused here on stop/cooldown state only.
        decision = decide_drain_state_updates(
            stop_threshold=_drain_state.stop_after_submittable_threshold(scheduler_options),
            current_submittable_count=current_submittable_count,
            congestion_detected=drain_result.congestion_detected,
        )
        _drain_state.apply_drain_state_decision(
            decision,
            scheduler_options=scheduler_options,
            execution_state=execution_state,
            runtime_state=runtime_state,
            log=log,
        )
        _queue.register_queue_busy_template(
            drain_result.queue_busy_key, scheduler_options, execution_state
        )
    return execution_state.template_stats
