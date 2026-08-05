"""Pure scheduler state decisions separated from runtime side effects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DrainStateDecision:
    """State-side effects selected after one completed future is persisted."""

    activate_stop_signal: bool
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
) -> DrainStateDecision:
    """Combine post-persistence signals into one immutable state decision."""
    return DrainStateDecision(
        activate_stop_signal=reached_submittable_stop_threshold(
            stop_threshold=stop_threshold,
            current_submittable_count=current_submittable_count,
        ),
        apply_congestion_cooldown=congestion_detected,
    )
