"""Queue-busy retry accounting helpers for scheduler."""

from __future__ import annotations

import logging

from ..models.runtime_options import SchedulerControlOptions
from ..models.runtime_protocols import SchedulerRuntimeArgs
from ..runtime.queue_retry import QueueRetryKey
from ..runtime.state import ExecutionState
from .scheduler_decisions import QueueBusyDecision, decide_queue_busy_update

logger = logging.getLogger(__name__)


def scheduler_control_options(
    args: SchedulerRuntimeArgs | SchedulerControlOptions,
) -> SchedulerControlOptions:
    if isinstance(args, SchedulerControlOptions):
        return args
    return SchedulerControlOptions.from_args(args)


def apply_queue_busy_decision(
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


def register_queue_busy_field(
    field_id: str | None,
    args: SchedulerRuntimeArgs | SchedulerControlOptions,
    field_queue_busy_counts: dict[str, int],
    skipped_fields_due_to_queue: set[str],
) -> None:
    """记录重复的排队拥塞字段，并在达到阈值后跳过该字段。"""
    options = scheduler_control_options(args)
    decision = decide_queue_busy_update(
        field_id,
        current_count=field_queue_busy_counts.get(field_id or "", 0),
        skip_after=options.field_queue_busy_skip_after,
    )
    apply_queue_busy_decision(
        decision,
        skip_after=options.field_queue_busy_skip_after,
        field_queue_busy_counts=field_queue_busy_counts,
        skipped_fields_due_to_queue=skipped_fields_due_to_queue,
    )


def register_queue_busy_template(
    key: QueueRetryKey | None,
    args: SchedulerRuntimeArgs | SchedulerControlOptions,
    execution_state: ExecutionState,
) -> None:
    """Bound retries for one candidate without blacklisting its whole field."""
    if key is None:
        return
    options = scheduler_control_options(args)
    update = execution_state.queue_retry_state.register_busy(
        key,
        retry_limit=options.field_queue_busy_skip_after,
    )
    if update.exhausted:
        logger.info(
            "[queue] exhausted retry budget %d/%d field=%s template=%s settings=%s",
            update.next_count,
            update.retry_limit,
            key[0],
            key[1],
            key[3],
        )
    else:
        logger.info(
            "[queue] candidate remains retryable attempt=%d%s field=%s template=%s",
            update.next_count,
            f"/{update.retry_limit}" if update.retry_limit > 0 else "",
            key[0],
            key[1],
        )
