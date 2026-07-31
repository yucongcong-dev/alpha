"""Field-level queue congestion state."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FieldQueueState:
    """Queue-busy counters and fields skipped after repeated congestion."""

    busy_counts: dict[str, int] = field(default_factory=dict)
    skipped_fields: set[str] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        *,
        busy_counts: dict[str, int] | None = None,
        skipped_fields: set[str] | None = None,
    ) -> FieldQueueState:
        return cls(
            busy_counts=dict(busy_counts or {}),
            skipped_fields=set(skipped_fields or set()),
        )

    def reset(self) -> None:
        """Clear field-level queue congestion state after a process restart."""
        self.busy_counts.clear()
        self.skipped_fields.clear()
