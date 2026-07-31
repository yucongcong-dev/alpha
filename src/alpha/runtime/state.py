"""Mutable runtime execution state."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field
import time

from ..config.models import DatasetExpressionPolicy
from ..models.domain import FieldTestResult, TemplateField, TemplateLibrary
from ..models.io_types import RunFilters
from ..models.runtime_protocols import (
    ClientFactoryLike,
    RunConfig,
    SemaphoreLike,
    TemplateStats,
)
from ..policy.types import BlacklistRuntimeStats
from .contexts import HistoricalRunState, PendingFutureContext
from .future_queue import FutureQueueState
from .result_ledger import ResultLedgerState

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
class ExecutionState:
    """执行过程中可变的待运行、跳过与累计结果状态。"""

    attempted_keys: set[tuple[str, str, str, str]] = field(default_factory=set)
    template_stats: TemplateStats = field(default_factory=dict)
    future_queue_state: FutureQueueState = field(default_factory=FutureQueueState.create)
    field_queue_busy_counts: dict[str, int] = field(default_factory=dict)
    skipped_fields_due_to_queue: set[str] = field(default_factory=set)
    queue_retry_state: QueueRetryState = field(default_factory=QueueRetryState)
    result_ledger_state: ResultLedgerState = field(
        default_factory=lambda: ResultLedgerState(results=[])
    )
    blacklist_runtime_stats: BlacklistRuntimeStats = field(default_factory=dict)
    blacklisted_template_keys: set[tuple[str, str, str]] = field(default_factory=set)
    last_submission_at: float = 0.0

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
            attempted_keys=set(attempted_keys or set()),
            template_stats=dict(template_stats or {}),
            field_queue_busy_counts=dict(field_queue_busy_counts or {}),
            skipped_fields_due_to_queue=set(skipped_fields_due_to_queue or set()),
            future_queue_state=FutureQueueState.create(
                pending_futures=pending_futures,
                resumable_simulations=resumable_simulations,
            ),
            result_ledger_state=ResultLedgerState(results=list(initial_results or [])),
            last_submission_at=last_submission_at,
        )

    @property
    def future_queue(self) -> FutureQueueState:
        """Return the authoritative future-state view."""
        return self.future_queue_state

    @property
    def result_ledger(self) -> ResultLedgerState:
        """Return the authoritative result-state view."""
        return self.result_ledger_state

    def reset_transient_queue_state(self) -> None:
        """Reset queue state that should not survive process restarts."""
        self.field_queue_busy_counts = {}
        self.skipped_fields_due_to_queue = set()
        self.queue_retry_state.reset()


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
