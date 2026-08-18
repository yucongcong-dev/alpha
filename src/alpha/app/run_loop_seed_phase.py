"""Seed-first scheduling state for full-run exploration."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config.static_config import get_static_config
from ..models.domain import TemplateField
from ..runtime.state import ExecutionState
from ..utils.helpers import first_non_empty


@dataclass
class SeedPhaseState:
    """Own seed coverage progress independently from ordinary round scheduling."""

    enabled: bool = False
    target_field_ids: set[str] = field(default_factory=set)
    resolved_field_ids: set[str] = field(default_factory=set)
    inflight_field_ids: set[str] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        fields: list[TemplateField],
        *,
        enabled: bool,
        resolved_field_ids: set[str] | None = None,
    ) -> SeedPhaseState:
        """Build seed state for the selected field set."""
        targets = {
            str(first_non_empty(item.field_id, get_static_config().sentinel_unknown))
            for item in fields
        }
        return cls(
            enabled=enabled,
            target_field_ids=targets,
            resolved_field_ids=set(resolved_field_ids or set()) & targets,
        )

    @property
    def total_count(self) -> int:
        return len(self.target_field_ids)

    @property
    def resolved_count(self) -> int:
        return len(self.resolved_field_ids)

    @property
    def remaining_count(self) -> int:
        if not self.enabled:
            return 0
        return len(self.target_field_ids - self.resolved_field_ids)

    @property
    def active(self) -> bool:
        return self.enabled and self.remaining_count > 0

    @property
    def phase_name(self) -> str:
        return "seed" if self.active else "refine"

    def sync(self, execution_state: ExecutionState) -> None:
        """Reconcile persisted attempts and active restored work with seed progress."""
        if not self.enabled:
            return
        attempted_field_ids = {
            field_id
            for field_id, _template, _expression, _settings in execution_state.attempted_keys
        }
        self.resolved_field_ids.update(attempted_field_ids & self.target_field_ids)
        active_field_ids = {
            pending.field_id
            for pending in (
                *execution_state.future_queue.resumable_simulations,
                *execution_state.future_queue.pending_futures.values(),
            )
            if pending.field_id
        }
        self.inflight_field_ids.intersection_update(active_field_ids)
        self.inflight_field_ids.update(
            (active_field_ids & self.target_field_ids) - self.resolved_field_ids
        )

    def should_wait_or_skip(self, field_id: str) -> bool:
        """Return whether an active seed phase already resolved or owns this field."""
        return self.active and (
            field_id in self.resolved_field_ids or field_id in self.inflight_field_ids
        )

    def mark_inflight(self, field_id: str) -> bool:
        """Mark a dispatched seed as inflight without claiming completed coverage."""
        if not self.enabled or field_id not in self.target_field_ids:
            return False
        previous_count = len(self.inflight_field_ids)
        self.inflight_field_ids.add(field_id)
        return len(self.inflight_field_ids) > previous_count

    def resolve(self, field_id: str) -> bool:
        """Mark one field seeded or unactionable and report whether state advanced."""
        if not self.enabled or field_id not in self.target_field_ids:
            return False
        previous_count = len(self.resolved_field_ids)
        self.inflight_field_ids.discard(field_id)
        self.resolved_field_ids.add(field_id)
        return len(self.resolved_field_ids) > previous_count
