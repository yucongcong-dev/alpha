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


@dataclass
class ExecutionState:
    """执行过程中可变的待运行、跳过与累计结果状态。"""

    results: list[FieldTestResult]
    attempted_keys: set[tuple[str, str, str, str]]
    template_stats: TemplateStats
    pending_futures: dict[Future[FieldTestResult], PendingFutureContext]
    field_queue_busy_counts: dict[str, int]
    skipped_fields_due_to_queue: set[str]
    unique_field_ids: set[str] = field(default_factory=set)
    submittable_count: int = 0
    submitted_count: int = 0
    error_count: int = 0
    queue_timeout_count: int = 0
    persisted_result_count: int = 0
    blacklist_runtime_stats: BlacklistRuntimeStats = field(default_factory=dict)
    blacklisted_template_keys: set[tuple[str, str, str]] = field(default_factory=set)
    last_submission_at: float = 0.0


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
