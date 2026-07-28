"""Runtime orchestration context dataclasses."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ..config.models import DatasetExpressionPolicy
from ..models.domain import (
    FieldTestResult,
    SettingsVariant,
    TemplateField,
    TemplateLibrary,
)
from ..models.domain_types import FieldFeedbackMap
from ..models.runtime_options import ResultWriteOptions, TemplateBuildOptions
from ..models.runtime_protocols import RunConfig, TemplateStats


@dataclass
class PendingFutureContext:
    """尚未完成的 future 元数据及可恢复的远端 simulation 状态。"""

    field_id: str = ""
    field_name: str = ""
    field_type: str = ""
    template_name: str = ""
    template_family: str = ""
    template_stage: str = ""
    template_role: str = ""
    template_activation_scope: str = ""
    policy_version: str = ""
    policy_arm: str = ""
    expression: str = ""
    settings_fingerprint: str = ""
    simulation_location: str = ""
    simulation_id: str = ""


@dataclass(frozen=True)
class PendingTemplateEntry:
    """单个待执行模板的完整信息（替代裸 tuple）。"""

    template_name: str
    template_family: str
    template_stage: str
    template_role: str
    template_activation_scope: str
    expression: str
    priority: int
    settings_variant: SettingsVariant
    variant_fingerprint: str
    policy_version: str = ""
    policy_arm: str = ""


@dataclass
class TemplateBuildContext:
    """模板队列构建的只读上下文数据类。"""

    options: TemplateBuildOptions
    template_library_file: str = ""
    all_fields: Sequence[TemplateField] = field(default_factory=list)
    template_library: TemplateLibrary = field(default_factory=dict)
    template_registry: dict[str, dict[str, object]] = field(default_factory=dict)
    template_family_registry: dict[str, dict[str, object]] = field(default_factory=dict)
    template_registry_overrides: dict[str, object] = field(default_factory=dict)
    field_feedback: FieldFeedbackMap = field(default_factory=dict)
    global_failed_check_counts: dict[str, int] = field(default_factory=dict)
    failed_check_counts_by_field_type: dict[str, dict[str, int]] = field(default_factory=dict)
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
class HistoricalRunState:
    """历史运行状态数据类。"""

    existing_results: list[FieldTestResult] = field(default_factory=list)
    attempted_keys: set[tuple[str, str, str, str]] = field(default_factory=set)
    template_stats: TemplateStats = field(default_factory=dict)
    template_registry: dict[str, dict[str, object]] = field(default_factory=dict)
    template_family_registry: dict[str, dict[str, object]] = field(default_factory=dict)
    template_registry_overrides: dict[str, object] = field(default_factory=dict)
    field_feedback: FieldFeedbackMap = field(default_factory=dict)
    global_failed_check_counts: dict[str, int] = field(default_factory=dict)
