"""
运行时上下文与状态模型。

本模块承载执行期、调度期和初始化期的上下文对象。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import time
from typing import Any

from ..config import DatasetExpressionPolicy
from .domain import FieldTestResult, TemplateLibrary
from .io_types import RunFilters


@dataclass(frozen=True)
class ApiClientOptions:
    """API 客户端与线程级 worker client 的窄配置。"""

    min_request_interval: float = 0.0
    rate_limit_max_retries: int = 0
    login_retries: int = 0

    @classmethod
    def from_args(cls, args: Any) -> "ApiClientOptions":
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
    def from_args(cls, args: Any) -> "TemplateBuildOptions":
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
    def from_args(cls, args: Any) -> "ResultWriteOptions":
        return cls(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            output_path=str(getattr(args, "output", "") or ""),
            auto_update_blacklist=bool(getattr(args, "auto_update_blacklist", False)),
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
    all_fields: Sequence[dict[str, Any]] = field(default_factory=list)
    template_library: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    field_feedback: dict[str, dict[str, Any]] = field(default_factory=dict)
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
    run_config: dict[str, Any] | None = None


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
    template_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    field_feedback: dict[str, dict[str, Any]] = field(default_factory=dict)
    global_failed_check_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ExecutionState:
    """执行过程中可变的待运行、跳过与累计结果状态。"""

    results: list[FieldTestResult]
    attempted_keys: set[tuple[str, str, str, str]]
    template_stats: dict[str, dict[str, int]]
    pending_futures: dict[Any, PendingFutureContext]
    field_queue_busy_counts: dict[str, int]
    skipped_fields_due_to_queue: set[str]
    unique_field_ids: set[str] = field(default_factory=set)
    submittable_count: int = 0
    submitted_count: int = 0
    error_count: int = 0
    queue_timeout_count: int = 0
    persisted_result_count: int = 0
    blacklist_runtime_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    blacklisted_template_names: set[str] = field(default_factory=set)
    last_submission_at: float = 0.0


@dataclass(frozen=True)
class InitializedRunContext:
    """初始化阶段产出的主流程上下文。"""

    client_factory: Any
    template_library: TemplateLibrary
    filters: RunFilters
    expression_policy: DatasetExpressionPolicy
    use_dataset_heuristics: bool
    template_library_fingerprint: str
    settings_fingerprint: str
    historical_state: HistoricalRunState
    fields: list[dict[str, Any]]
    execution_state: ExecutionState
    runtime_state: RuntimeConcurrencyState
    create_semaphore: Any
    run_config: dict[str, Any]
