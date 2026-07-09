"""Typed bootstrap data carriers."""

from __future__ import annotations

from dataclasses import dataclass

from ..config.models import DatasetExpressionPolicy
from ..models.domain import TemplateField, TemplateLibrary
from ..models.io_types import RunFilters
from ..models.runtime_protocols import RunConfig
from ..runtime import HistoricalRunState


@dataclass(frozen=True)
class ResolvedCredentials:
    """凭证加载所需的最小只读输入。"""

    email: str | None
    password: str | None
    creds_file: str
    creds_key_file: str


@dataclass(frozen=True)
class BootstrapPaths:
    """初始化阶段使用的归一化路径快照。"""

    output_file: str
    log_file: str
    template_library_file: str
    fields_cache_file: str
    feedback_output: str
    creds_file: str
    creds_key_file: str


@dataclass(frozen=True)
class PreparedBootstrapResources:
    """模板、过滤器、反馈和字段等初始化资源集合。"""

    template_library: TemplateLibrary
    filters: RunFilters
    expression_policy: DatasetExpressionPolicy
    use_dataset_heuristics: bool
    template_library_fingerprint: str
    settings_fingerprint: str
    historical_state: HistoricalRunState
    fields: list[TemplateField]
    run_config: RunConfig
