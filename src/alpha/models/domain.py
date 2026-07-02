"""
领域数据模型。

本模块只承载与业务领域直接相关的纯数据对象，
避免夹带 CLI、路径或运行时调度状态。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TemplateLibrary = dict[str, list[dict[str, Any]]]
"""模板库类型别名。"""

SettingsVariant = dict[str, Any]
"""设置变体类型别名。"""


@dataclass
class FieldTestResult:
    """字段模板测试结果数据类。"""

    field_id: str
    field_type: str
    field_name: str
    template_name: str
    template_family: str = ""
    template_stage: str = ""
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
    failed_checks: list[dict[str, Any]] | None = None

    def is_successful(self) -> bool:
        return self.submittable is True

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "field_type": self.field_type,
            "field_name": self.field_name,
            "template_name": self.template_name,
            "template_family": self.template_family,
            "template_stage": self.template_stage,
            "simulation_id": self.simulation_id,
            "alpha_id": self.alpha_id,
            "status": self.status,
            "submittable": self.submittable,
            "submitted": self.submitted,
            "message": self.message,
            "expression": self.expression,
            "settings_fingerprint": self.settings_fingerprint,
            "template_library_fingerprint": self.template_library_fingerprint,
            "failed_stage": self.failed_stage,
            "failed_checks": self.failed_checks,
        }

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
    ratio_numerator_expression: str
    ratio_denominator_expression: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemplateCandidate:
    """统一的模板候选结构。"""

    name: str
    expression: str
    priority: int
    metadata: dict[str, Any] = field(default_factory=dict)

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
    failed_checks: list[dict[str, Any]] = field(default_factory=list)


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
    settings_fingerprint: str = ""
    template_library_fingerprint: str = ""

    def failure(
        self,
        *,
        failed_stage: str,
        message: str,
        simulation_id: str | None = None,
        alpha_id: str | None = None,
        status: str = "error",
        failed_checks: list[dict[str, Any]] | None = None,
    ) -> FieldTestResult:
        return FieldTestResult(
            field_id=self.field_id,
            field_type=self.field_type,
            field_name=self.field_name,
            template_name=self.template_name,
            template_family=self.template_family,
            template_stage=self.template_stage,
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
            failed_checks=failed_checks,
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
        failed_checks: list[dict[str, Any]] | None = None,
    ) -> FieldTestResult:
        return FieldTestResult(
            field_id=self.field_id,
            field_type=self.field_type,
            field_name=self.field_name,
            template_name=self.template_name,
            template_family=self.template_family,
            template_stage=self.template_stage,
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
