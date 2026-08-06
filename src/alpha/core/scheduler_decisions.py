"""Pure scheduler state decisions separated from runtime side effects."""


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
