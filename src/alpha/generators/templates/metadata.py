"""
模板库元数据索引。

本模块负责从基础模板、字段类型模板和数据集专属模板中提取运行时
元数据，并为已渲染表达式建立查询索引。
"""

from __future__ import annotations

from ...models.domain import TemplateLibrary, TemplateLibraryItem
from ...models.domain_types import TemplateMetadata

TemplateMetadataMap = dict[tuple[str, str], TemplateMetadata]
"""表达式构建阶段使用的模板元数据映射。key=(template_name, expression)。"""


def normalize_template_role(role: object) -> str:
    """Normalize an optional template role for persisted/runtime metadata."""
    return str(role or "").strip().lower() or "default_seed"


def normalize_activation_scope(scope: object) -> str:
    """Normalize an optional activation scope and fall back to broad."""
    value = str(scope or "").strip().lower()
    return value if value in {"broad", "refine", "diagnostic"} else "broad"


def _template_key(template_name: str, expression: str) -> tuple[str, str]:
    """生成模板元数据映射键。"""
    return (template_name, expression)


def _runtime_template_metadata(item: TemplateLibraryItem) -> dict[str, object]:
    """提取运行时需要的模板元数据。"""
    metadata = dict(item.metadata)
    if item.family:
        metadata["family"] = item.family
    if item.stage:
        metadata["stage"] = item.stage
    return metadata


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
) -> list[TemplateLibraryItem]:
    """合并基础模板、字段类型模板和数据集专属模板，后者可覆盖前者。"""
    merged: dict[str, TemplateLibraryItem] = {}
    for key in _dataset_template_keys(field_type, dataset_id):
        for item in template_library.get(key, []):
            if isinstance(item, TemplateLibraryItem):
                merged[item.name] = item
    return list(merged.values())
