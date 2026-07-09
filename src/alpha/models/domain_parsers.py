"""Parsers that convert JSON-like payloads into domain dataclasses."""

from __future__ import annotations

from typing import Any


def parse_failed_check(data: dict[str, Any]) -> "FailedCheck":
    """从字典创建失败检查项。"""
    from .domain import FailedCheck

    return FailedCheck(
        name=str(data.get("name", "")),
        value=data.get("value"),
        limit=data.get("limit"),
        result=data.get("result"),
    )


def parse_template_library_item(item: dict[str, Any]) -> "TemplateLibraryItem":
    """从字典创建模板项。"""
    from .domain import TemplateLibraryItem

    return TemplateLibraryItem(
        name=str(item["name"]),
        expression=str(item["expression"]),
        priority=int(item.get("priority", 0)),
        family=item.get("family"),
        stage=item.get("stage"),
        metadata=item.get("metadata", {}),
    )


def parse_settings_variant(data: dict[str, Any]) -> "SettingsVariant":
    """从字典创建设置变体。"""
    from .domain import SettingsVariant

    return SettingsVariant(
        decay=data.get("decay"),
        neutralization=data.get("neutralization"),
        truncation=data.get("truncation"),
        pasteurization=data.get("pasteurization"),
        unit_handling=data.get("unit_handling", data.get("unitHandling")),
        nan_handling=data.get("nan_handling", data.get("nanHandling")),
        language=data.get("language"),
        instrument_type=data.get("instrument_type", data.get("instrumentType")),
        region=data.get("region"),
        universe=data.get("universe"),
        delay=data.get("delay"),
        start_date=data.get("start_date", data.get("startDate")),
        end_date=data.get("end_date", data.get("endDate")),
        visualization=data.get("visualization"),
    )


def parse_template_field(field: dict[str, Any]) -> "TemplateField":
    """从字典创建字段对象，兼容 API 原始格式和旧版序列化格式。"""
    from .domain import TemplateField

    if "field_id" in field and "metadata" in field and isinstance(field.get("metadata"), dict):
        nested = field["metadata"]
        return TemplateField(
            field_id=str(field.get("field_id", "")),
            field_name=str(field.get("field_name", "")),
            field_type=str(field.get("field_type", "UNKNOWN")).upper(),
            metadata=dict(nested),
        )
    field_id = str(field.get("id") or field.get("name") or field.get("mnemonic") or "")
    field_name = str(field.get("name") or field.get("id") or field.get("mnemonic") or "")
    field_type = str(
        field.get("type") or field.get("fieldType") or field.get("category") or "UNKNOWN"
    ).upper()
    return TemplateField(
        field_id=field_id,
        field_name=field_name,
        field_type=field_type,
        metadata=dict(field),
    )
