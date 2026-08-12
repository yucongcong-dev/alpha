"""Parsers that convert JSON-like payloads into domain dataclasses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .domain import FailedCheck, SettingsVariant, TemplateField


def parse_failed_check(data: Mapping[str, Any]) -> FailedCheck:
    """从字典创建失败检查项。"""
    return FailedCheck(
        name=str(data.get("name", "")),
        value=data.get("value"),
        limit=data.get("limit", data.get("threshold")),
        result=data.get("result"),
    )


def coerce_failed_checks(
    checks: Sequence[FailedCheck | Mapping[str, Any]] | None,
) -> list[FailedCheck]:
    """Normalize optional failed-check payloads at the JSON/domain boundary."""
    if not checks:
        return []
    return [
        check if isinstance(check, FailedCheck) else parse_failed_check(check) for check in checks
    ]


def parse_settings_variant(data: dict[str, Any]) -> SettingsVariant:
    """从字典创建设置变体。"""
    return SettingsVariant(
        decay=data.get("decay"),
        neutralization=data.get("neutralization"),
        truncation=data.get("truncation"),
        pasteurization=data.get("pasteurization"),
        unit_handling=data.get("unit_handling", data.get("unitHandling")),
        nan_handling=data.get("nan_handling", data.get("nanHandling")),
        max_trade=data.get("max_trade", data.get("maxTrade")),
        language=data.get("language"),
        instrument_type=data.get("instrument_type", data.get("instrumentType")),
        region=data.get("region"),
        universe=data.get("universe"),
        delay=data.get("delay"),
        start_date=data.get("start_date", data.get("startDate")),
        end_date=data.get("end_date", data.get("endDate")),
        visualization=data.get("visualization"),
    )


def parse_template_field(field: dict[str, Any]) -> TemplateField:
    """从字典创建字段对象，兼容 API 原始格式和旧版序列化格式。"""
    if "field_id" in field and "metadata" in field and isinstance(field.get("metadata"), dict):
        return TemplateField(
            field_id=str(field.get("field_id", "")),
            field_name=str(field.get("field_name", "")),
            field_type=str(field.get("field_type", "UNKNOWN")).upper(),
            metadata=dict(field["metadata"]),
        )
    return TemplateField(
        field_id=str(field.get("id") or field.get("name") or field.get("mnemonic") or ""),
        field_name=str(field.get("name") or field.get("id") or field.get("mnemonic") or ""),
        field_type=str(
            field.get("type") or field.get("fieldType") or field.get("category") or "UNKNOWN"
        ).upper(),
        metadata=dict(field),
    )
