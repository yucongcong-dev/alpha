"""Typed bootstrap data carriers."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Semaphore

from ..config.models import DatasetExpressionPolicy
from ..models.domain import TemplateField, TemplateLibrary
from ..models.io_types import RunFilters
from ..models.runtime_protocols import RunConfig
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import HistoricalRunState


@dataclass(frozen=True)
class PreparedBootstrapResources:
    """模板、过滤器、反馈和字段等初始化资源集合。"""

    template_library: TemplateLibrary
    filters: RunFilters
    expression_policy: DatasetExpressionPolicy
    use_dataset_heuristics: bool
    template_library_fingerprint: str
    settings_fingerprint: str
    run_fingerprint: str
    historical_state: HistoricalRunState
    fields: list[TemplateField]
    run_config: RunConfig


@dataclass(frozen=True)
class RuntimeConcurrencyResources:
    """初始化阶段产出的并发调度资源。"""

    runtime_state: RuntimeConcurrencyState
    create_semaphore: Semaphore
