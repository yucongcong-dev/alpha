"""Per-field template queues used by breadth-first scheduling."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from itertools import islice

from .contexts import PendingTemplateEntry


@dataclass
class FieldTemplateQueue:
    """Cached pending template queue for one field between scheduling rounds."""

    entries: deque[PendingTemplateEntry]
    filtered_templates: int
    template_count: int

    @classmethod
    def create(
        cls,
        entries: list[PendingTemplateEntry],
        *,
        filtered_templates: int,
        template_count: int,
    ) -> FieldTemplateQueue:
        return cls(
            entries=deque(entries),
            filtered_templates=filtered_templates,
            template_count=template_count,
        )

    def peek(self, limit: int) -> list[PendingTemplateEntry]:
        """Return the next batch without advancing the queue."""
        if limit <= 0:
            return list(self.entries)
        return list(islice(self.entries, limit))

    def consume_one(self) -> None:
        """Advance past one successfully dispatched entry."""
        if self.entries:
            self.entries.popleft()
