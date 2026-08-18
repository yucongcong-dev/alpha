"""Result ledger state and derived execution metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config.static_config import get_static_config
from ..models.domain import FieldTestResult
from ..models.result_predicates import has_pending_checks, is_queue_timeout_result


@dataclass(frozen=True, slots=True)
class ExecutionMetrics:
    """Counts derived from the authoritative in-memory result sequence."""

    unique_field_ids: frozenset[str]
    submittable_count: int
    error_count: int
    queue_timeout_count: int
    pending_check_count: int

    @classmethod
    def from_results(cls, results: list[FieldTestResult]) -> ExecutionMetrics:
        return cls(
            unique_field_ids=frozenset(result.field_id for result in results),
            submittable_count=sum(1 for result in results if result.submittable),
            error_count=sum(
                1 for result in results if result.status == get_static_config().status_error
            ),
            queue_timeout_count=sum(1 for result in results if is_queue_timeout_result(result)),
            pending_check_count=sum(1 for result in results if has_pending_checks(result)),
        )

    def with_result(self, result: FieldTestResult) -> ExecutionMetrics:
        """Return an incrementally updated snapshot containing one additional result."""
        return ExecutionMetrics(
            unique_field_ids=self.unique_field_ids | {result.field_id},
            submittable_count=self.submittable_count + int(bool(result.submittable)),
            error_count=self.error_count + int(result.status == get_static_config().status_error),
            queue_timeout_count=self.queue_timeout_count + int(is_queue_timeout_result(result)),
            pending_check_count=self.pending_check_count + int(has_pending_checks(result)),
        )


@dataclass
class ResultLedgerState:
    """Authoritative result sequence plus derived result counters."""

    results: list[FieldTestResult]
    persisted_result_count: int = 0
    _metrics: ExecutionMetrics = field(init=False, repr=False)
    _metrics_result_count: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rebuild_metrics()

    def _rebuild_metrics(self) -> ExecutionMetrics:
        self._metrics = ExecutionMetrics.from_results(self.results)
        self._metrics_result_count = len(self.results)
        return self._metrics

    @property
    def metrics(self) -> ExecutionMetrics:
        """Return the cached snapshot, rebuilding after unsupported direct list mutation."""
        if self._metrics_result_count != len(self.results):
            return self._rebuild_metrics()
        return self._metrics

    @property
    def unique_field_ids(self) -> set[str]:
        return set(self.metrics.unique_field_ids)

    @property
    def submittable_count(self) -> int:
        return self.metrics.submittable_count

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
        current_metrics = self.metrics
        self.results.append(result)
        self._metrics = current_metrics.with_result(result)
        self._metrics_result_count += 1
        return self._metrics

    def refresh_metrics(self) -> ExecutionMetrics:
        """Force a full snapshot rebuild after direct result-list mutation."""
        return self._rebuild_metrics()
