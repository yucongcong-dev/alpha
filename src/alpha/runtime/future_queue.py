"""Future queue state owned by the runtime execution state."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from threading import Event

from ..models.domain import FieldTestResult
from .contexts import PendingFutureContext


@dataclass
class FutureQueueState:
    """Pending worker futures plus resumable remote simulations."""

    pending_futures: dict[Future[FieldTestResult], PendingFutureContext]
    resumable_simulations: list[PendingFutureContext]
    stop_scheduling: Event
    abort_workers: Event

    @classmethod
    def create(
        cls,
        *,
        pending_futures: dict[Future[FieldTestResult], PendingFutureContext] | None = None,
        resumable_simulations: list[PendingFutureContext] | None = None,
    ) -> FutureQueueState:
        """Create an isolated future queue with fresh containers and stop signal."""
        return cls(
            pending_futures=dict(pending_futures or {}),
            resumable_simulations=list(resumable_simulations or []),
            stop_scheduling=Event(),
            abort_workers=Event(),
        )

    def should_stop_scheduling(self) -> bool:
        """Return whether new work must no longer be scheduled."""
        return self.stop_scheduling.is_set()

    def should_abort_workers(self) -> bool:
        """Return whether running workers should abort their current stage."""
        return self.abort_workers.is_set()

    def request_stop(self, *, abort_workers: bool) -> None:
        """Stop new scheduling and optionally abort already running workers."""
        self.stop_scheduling.set()
        if abort_workers:
            self.abort_workers.set()

    def cancel_unstarted(self) -> int:
        """Cancel futures that have not started and remove their pending metadata."""
        cancelled = 0
        for future in list(self.pending_futures):
            if future.cancel():
                self.pending_futures.pop(future, None)
                cancelled += 1
        return cancelled

    def register(
        self,
        future: Future[FieldTestResult],
        context: PendingFutureContext,
    ) -> None:
        self.pending_futures[future] = context

    def pop_completed(self, future: Future[FieldTestResult]) -> PendingFutureContext:
        return self.pending_futures.pop(future)

    def take_resumable_batch(self) -> list[PendingFutureContext]:
        pending_contexts = list(self.resumable_simulations)
        self.resumable_simulations.clear()
        return pending_contexts

    def replace_resumable_batch(self, pending_contexts: list[PendingFutureContext]) -> None:
        """Replace resumable contexts without replacing the owned list object."""
        self.resumable_simulations[:] = pending_contexts

    def restore_resumable_batch(self, pending_contexts: list[PendingFutureContext]) -> None:
        self.resumable_simulations.extend(pending_contexts)
