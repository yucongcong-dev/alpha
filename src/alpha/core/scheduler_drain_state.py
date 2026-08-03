"""Post-drain scheduler state application helpers."""

from __future__ import annotations

import logging

from ..models.runtime_options import SchedulerControlOptions
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.state import ExecutionState
from . import scheduler_concurrency as _concurrency
from . import scheduler_queue as _queue
from .scheduler_decisions import DrainStateDecision

logger = logging.getLogger(__name__)


def stop_after_submittable_threshold(options: SchedulerControlOptions) -> int:
    """Coerce the stop-after-submittable option into a non-negative threshold."""
    try:
        return int(options.stop_after_submittable or 0)
    except (TypeError, ValueError):
        return 0


def cancel_unstarted_pending_futures(
    execution_state: ExecutionState,
    *,
    log: logging.Logger = logger,
) -> None:
    """Cancel queued futures that have not started after the stop signal is active."""
    for future, context in list(execution_state.future_queue.pending_futures.items()):
        if future.cancel():
            execution_state.future_queue.pending_futures.pop(future, None)
            log.info(
                "[stop] cancelled queued future field=%s template=%s after stop-after-submittable",
                context.field_id,
                context.template_name,
            )


def apply_drain_state_decision(
    decision: DrainStateDecision,
    *,
    scheduler_options: SchedulerControlOptions,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    log: logging.Logger = logger,
) -> None:
    """Apply a previously computed post-persistence scheduler decision."""
    if decision.activate_stop_signal:
        execution_state.future_queue.stop_signal.set()
        cancel_unstarted_pending_futures(execution_state, log=log)

    _queue.apply_queue_busy_decision(
        decision.queue_busy,
        skip_after=scheduler_options.field_queue_busy_skip_after,
        field_queue_busy_counts=execution_state.field_queue.busy_counts,
        skipped_fields_due_to_queue=execution_state.field_queue.skipped_fields,
    )

    if decision.apply_congestion_cooldown:
        _concurrency.apply_congestion_cooldown(scheduler_options, runtime_state, log=log)
