"""
运行时上下文与状态模型。

本模块承载执行期、调度期和初始化期的上下文对象。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import time
from typing import Any, Protocol, Union

from ..config.models import DatasetExpressionPolicy
from .domain import (
    FieldFeedbackMap,
    FieldFeedbackSummary,
    FieldTestResult,
    TemplateCandidate,
    TemplateLibrary,
)
from .io_types import RunFilters

TemplateField = dict[str, Any]
TemplateFeedback = FieldFeedbackSummary
TemplateStats = dict[str, dict[str, int]]
RunConfig = dict[str, Any]
BlacklistRuntimeStats = dict[str, dict[str, Any]]


class ApiClientArgs(Protocol):
    min_request_interval: object
    rate_limit_max_retries: object
    login_retries: object


class TemplateBuildArgs(Protocol):
    dataset_id: object
    max_templates_per_field: object
    max_templates_per_family: object
    legacy_similarity_penalty: object
    template_disable_after: object
    disable_legacy_after: object
    region: object
    universe: object
    instrument_type: object
    delay: object
    decay: object
    neutralization: object
    truncation: object
    pasteurization: object
    unit_handling: object
    nan_handling: object
    language: object
    start_date: object
    end_date: object


class ResultWriteArgs(Protocol):
    dataset_id: object
    output: object
    auto_update_blacklist: object


class CleanRuntimeArgs(Protocol):
    include_credentials: object
    dry_run_clean: object


class CredentialsArgs(Protocol):
    email: object
    password: object
    creds_file: object
    creds_key_file: object


class FieldFetchArgs(Protocol):
    dataset_id: object
    page_size: object
    region: object
    universe: object
    instrument_type: object
    delay: object


class FieldSelectionArgs(Protocol):
    top_fields_by_feedback: object
    offset: object
    limit: object


class RunConfigArgs(Protocol):
    dataset_id: object
    region: object
    universe: object
    instrument_type: object
    delay: object
    decay: object
    neutralization: object
    truncation: object
    nan_handling: object
    limit: object
    offset: object
    page_size: object
    sleep_between_fields: object
    max_templates_per_field: object
    max_templates_per_family: object
    field_template_batch_size: object
    legacy_similarity_penalty: object
    disable_legacy_after: object
    max_concurrent_simulations: object
    max_concurrent_creates: object
    simulation_create_retries: object
    simulation_poll_retries: object
    simulation_max_polls: object
    simulation_max_wait_seconds: object
    simulation_max_pending_cycles: object
    simulation_max_queue_seconds: object
    queue_busy_cooldown_seconds: object
    field_queue_busy_skip_after: object
    check_submit_retries: object
    submit_retries: object
    rate_limit_max_retries: object
    login_retries: object
    min_request_interval: object
    template_disable_after: object
    top_fields_by_feedback: object
    stop_after_submittable: object
    submit: object
    auto_update_blacklist: object
    smoke_test: object
    dry_run_plan: object
    full_run: object
    verbose: object
    quiet: object


class StopAfterSubmittableArgs(Protocol):
    stop_after_submittable: object


class BootstrapRuntimeArgs(
    ApiClientArgs,
    CredentialsArgs,
    FieldFetchArgs,
    FieldSelectionArgs,
    RunConfigArgs,
    Protocol,
):
    output: object
    template_library_file: object
    fields_cache_file: object
    max_concurrent_simulations: object
    max_concurrent_creates: object


class SimulationSettingsArgs(Protocol):
    instrument_type: object
    region: object
    universe: object
    delay: object
    decay: object
    neutralization: object
    truncation: object
    pasteurization: object
    unit_handling: object
    nan_handling: object
    language: object
    start_date: object
    end_date: object


class SimulationStageArgs(SimulationSettingsArgs, Protocol):
    simulation_create_retries: object
    simulation_poll_retries: object
    simulation_max_polls: object
    simulation_max_wait_seconds: object
    simulation_max_pending_cycles: object
    simulation_max_queue_seconds: object
    check_submit_retries: object
    submit_retries: object
    submit: object
    min_sharpe: object
    min_fitness: object
    min_turnover: object
    max_turnover: object
    max_weight: object


class SchedulerRuntimeArgs(Protocol):
    queue_busy_cooldown_seconds: object
    field_queue_busy_skip_after: object
    sleep_between_fields: object
    dataset_id: object
    output: object
    auto_update_blacklist: object


class RunLoopArgs(SimulationStageArgs, SchedulerRuntimeArgs, StopAfterSubmittableArgs, Protocol):
    dry_run_plan: object
    field_template_batch_size: object


class ClientFactoryLike(Protocol):
    def create_client(self) -> object: ...


class SemaphoreLike(Protocol):
    def acquire(self, blocking: bool = True, timeout: float | None = -1) -> bool: ...

    def release(self) -> None: ...


@dataclass(frozen=True)
class ApiClientOptions:
    """API 客户端与线程级 worker client 的窄配置。"""

    min_request_interval: float = 0.0
    rate_limit_max_retries: int = 0
    login_retries: int = 0

    @classmethod
    def from_args(cls, args: ApiClientArgs) -> ApiClientOptions:
        return cls(
            min_request_interval=float(getattr(args, "min_request_interval", 0.0) or 0.0),
            rate_limit_max_retries=int(getattr(args, "rate_limit_max_retries", 0) or 0),
            login_retries=int(getattr(args, "login_retries", 0) or 0),
        )


@dataclass(frozen=True)
class TemplateBuildOptions:
    """模板选择、反馈回路与 settings 变体展开所需的窄配置。"""

    dataset_id: str = ""
    max_templates_per_field: int = 0
    max_templates_per_family: int = 0
    legacy_similarity_penalty: int = 0
    template_disable_after: int = 0
    disable_legacy_after: int = 0
    region: str = ""
    universe: str = ""
    instrument_type: str = ""
    delay: int = 0
    decay: int = 0
    neutralization: str = ""
    truncation: float = 0.0
    pasteurization: str = ""
    unit_handling: str = ""
    nan_handling: str = ""
    language: str = ""
    start_date: str | None = None
    end_date: str | None = None

    @classmethod
    def from_args(cls, args: TemplateBuildArgs) -> TemplateBuildOptions:
        return cls(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            max_templates_per_field=int(getattr(args, "max_templates_per_field", 0) or 0),
            max_templates_per_family=int(getattr(args, "max_templates_per_family", 0) or 0),
            legacy_similarity_penalty=int(getattr(args, "legacy_similarity_penalty", 0) or 0),
            template_disable_after=int(getattr(args, "template_disable_after", 0) or 0),
            disable_legacy_after=int(getattr(args, "disable_legacy_after", 0) or 0),
            region=str(getattr(args, "region", "") or ""),
            universe=str(getattr(args, "universe", "") or ""),
            instrument_type=str(getattr(args, "instrument_type", "") or ""),
            delay=int(getattr(args, "delay", 0) or 0),
            decay=int(getattr(args, "decay", 0) or 0),
            neutralization=str(getattr(args, "neutralization", "") or ""),
            truncation=float(getattr(args, "truncation", 0.0) or 0.0),
            pasteurization=str(getattr(args, "pasteurization", "") or ""),
            unit_handling=str(getattr(args, "unit_handling", "") or ""),
            nan_handling=str(getattr(args, "nan_handling", "") or ""),
            language=str(getattr(args, "language", "") or ""),
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
        )


@dataclass(frozen=True)
class ResultWriteOptions:
    """future 完成后结果落盘与副作用所需的窄配置。"""

    dataset_id: str = ""
    output_path: str = ""
    auto_update_blacklist: bool = False

    @classmethod
    def from_args(cls, args: ResultWriteArgs) -> ResultWriteOptions:
        return cls(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            output_path=str(getattr(args, "output", "") or ""),
            auto_update_blacklist=bool(getattr(args, "auto_update_blacklist", False)),
        )


@dataclass(frozen=True)
class FieldFetchOptions:
    """字段缓存校验与字段列表拉取所需的窄配置。"""

    dataset_id: str = ""
    page_size: int = 0
    region: str = ""
    universe: str = ""
    instrument_type: str = ""
    delay: int = 0

    @classmethod
    def from_args(cls, args: FieldFetchArgs) -> FieldFetchOptions:
        return cls(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            page_size=int(getattr(args, "page_size", 0) or 0),
            region=str(getattr(args, "region", "") or ""),
            universe=str(getattr(args, "universe", "") or ""),
            instrument_type=str(getattr(args, "instrument_type", "") or ""),
            delay=int(getattr(args, "delay", 0) or 0),
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


@dataclass
class TemplateBuildContext:
    """模板队列构建的只读上下文数据类。"""

    options: TemplateBuildOptions = field(default_factory=TemplateBuildOptions)
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
    """执行过程中可变的待运行、跳过与累计结果状态。"""

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
    blacklisted_template_names: set[str] = field(default_factory=set)
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


PendingFutureLike = Union[PendingFutureContext, dict[str, object]]
TemplateSequence = Sequence[TemplateCandidate]
