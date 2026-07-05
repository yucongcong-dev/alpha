"""
领域数据模型。

本模块只承载与业务领域直接相关的纯数据对象，
避免夹带 CLI、路径或运行时调度状态。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config.constants import STATUS_ERROR

FieldFeedbackSummary = dict[str, Any]
"""单个字段的历史反馈画像。"""


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
        """从字典创建失败检查项。"""
        return cls(
            name=str(data.get("name", "")),
            value=data.get("value"),
            limit=data.get("limit"),
            result=data.get("result"),
        )

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


ResultRow = dict[str, Any]
"""结果落盘 / 分析阶段使用的通用行对象。"""

TemplateMetadata = dict[str, Any]
"""模板候选或字段视图附带的元数据。"""

FieldFeedbackMap = dict[str, FieldFeedbackSummary]
"""按字段 ID 聚合的反馈画像映射。"""

AnalysisInputs = dict[str, list[ResultRow]]
"""analysis sidecar 构建前的中间聚合输入。"""

SummaryPayload = dict[str, Any]
"""主结果文件 summary payload。"""

AnalysisPayload = dict[str, Any]
"""analysis sidecar payload。"""


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
        """从字典创建模板项。"""
        return cls(
            name=str(item["name"]),
            expression=str(item["expression"]),
            priority=int(item.get("priority", 0)),
            family=item.get("family"),
            stage=item.get("stage"),
            metadata=item.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 化的字典。"""
        return {
            "name": self.name,
            "expression": self.expression,
            "priority": self.priority,
            "family": self.family,
            "stage": self.stage,
            "metadata": self.metadata,
        }


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

    def to_dict(self) -> dict[str, Any]:
        """转换为字典表示。"""
        return {
            k: v for k, v in self.__dict__.items() if v is not None
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SettingsVariant:
        """从字典创建设置变体。"""
        return cls(
            decay=data.get("decay"),
            neutralization=data.get("neutralization"),
            truncation=data.get("truncation"),
            pasteurization=data.get("pasteurization"),
            unit_handling=data.get("unit_handling"),
            nan_handling=data.get("nan_handling"),
            language=data.get("language"),
            instrument_type=data.get("instrument_type"),
            region=data.get("region"),
            universe=data.get("universe"),
            delay=data.get("delay"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
        )


@dataclass(frozen=True)
class TemplateField:
    """字段元数据数据类（不可变）。"""

    field_id: str
    field_name: str
    field_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, field: dict[str, Any]) -> TemplateField:
        """从字典创建字段对象，兼容 API 原始格式和旧版序列化格式。"""
        if "field_id" in field and "metadata" in field and isinstance(field.get("metadata"), dict):
            nested = field["metadata"]
            return cls(
                field_id=str(field.get("field_id", "")),
                field_name=str(field.get("field_name", "")),
                field_type=str(field.get("field_type", "UNKNOWN")).upper(),
                metadata=dict(nested),
            )
        field_id = str(field.get("id") or field.get("name") or field.get("mnemonic") or "")
        field_name = str(field.get("name") or field.get("id") or field.get("mnemonic") or "")
        field_type = str(field.get("type") or field.get("fieldType") or field.get("category") or "UNKNOWN").upper()
        return cls(
            field_id=field_id,
            field_name=field_name,
            field_type=field_type,
            metadata=dict(field),
        )

    def get(self, key: str, default: Any = None) -> Any:
        """兼容 dict 风格的 get 方法。"""
        return self.metadata.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 化的字典，保留 API 返回的完整元数据。"""
        return dict(self.metadata)


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
    failed_checks: list[FailedCheck] | None = None


    def is_successful(self) -> bool:
        return self.submittable is True

    def to_dict(self) -> ResultRow:
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
            "failed_checks": [check.to_dict() if hasattr(check, "to_dict") else check for check in self.failed_checks] if self.failed_checks else None,

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
        failed_checks: list[FailedCheck] | None = None,
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
        failed_checks: list[FailedCheck] | None = None,
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
