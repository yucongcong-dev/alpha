"""Queue-busy retry accounting helpers for scheduler."""

from __future__ import annotations

import logging

from ..models.runtime_options import SchedulerControlOptions
from ..runtime.queue_retry import QueueRetryKey
from ..runtime.state import ExecutionState

logger = logging.getLogger(__name__)


def register_queue_busy_template(
    key: QueueRetryKey | None,
    options: SchedulerControlOptions,
    execution_state: ExecutionState,
) -> None:
    """Bound retries for one candidate without blacklisting its whole field."""
    if key is None:
        return
    update = execution_state.queue_retry_state.register_busy(
        key,
        retry_limit=options.queue_busy_retry_limit,
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
