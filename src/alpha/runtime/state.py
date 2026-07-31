"""Mutable runtime execution state."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field
from threading import Event
import time

from ..config.constants import STATUS_ERROR
from ..config.models import DatasetExpressionPolicy
from ..models.domain import FieldTestResult, TemplateField, TemplateLibrary
from ..models.io_types import RunFilters
from ..models.result_predicates import has_pending_checks, is_queue_timeout_result
from ..models.runtime_protocols import (
    ClientFactoryLike,
    RunConfig,
    SemaphoreLike,
    TemplateStats,
)
from ..policy.types import BlacklistRuntimeStats
from .contexts import HistoricalRunState, PendingFutureContext

QueueRetryKey = tuple[str, str, str, str]


@dataclass
class RuntimeConcurrencyState:
    """并发调度状态数据类。"""

    max_workers: int = 2
    runtime_max_workers: int = 2
    cooldown_until: float = 0.0

    def is_cooling_down(self) -> bool:
        return self.cooldown_until > 0 and time.monotonic() < self.cooldown_until

    def can_restore_concurrency(self) -> bool:
        return (
            self.cooldown_until > 0
            and time.monotonic() >= self.cooldown_until
            and self.runtime_max_workers != self.max_workers
        )


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


@dataclass
class FutureQueueState:
    """Pending worker futures plus resumable remote simulations."""

    pending_futures: dict[Future[FieldTestResult], PendingFutureContext]
    resumable_simulations: list[PendingFutureContext]
    stop_signal: Event

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

    def restore_resumable_batch(self, pending_contexts: list[PendingFutureContext]) -> None:
        self.resumable_simulations.extend(pending_contexts)


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


@dataclass
class ExecutionState:
    """执行过程中可变的待运行、跳过与累计结果状态。"""

    results: list[FieldTestResult]
    attempted_keys: set[tuple[str, str, str, str]]
    template_stats: TemplateStats
    pending_futures: dict[Future[FieldTestResult], PendingFutureContext]
    field_queue_busy_counts: dict[str, int]
    skipped_fields_due_to_queue: set[str]
    resumable_simulations: list[PendingFutureContext] = field(default_factory=list)
    queue_retry_counts: dict[QueueRetryKey, int] = field(default_factory=dict)
    queue_exhausted_keys: set[QueueRetryKey] = field(default_factory=set)
    queue_retry_state: QueueRetryState = field(init=False)
    future_queue_state: FutureQueueState = field(init=False)
    result_ledger_state: ResultLedgerState = field(init=False)
    submittable_baseline_count: int = 0
    persisted_result_count: int = 0
    blacklist_runtime_stats: BlacklistRuntimeStats = field(default_factory=dict)
    blacklisted_template_keys: set[tuple[str, str, str]] = field(default_factory=set)
    last_submission_at: float = 0.0
    stop_signal: Event = field(default_factory=Event)

    @classmethod
    def create(
        cls,
        *,
        initial_results: list[FieldTestResult] | None = None,
        attempted_keys: set[tuple[str, str, str, str]] | None = None,
        template_stats: TemplateStats | None = None,
        pending_futures: dict[Future[FieldTestResult], PendingFutureContext] | None = None,
        field_queue_busy_counts: dict[str, int] | None = None,
        skipped_fields_due_to_queue: set[str] | None = None,
        resumable_simulations: list[PendingFutureContext] | None = None,
        last_submission_at: float = 0.0,
    ) -> ExecutionState:
        """Create runtime state through a narrow initialization boundary."""
        return cls(
            results=list(initial_results or []),
            attempted_keys=set(attempted_keys or set()),
            template_stats=dict(template_stats or {}),
            pending_futures=dict(pending_futures or {}),
            field_queue_busy_counts=dict(field_queue_busy_counts or {}),
            skipped_fields_due_to_queue=set(skipped_fields_due_to_queue or set()),
            resumable_simulations=list(resumable_simulations or []),
            last_submission_at=last_submission_at,
        )

    def __post_init__(self) -> None:
        self.queue_retry_state = QueueRetryState(
            retry_counts=self.queue_retry_counts,
            exhausted_keys=self.queue_exhausted_keys,
        )
        self.future_queue_state = FutureQueueState(
            pending_futures=self.pending_futures,
            resumable_simulations=self.resumable_simulations,
            stop_signal=self.stop_signal,
        )
        self.result_ledger_state = ResultLedgerState(
            results=self.results,
            submittable_baseline_count=self.submittable_baseline_count,
            persisted_result_count=self.persisted_result_count,
        )

    @property
    def future_queue(self) -> FutureQueueState:
        """Return a future-state view that tracks legacy mutable attributes."""
        self.future_queue_state.pending_futures = self.pending_futures
        self.future_queue_state.resumable_simulations = self.resumable_simulations
        self.future_queue_state.stop_signal = self.stop_signal
        return self.future_queue_state

    @property
    def result_ledger(self) -> ResultLedgerState:
        """Return the authoritative result-state view."""
        return self.result_ledger_state

    def sync_result_ledger(self) -> None:
        """Copy ledger-owned counters back to legacy execution-state attributes."""
        self.results = self.result_ledger_state.results
        self.submittable_baseline_count = self.result_ledger_state.submittable_baseline_count
        self.persisted_result_count = self.result_ledger_state.persisted_result_count

    def reset_transient_queue_state(self) -> None:
        """Reset queue state that should not survive process restarts."""
        self.field_queue_busy_counts = {}
        self.skipped_fields_due_to_queue = set()
        self.queue_retry_state.reset()

    @property
    def metrics(self) -> ExecutionMetrics:
        """Return a current snapshot derived from the authoritative results list."""
        return self.result_ledger.metrics

    @property
    def unique_field_ids(self) -> set[str]:
        return self.result_ledger.unique_field_ids

    @property
    def submittable_count(self) -> int:
        return self.result_ledger.submittable_count

    @property
    def current_run_submittable_count(self) -> int:
        """Return submittable results added after this process initialized."""
        return self.result_ledger.current_run_submittable_count

    @property
    def submitted_count(self) -> int:
        return self.result_ledger.submitted_count

    @property
    def error_count(self) -> int:
        return self.result_ledger.error_count

    @property
    def queue_timeout_count(self) -> int:
        return self.result_ledger.queue_timeout_count

    @property
    def pending_check_count(self) -> int:
        return self.result_ledger.pending_check_count

    def refresh_metrics(self) -> ExecutionMetrics:
        """Compatibility method returning the current derived snapshot."""
        return self.result_ledger.refresh_metrics()


@dataclass(frozen=True)
class InitializedRunContext:
    """初始化阶段产出的主流程上下文。"""

    client_factory: ClientFactoryLike
    template_library: TemplateLibrary
    filters: RunFilters
    expression_policy: DatasetExpressionPolicy
    use_dataset_heuristics: bool
    template_library_fingerprint: str
    settings_fingerprint: str
    historical_state: HistoricalRunState
    fields: list[TemplateField]
    execution_state: ExecutionState
    runtime_state: RuntimeConcurrencyState
    create_semaphore: SemaphoreLike
    run_config: RunConfig


PendingFutureLike = PendingFutureContext
