"""Wait for simulation workers, consume results, and persist progress."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, wait

from ..core.checkpoint import save_pipeline_state
from ..core.scheduler_draining import drain_completed_futures_with_context
from ..models.domain import FieldTestResult
from ..models.runtime_options import SchedulerControlOptions
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import CheckpointIdentity, FutureCompletionContext, PendingFutureContext
from ..runtime.state import ExecutionState


def _checkpoint_identity(completion_ctx: FutureCompletionContext) -> CheckpointIdentity:
    return CheckpointIdentity(run_fingerprint=completion_ctx.run_fingerprint)


def _drain_completed_cycle(
    *,
    pending_futures: dict[Future[FieldTestResult], PendingFutureContext],
    execution_state: ExecutionState,
    scheduler_options: SchedulerControlOptions,
    completion_ctx: FutureCompletionContext,
    runtime_state: RuntimeConcurrencyState,
) -> None:
    """Wait for one completion cycle and drain all finished futures."""
    done, _ = wait(set(pending_futures), return_when=FIRST_COMPLETED)
    drain_completed_futures_with_context(
        completed_futures=list(done),
        execution_state=execution_state,
        scheduler_options=scheduler_options,
        completion_ctx=completion_ctx,
        runtime_state=runtime_state,
    )


def drain_next_completion(
    *,
    state_file: str,
    execution_state: ExecutionState,
    scheduler_options: SchedulerControlOptions,
    completion_ctx: FutureCompletionContext,
    runtime_state: RuntimeConcurrencyState,
) -> bool:
    """Drain one completion batch and persist resumable runtime state."""
    pending_futures = execution_state.future_queue.pending_futures
    if not pending_futures:
        return False
    _drain_completed_cycle(
        pending_futures=pending_futures,
        execution_state=execution_state,
        scheduler_options=scheduler_options,
        completion_ctx=completion_ctx,
        runtime_state=runtime_state,
    )
    if state_file:
        saved = save_pipeline_state(
            state_file,
            execution_state=execution_state,
            runtime_state=runtime_state,
            identity=_checkpoint_identity(completion_ctx),
        )
        if not saved:
            raise RuntimeError(f"failed to save pipeline state: {state_file}")
    return True


def drain_until_capacity(
    *,
    executor_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    scheduler_options: SchedulerControlOptions,
    completion_ctx: FutureCompletionContext,
) -> None:
    """Drain completed futures until runtime concurrency has available capacity."""
    future_queue = executor_state.future_queue
    while len(future_queue.pending_futures) >= runtime_state.runtime_max_workers:
        _drain_completed_cycle(
            pending_futures=future_queue.pending_futures,
            execution_state=executor_state,
            scheduler_options=scheduler_options,
            completion_ctx=completion_ctx,
            runtime_state=runtime_state,
        )


def drain_remaining_futures(
    *,
    state_file: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    scheduler_options: SchedulerControlOptions,
    completion_ctx: FutureCompletionContext,
) -> None:
    """Drain all remaining futures and persist resumable state as they finish."""
    future_queue = execution_state.future_queue
    while future_queue.pending_futures:
        drain_next_completion(
            state_file=state_file,
            execution_state=execution_state,
            scheduler_options=scheduler_options,
            completion_ctx=completion_ctx,
            runtime_state=runtime_state,
        )
