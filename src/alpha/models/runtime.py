"""
运行时上下文与状态模型。

本模块承载执行期、调度期和初始化期的上下文对象。
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass, field
import time
from typing import Any

from ..config import DatasetExpressionPolicy
from .domain import FieldTestResult, TemplateLibrary
from .io_types import RunFilters


@dataclass
class TemplateBuildContext:
    """模板队列构建的只读上下文数据类。"""

    args: argparse.Namespace = field(default_factory=argparse.Namespace)
    all_fields: Sequence[dict[str, Any]] = field(default_factory=list)
    template_library: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    field_feedback: dict[str, dict[str, Any]] = field(default_factory=dict)
    global_failed_check_counts: dict[str, int] = field(default_factory=dict)
    include_templates: set[str] = field(default_factory=set)
    exclude_templates: set[str] = field(default_factory=set)
    use_dataset_heuristics: bool = False
    expression_policy: DatasetExpressionPolicy | None = None


@dataclass
class FutureCompletionContext:
    """future 完成处理的不可变配置上下文。"""

    args: argparse.Namespace = field(default_factory=argparse.Namespace)
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
    pending_futures: dict[Any, dict[str, Any]]
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
