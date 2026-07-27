"""Pure scheduler state decisions separated from runtime side effects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueueBusyDecision:
    """State update selected after a queue-busy signal."""

    field_id: str | None = None
    next_count: int = 0
    should_skip: bool = False

    @property
    def should_register(self) -> bool:
        return bool(self.field_id)


@dataclass(frozen=True)
class DrainStateDecision:
    """State-side effects selected after one completed future is persisted."""

    activate_stop_signal: bool
    queue_busy: QueueBusyDecision
    apply_congestion_cooldown: bool


def should_restore_runtime_concurrency(
    *,
    cooldown_until: float,
    runtime_max_workers: int,
    max_workers: int,
    now: float,
) -> bool:
    """Return whether an expired cooldown should restore configured concurrency."""
    return cooldown_until > 0 and now >= cooldown_until and runtime_max_workers != max_workers


def resolve_congestion_cooldown_until(*, now: float, cooldown_seconds: float) -> float:
    """Resolve a non-negative cooldown deadline from a monotonic timestamp."""
    return now + max(cooldown_seconds, 0.0)


def decide_queue_busy_update(
    field_id: str | None,
    *,
    current_count: int,
    skip_after: int,
) -> QueueBusyDecision:
    """Decide the next per-field queue-busy count and skip transition."""
    if not field_id or skip_after <= 0:
        return QueueBusyDecision()
    next_count = current_count + 1
    return QueueBusyDecision(
        field_id=field_id,
        next_count=next_count,
        should_skip=next_count >= skip_after,
    )


def submission_throttle_delay(
    *,
    interval_seconds: float,
    last_submission_at: float,
    now: float,
) -> float:
    """Return the remaining pre-submission delay without sleeping."""
    if interval_seconds <= 0 or last_submission_at <= 0:
        return 0.0
    return max(interval_seconds - (now - last_submission_at), 0.0)


def reached_submittable_stop_threshold(
    *,
    stop_threshold: int,
    current_submittable_count: int,
) -> bool:
    """Return whether completed results reached the configured stop target."""
    return stop_threshold > 0 and current_submittable_count >= stop_threshold


def decide_drain_state_updates(
    *,
    stop_threshold: int,
    current_submittable_count: int,
    congestion_detected: bool,
    queue_busy_field_id: str | None,
    current_queue_busy_count: int,
    queue_busy_skip_after: int,
) -> DrainStateDecision:
    """Combine post-persistence signals into one immutable state decision."""
    return DrainStateDecision(
        activate_stop_signal=reached_submittable_stop_threshold(
            stop_threshold=stop_threshold,
            current_submittable_count=current_submittable_count,
        ),
        queue_busy=decide_queue_busy_update(
            queue_busy_field_id,
            current_count=current_queue_busy_count,
            skip_after=queue_busy_skip_after,
        ),
        apply_congestion_cooldown=congestion_detected,
    )
