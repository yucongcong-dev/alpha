"""Result ledger state and derived execution metrics."""

from __future__ import annotations

from dataclasses import dataclass

from ..config.constants import STATUS_ERROR
from ..models.domain import FieldTestResult
from ..models.result_predicates import has_pending_checks, is_queue_timeout_result


@dataclass(frozen=True, slots=True)
class ExecutionMetrics:
    """Counts derived from the authoritative in-memory result sequence."""

    unique_field_ids: frozenset[str]
    submittable_count: int
    submitted_count: int
    error_count: int
    queue_timeout_count: int
    pending_check_count: int

    @classmethod
    def from_results(cls, results: list[FieldTestResult]) -> ExecutionMetrics:
        return cls(
            unique_field_ids=frozenset(result.field_id for result in results),
            submittable_count=sum(1 for result in results if result.submittable),
            submitted_count=sum(1 for result in results if result.submitted),
            error_count=sum(1 for result in results if result.status == STATUS_ERROR),
            queue_timeout_count=sum(1 for result in results if is_queue_timeout_result(result)),
            pending_check_count=sum(1 for result in results if has_pending_checks(result)),
        )


@dataclass
class ResultLedgerState:
    """Authoritative result sequence plus derived result counters."""

    results: list[FieldTestResult]
    submittable_baseline_count: int = 0
    persisted_result_count: int = 0

    @property
    def metrics(self) -> ExecutionMetrics:
        """Return a current snapshot derived from the authoritative results list."""
        return ExecutionMetrics.from_results(self.results)

    @property
    def unique_field_ids(self) -> set[str]:
        return set(self.metrics.unique_field_ids)

    @property
    def submittable_count(self) -> int:
        return self.metrics.submittable_count

    @property
    def current_run_submittable_count(self) -> int:
        """Return submittable results added after this process initialized."""
        return max(0, self.metrics.submittable_count - self.submittable_baseline_count)

    @property
    def submitted_count(self) -> int:
        return self.metrics.submitted_count

    @property
    def error_count(self) -> int:
        return self.metrics.error_count

    @property
    def queue_timeout_count(self) -> int:
        return self.metrics.queue_timeout_count

    @property
    def pending_check_count(self) -> int:
        return self.metrics.pending_check_count

    def append(self, result: FieldTestResult) -> ExecutionMetrics:
        self.results.append(result)
        return self.metrics

    def reached_submittable_stop_threshold(self, stop_threshold: int) -> bool:
        """Return whether current-run submittable results reached the stop threshold."""
        return stop_threshold > 0 and self.current_run_submittable_count >= stop_threshold

    def refresh_metrics(self) -> ExecutionMetrics:
        """Compatibility method returning the current derived snapshot."""
        return self.metrics
