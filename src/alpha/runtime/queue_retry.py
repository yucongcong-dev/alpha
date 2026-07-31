"""Candidate-level queue retry state."""

from __future__ import annotations

from dataclasses import dataclass, field

QueueRetryKey = tuple[str, str, str, str]


@dataclass(frozen=True, slots=True)
class QueueRetryUpdate:
    """Result of registering one queue-busy candidate retry."""

    next_count: int
    retry_limit: int
    exhausted: bool


@dataclass
class QueueRetryState:
    """Candidate-level retry budget state for queue-busy simulation results."""

    retry_counts: dict[QueueRetryKey, int] = field(default_factory=dict)
    exhausted_keys: set[QueueRetryKey] = field(default_factory=set)

    def register_busy(self, key: QueueRetryKey, *, retry_limit: int) -> QueueRetryUpdate:
        """Increment one candidate retry count and mark it exhausted when budget is spent."""
        normalized_limit = max(0, int(retry_limit or 0))
        next_count = self.retry_counts.get(key, 0) + 1
        self.retry_counts[key] = next_count
        exhausted = normalized_limit > 0 and next_count >= normalized_limit
        if exhausted:
            self.exhausted_keys.add(key)
        return QueueRetryUpdate(
            next_count=next_count,
            retry_limit=normalized_limit,
            exhausted=exhausted,
        )

    def reset(self) -> None:
        """Clear transient queue retry state after a process restart."""
        self.retry_counts.clear()
        self.exhausted_keys.clear()
