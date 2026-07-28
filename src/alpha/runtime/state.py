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
class ExecutionState:
    """执行过程中可变的待运行、跳过与累计结果状态。"""

    results: list[FieldTestResult]
    attempted_keys: set[tuple[str, str, str, str]]
    template_stats: TemplateStats
    pending_futures: dict[Future[FieldTestResult], PendingFutureContext]
    field_queue_busy_counts: dict[str, int]
    skipped_fields_due_to_queue: set[str]
    resumable_simulations: list[PendingFutureContext] = field(default_factory=list)
    persisted_result_count: int = 0
    blacklist_runtime_stats: BlacklistRuntimeStats = field(default_factory=dict)
    blacklisted_template_keys: set[tuple[str, str, str]] = field(default_factory=set)
    last_submission_at: float = 0.0
    stop_signal: Event = field(default_factory=Event)

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

    def refresh_metrics(self) -> ExecutionMetrics:
        """Compatibility method returning the current derived snapshot."""
        return self.metrics


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
