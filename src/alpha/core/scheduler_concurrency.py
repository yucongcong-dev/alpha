"""Runtime concurrency and submission throttling helpers for scheduler."""

from __future__ import annotations

from collections.abc import Callable
import logging
import time

from ..models.runtime_options import SchedulerControlOptions
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.state import ExecutionState
from .scheduler_decisions import (
    resolve_congestion_cooldown_until,
    should_restore_runtime_concurrency,
    submission_throttle_delay,
)

logger = logging.getLogger(__name__)


def maybe_restore_runtime_concurrency(
    state: RuntimeConcurrencyState,
    *,
    log: logging.Logger = logger,
) -> None:
    """Restore configured concurrency after an expired congestion cooldown."""
    if should_restore_runtime_concurrency(
        cooldown_until=state.cooldown_until,
        runtime_max_workers=state.runtime_max_workers,
        max_workers=state.max_workers,
        now=time.monotonic(),
    ):
        state.runtime_max_workers = state.max_workers
        state.cooldown_until = 0.0
        log.info(
            "[cooldown] restored runtime concurrency to %d",
            state.runtime_max_workers,
        )


def apply_congestion_cooldown(
    options: SchedulerControlOptions,
    state: RuntimeConcurrencyState,
    *,
    log: logging.Logger = logger,
) -> None:
    """Switch temporarily to single-worker mode after queue congestion."""
    state.runtime_max_workers = 1
    state.cooldown_until = resolve_congestion_cooldown_until(
        now=time.monotonic(),
        cooldown_seconds=options.queue_busy_cooldown_seconds,
    )
    log.info(
        "[cooldown] detected queue congestion, runtime concurrency -> 1 for %.0fs",
        options.queue_busy_cooldown_seconds,
    )


def throttle_before_submission(
    options: SchedulerControlOptions,
    execution_state: ExecutionState,
    *,
    wait: Callable[[float, str], None],
) -> None:
    """Wait before the next submission when the configured interval requires it."""
    remaining = submission_throttle_delay(
        interval_seconds=options.sleep_between_fields,
        last_submission_at=execution_state.last_submission_at,
        now=time.monotonic(),
    )
    if remaining > 0:
        wait(remaining, "before next template submission")
