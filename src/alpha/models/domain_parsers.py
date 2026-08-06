"""Parsers that convert JSON-like payloads into domain dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .domain import FailedCheck, SettingsVariant, TemplateField, TemplateLibraryItem


def parse_failed_check(data: Mapping[str, Any]) -> FailedCheck:
    """从字典创建失败检查项。"""
    return FailedCheck.from_dict(dict(data))


def parse_template_library_item(item: dict[str, Any]) -> TemplateLibraryItem:
    """从字典创建模板项。"""
    return TemplateLibraryItem.from_dict(item)


def parse_settings_variant(data: dict[str, Any]) -> SettingsVariant:
    """从字典创建设置变体。"""
    return SettingsVariant.from_dict(data)


def parse_template_field(field: dict[str, Any]) -> TemplateField:
    """从字典创建字段对象，兼容 API 原始格式和旧版序列化格式。"""
    return TemplateField.from_dict(field)
