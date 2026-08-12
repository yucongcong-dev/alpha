"""
领域数据模型。

本模块只承载与业务领域直接相关的纯数据对象，
避免夹带 CLI、路径或运行时调度状态。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ..config._constants_strings import STATUS_ERROR
from .domain_types import (
    AnalysisInputs as AnalysisInputs,
)
from .domain_types import (
    AnalysisPayload as AnalysisPayload,
)
from .domain_types import (
    FieldFeedbackMap as FieldFeedbackMap,
)
from .domain_types import (
    FieldFeedbackSummary as FieldFeedbackSummary,
)
from .domain_types import (
    ResultRow as ResultRow,
)
from .domain_types import (
    SummaryPayload as SummaryPayload,
)
from .domain_types import (
    TemplateMetadata,
)


@dataclass(frozen=True)
class FailedCheck:
    """单条失败检查项。"""

    name: str
    value: float | None = None
    limit: float | None = None
    result: str | None = None


@dataclass(frozen=True)
class TemplateLibraryItem:
    """模板库中的单个模板项。"""

    name: str
    expression: str
    priority: int = 0
    family: str | None = None
    stage: str | None = None
    metadata: TemplateMetadata = field(default_factory=dict)


TemplateLibrary = dict[str, list[TemplateLibraryItem]]
"""模板库类型：键为字段类型（如 "MATRIX"），值为模板项列表。"""


@dataclass(frozen=True)
class SettingsVariant:
    """模拟设置变体数据类（不可变）。"""

    decay: int | None = None
    neutralization: str | None = None
    truncation: float | None = None
    pasteurization: bool | None = None
    unit_handling: str | None = None
    nan_handling: str | None = None
    max_trade: str | None = None
    language: str | None = None
    instrument_type: str | None = None
    region: str | None = None
    universe: str | None = None
    delay: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    visualization: bool | None = None


@dataclass(frozen=True)
class TemplateField:
    """字段元数据数据类（不可变）。"""

    field_id: str
    field_name: str
    field_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FieldTestResult:
    """字段模板测试结果数据类。"""

    field_id: str
    field_type: str
    field_name: str
    template_name: str
    template_family: str = ""
    template_stage: str = ""
    template_role: str = ""
    template_activation_scope: str = ""
    policy_version: str = ""
    simulation_id: str | None = None
    alpha_id: str | None = None
    status: str = "unknown"
    submittable: bool | None = None
    message: str = ""
    expression: str = ""
    settings_fingerprint: str = ""
    template_library_fingerprint: str = ""
    settings: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    region: str = ""
    universe: str = ""
    instrument_type: str = ""
    delay: int | None = None
    run_name: str = ""
    source_summary: str = ""
    created_at: str = ""
    updated_at: str = ""
    revision: int = 1
    failed_stage: str | None = None
    failed_checks: list[FailedCheck] | None = None

    def __str__(self) -> str:
        status_symbol = "✓" if self.submittable else "✗"
        return f"FieldTestResult({self.field_name}/{self.template_name}: {status_symbol})"


@dataclass(frozen=True)
class FieldView:
    """模板构建消费的字段视图。"""

    field_id: str
    field_name: str
    field_type: str
    raw_expression: str
    preprocessed_expression: str
    groupfill_expression: str
    ratio_numerator_expression: str
    ratio_denominator_expression: str
    metadata: TemplateMetadata = field(default_factory=dict)


@dataclass(frozen=True)
class TemplateCandidate:
    """统一的模板候选结构。"""

    name: str
    expression: str
    priority: int
    metadata: TemplateMetadata = field(default_factory=dict)


@dataclass
class FieldTestContext:
    """字段测试运行上下文数据类。"""

    field_id: str
    field_type: str
    field_name: str
    template_name: str
    expression: str
    template_family: str = ""
    template_stage: str = ""
    template_role: str = ""
    template_activation_scope: str = ""
    policy_version: str = ""
    settings_fingerprint: str = ""
    template_library_fingerprint: str = ""
    settings: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    def failure(
        self,
        *,
        failed_stage: str,
        message: str,
        simulation_id: str | None = None,
        alpha_id: str | None = None,
        status: str = STATUS_ERROR,
        failed_checks: Sequence[FailedCheck] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> FieldTestResult:
        return FieldTestResult(
            field_id=self.field_id,
            field_type=self.field_type,
            field_name=self.field_name,
            template_name=self.template_name,
            template_family=self.template_family,
            template_stage=self.template_stage,
            template_role=self.template_role,
            template_activation_scope=self.template_activation_scope,
            policy_version=self.policy_version,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
            status=status,
            submittable=False,
            message=message,
            expression=self.expression,
            settings_fingerprint=self.settings_fingerprint,
            template_library_fingerprint=self.template_library_fingerprint,
            settings=dict(self.settings),
            metrics=dict(self.metrics if metrics is None else metrics),
            failed_stage=failed_stage,
            failed_checks=list(failed_checks or []),
        )

    def success(
        self,
        *,
        simulation_id: str | None,
        alpha_id: str | None,
        submittable: bool | None,
        message: str,
        status: str = "simulated",
        failed_checks: list[FailedCheck] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> FieldTestResult:
        return FieldTestResult(
            field_id=self.field_id,
            field_type=self.field_type,
            field_name=self.field_name,
            template_name=self.template_name,
            template_family=self.template_family,
            template_stage=self.template_stage,
            template_role=self.template_role,
            template_activation_scope=self.template_activation_scope,
            policy_version=self.policy_version,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
            status=status,
            submittable=submittable,
            message=message,
            expression=self.expression,
            settings_fingerprint=self.settings_fingerprint,
            template_library_fingerprint=self.template_library_fingerprint,
            settings=dict(self.settings),
            metrics=dict(self.metrics if metrics is None else metrics),
            failed_checks=failed_checks,
        )
