"""Mutable runtime execution state."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field

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
from .concurrency import RuntimeConcurrencyState
from .contexts import HistoricalRunState, PendingFutureContext
from .field_queue import FieldQueueState
from .future_queue import FutureQueueState
from .queue_retry import QueueRetryState
from .result_ledger import ResultLedgerState


@dataclass
class ExecutionState:
    """执行过程中可变的待运行、跳过与累计结果状态。"""

    attempted_keys: set[tuple[str, str, str, str]] = field(default_factory=set)
    template_stats: TemplateStats = field(default_factory=dict)
    future_queue_state: FutureQueueState = field(default_factory=FutureQueueState.create)
    field_queue_state: FieldQueueState = field(default_factory=FieldQueueState)
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
            field_queue_state=FieldQueueState.create(
                busy_counts=field_queue_busy_counts,
                skipped_fields=skipped_fields_due_to_queue,
            ),
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
    def field_queue(self) -> FieldQueueState:
        """Return the authoritative field-level queue-state view."""
        return self.field_queue_state

    @property
    def result_ledger(self) -> ResultLedgerState:
        """Return the authoritative result-state view."""
        return self.result_ledger_state

    def reset_transient_queue_state(self) -> None:
        """Reset queue state that should not survive process restarts."""
        self.field_queue.reset()
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
