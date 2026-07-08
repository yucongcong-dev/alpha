"""Runtime state and orchestration dataclasses."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import time
from typing import Union

from ..config.models import DatasetExpressionPolicy
from .domain import (
    FieldFeedbackMap,
    FieldTestResult,
    SettingsVariant,
    TemplateField,
    TemplateLibrary,
)
from .io_types import RunFilters
from .runtime_options import ResultWriteOptions, TemplateBuildOptions
from .runtime_protocols import (
    BlacklistRuntimeStats,
    ClientFactoryLike,
    RunConfig,
    SemaphoreLike,
    TemplateStats,
)
from .runtime_protocols import (
    PendingFutureLike as PendingFuturePayload,
)


@dataclass(frozen=True)
class PendingFutureContext:
    """尚未完成的 future 对应的只读元数据。"""

    field_id: str = ""
    field_name: str = ""
    field_type: str = ""
    template_name: str = ""
    template_family: str = ""
    template_stage: str = ""
    expression: str = ""
    settings_fingerprint: str = ""


@dataclass(frozen=True)
class PendingTemplateEntry:
    """单个待执行模板的完整信息（替代裸 tuple）。"""

    template_name: str
    template_family: str
    template_stage: str
    expression: str
    priority: int
    settings_variant: SettingsVariant
    variant_fingerprint: str


@dataclass
class TemplateBuildContext:
    """模板队列构建的只读上下文数据类。"""

    options: TemplateBuildOptions = field(default_factory=TemplateBuildOptions)
    template_library_file: str = ""
    all_fields: Sequence[TemplateField] = field(default_factory=list)
    template_library: TemplateLibrary = field(default_factory=dict)
    field_feedback: FieldFeedbackMap = field(default_factory=dict)
    global_failed_check_counts: dict[str, int] = field(default_factory=dict)
    include_templates: set[str] = field(default_factory=set)
    exclude_templates: set[str] = field(default_factory=set)
    use_dataset_heuristics: bool = False
    expression_policy: DatasetExpressionPolicy | None = None
    feedback_result_count: int = -1


@dataclass
class FutureCompletionContext:
    """future 完成处理的不可变配置上下文。"""

    result_write_options: ResultWriteOptions = field(default_factory=ResultWriteOptions)
    settings_fingerprint: str = ""
    template_library_fingerprint: str = ""
    run_config: RunConfig | None = None


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
class HistoricalRunState:
    """历史运行状态数据类。"""

    existing_results: list[FieldTestResult] = field(default_factory=list)
    attempted_keys: set[tuple[str, str, str, str]] = field(default_factory=set)
    template_stats: TemplateStats = field(default_factory=dict)
    field_feedback: FieldFeedbackMap = field(default_factory=dict)
    global_failed_check_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ExecutionState:
    """执行过程中可变的待运行、跳过与累计结果状态。

    Thread Safety:
    This class is shared across multiple threads and must be accessed with
    proper synchronization. The following describes the ownership and access
    patterns for each field:

    Fields modified by the MAIN THREAD only:
    - unique_field_ids: Populated during field preparation phase
    - last_submission_at: Updated when submissions occur

    Fields modified by WORKER THREADS (via handle_completed_future):
    - results: Appended with completed FieldTestResult objects
    - attempted_keys: Updated with (field_id, template_name, expression, fingerprint) tuples
    - template_stats: Updated via update_template_stats_with_result
    - pending_futures: Popped when futures complete
    - field_queue_busy_counts: Updated when queue congestion is detected
    - skipped_fields_due_to_queue: Updated when fields are skipped
    - submittable_count: Incremented for submittable results
    - submitted_count: Incremented for submitted results
    - error_count: Incremented for failed results
    - queue_timeout_count: Incremented for queue timeouts
    - persisted_result_count: Incremented after result persistence
    - blacklist_runtime_stats: Updated via build_blacklist_runtime_stats
    - blacklisted_template_keys: Updated when templates are blacklisted

    Fields read by multiple threads:
    - results: Read for progress tracking and checkpointing
    - attempted_keys: Read to avoid duplicate submissions
    - pending_futures: Read for inflight tracking
    - submittable_count: Read for stop_after_submittable logic
    - submitted_count: Read for progress reporting

    Synchronization Protocol:
    All modifications to this object must be performed under the lock provided
    by the caller (typically a threading.Lock). The run_loop module is
    responsible for acquiring/releasing the lock when accessing ExecutionState.

    The following methods in alpha.core.scheduler are thread-safe when called
    with proper locking:
    - handle_completed_future()
    - drain_completed_futures()
    """

    results: list[FieldTestResult]
    attempted_keys: set[tuple[str, str, str, str]]
    template_stats: TemplateStats
    pending_futures: dict[object, PendingFutureContext]
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


PendingFutureLike = Union[PendingFutureContext, PendingFuturePayload]
