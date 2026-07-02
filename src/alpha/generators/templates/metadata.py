"""
模板库元数据索引。

本模块负责从基础模板、字段类型模板和数据集专属模板中提取运行时
元数据，并为已渲染表达式建立查询索引。
"""

from __future__ import annotations

from typing import Any

from ...config import get_backfill_window
from ...models.base import TemplateLibrary

TemplateMetadataMap = dict[tuple[str, str], dict[str, Any]]
"""表达式构建阶段使用的模板元数据映射。key=(template_name, expression)。"""


def _template_key(template_name: str, expression: str) -> tuple[str, str]:
    """生成模板元数据映射键。"""
    return (template_name, expression)


def _runtime_template_metadata(item: dict[str, Any]) -> dict[str, Any]:
    """提取运行时需要的模板元数据。"""
    return {
        key: item[key]
        for key in ("family", "layer", "stage", "requires_partner_field", "field_kinds", "dataset_tags")
        if key in item
    }


def _dataset_template_keys(field_type: str, dataset_id: str) -> list[str]:
    """返回模板库检索键，支持数据集专属模板分层。"""
    keys = ["default"]
    if field_type:
        keys.append(field_type)
    if dataset_id:
        dataset_key = dataset_id.upper()
        keys.append(f"DATASET_{dataset_key}")
        if field_type:
            keys.append(f"DATASET_{dataset_key}_{field_type}")
    return keys


def _select_template_items(
    template_library: TemplateLibrary,
    field_type: str,
    dataset_id: str,
) -> list[dict[str, Any]]:
    """合并基础模板、字段类型模板和数据集专属模板，后者可覆盖前者。"""
    merged: dict[str, dict[str, Any]] = {}
    for key in _dataset_template_keys(field_type, dataset_id):
        for item in template_library.get(key, []):
            if isinstance(item, dict) and "name" in item and "expression" in item:
                merged[str(item["name"])] = item
    return list(merged.values())


def build_template_metadata_index(
    field_view: Any,
    template_library: TemplateLibrary,
    field_type: str,
    dataset_id: str,
) -> TemplateMetadataMap:
    """为当前字段构建已渲染模板的元数据索引。"""
    metadata_by_key: TemplateMetadataMap = {}
    raw_templates = _select_template_items(template_library, field_type, dataset_id)
    for item in raw_templates:
        if not isinstance(item, dict) or "name" not in item or "expression" not in item:
            continue
        rendered_expression = str(item["expression"]).format(
            field=field_view.raw_expression,
            field_preprocessed=field_view.preprocessed_expression,
            ratio_numerator=field_view.ratio_numerator_expression,
            ratio_denominator=field_view.ratio_denominator_expression,
            backfill_window=get_backfill_window(),
        )
        metadata = _runtime_template_metadata(item)
        if metadata:
            metadata_by_key[_template_key(str(item["name"]), rendered_expression)] = metadata
    return metadata_by_key


def get_template_metadata(
    template_name: str,
    expression: str,
    metadata_by_key: TemplateMetadataMap | None = None,
) -> dict[str, Any]:
    """查找模板元数据。"""
    return (metadata_by_key or {}).get(_template_key(template_name, expression), {})
