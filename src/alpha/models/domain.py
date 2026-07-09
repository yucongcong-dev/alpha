"""
领域数据模型。

本模块只承载与业务领域直接相关的纯数据对象，
避免夹带 CLI、路径或运行时调度状态。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from ..config.constants import STATUS_ERROR
from .domain_conversion import coerce_failed_check, coerce_failed_checks, serialize_failed_check
from .domain_parsers import (
    parse_failed_check,
    parse_settings_variant,
    parse_template_field,
    parse_template_library_item,
)
from .domain_serializers import serialize_field_test_result
from .domain_serializers import (
    serialize_settings_variant,
    serialize_template_field,
    serialize_template_library_item,
)
from .domain_types import (
    AnalysisInputs,
    AnalysisPayload,
    FieldFeedbackMap,
    FieldFeedbackSummary,
    ResultRow,
    SummaryPayload,
    TemplateMetadata,
)


@dataclass(frozen=True)
class FailedCheck:
    """单条失败检查项。"""

    name: str
    value: float | None = None
    limit: float | None = None
    result: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """兼容 dict 风格的 get 方法。"""
        return getattr(self, key, default)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailedCheck:
        """兼容入口：从字典创建失败检查项。"""
        return parse_failed_check(data)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典表示。"""
        result: dict[str, Any] = {"name": self.name}
        if self.value is not None:
            result["value"] = self.value
        if self.limit is not None:
            result["limit"] = self.limit
        if self.result is not None:
            result["result"] = self.result
        return result

@dataclass(frozen=True)
class TemplateLibraryItem:
    """模板库中的单个模板项。"""

    name: str
    expression: str
    priority: int = 0
    family: str | None = None
    stage: str | None = None
    metadata: TemplateMetadata = field(default_factory=dict)

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> TemplateLibraryItem:
        """兼容入口：从字典创建模板项。"""
        return parse_template_library_item(item)

    def to_dict(self) -> dict[str, Any]:
        """兼容入口：序列化为模板项字典。"""
        return serialize_template_library_item(self)


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
    language: str | None = None
    instrument_type: str | None = None
    region: str | None = None
    universe: str | None = None
    delay: int | None = None
    start_date: str | None = None
    end_date: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """兼容旧的 dict 风格读取。"""
        return getattr(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        """兼容入口：序列化为设置变体字典。"""
        return serialize_settings_variant(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SettingsVariant:
        """兼容入口：从字典创建设置变体。"""
        return parse_settings_variant(data)


@dataclass(frozen=True)
class TemplateField:
    """字段元数据数据类（不可变）。"""

    field_id: str
    field_name: str
    field_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, field: dict[str, Any]) -> TemplateField:
        """兼容入口：从字典创建字段对象。"""
        return parse_template_field(field)

    def get(self, key: str, default: Any = None) -> Any:
        """兼容 dict 风格的 get 方法。"""
        return self.metadata.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """兼容入口：序列化为字段字典。"""
        return serialize_template_field(self)


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
    simulation_id: str | None = None
    alpha_id: str | None = None
    status: str = "unknown"
    submittable: bool | None = None
    submitted: bool = False
    message: str = ""
    expression: str = ""
    settings_fingerprint: str = ""
    template_library_fingerprint: str = ""
    failed_stage: str | None = None
    failed_checks: list[FailedCheck] | None = None

    def __post_init__(self) -> None:
        if self.failed_checks is not None:
            self.failed_checks = [coerce_failed_check(check) for check in self.failed_checks]

    def is_successful(self) -> bool:
        return self.submittable is True

    def to_dict(self) -> ResultRow:
        """兼容入口：序列化为结果行字典。"""
        return serialize_field_test_result(self)

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

    def __iter__(self):
        yield self.name
        yield self.expression
        yield self.priority

    def __getitem__(self, index: int):
        return (self.name, self.expression, self.priority)[index]


@dataclass(frozen=True)
class NearPassCandidate:
    """阶段 3 refine 使用的近门槛候选。"""

    field_id: str
    field_name: str
    template_name: str
    expression: str
    template_family: str = ""
    template_stage: str = ""
    score: float = 0.0
    failed_checks: list[FailedCheck] = field(default_factory=list)


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
    settings_fingerprint: str = ""
    template_library_fingerprint: str = ""

    def failure(
        self,
        *,
        failed_stage: str,
        message: str,
        simulation_id: str | None = None,
        alpha_id: str | None = None,
        status: str = STATUS_ERROR,
        failed_checks: Sequence[FailedCheck | dict[str, Any]] | None = None,
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
            simulation_id=simulation_id,
            alpha_id=alpha_id,
            status=status,
            submittable=False,
            submitted=False,
            message=message,
            expression=self.expression,
            settings_fingerprint=self.settings_fingerprint,
            template_library_fingerprint=self.template_library_fingerprint,
            failed_stage=failed_stage,
            failed_checks=coerce_failed_checks(failed_checks),
        )

    def success(
        self,
        *,
        simulation_id: str | None,
        alpha_id: str | None,
        submittable: bool | None,
        submitted: bool,
        message: str,
        status: str = "simulated",
        failed_checks: list[FailedCheck] | None = None,
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
            simulation_id=simulation_id,
            alpha_id=alpha_id,
            status=status,
            submittable=submittable,
            submitted=submitted,
            message=message,
            expression=self.expression,
            settings_fingerprint=self.settings_fingerprint,
            template_library_fingerprint=self.template_library_fingerprint,
            failed_checks=failed_checks,
        )
