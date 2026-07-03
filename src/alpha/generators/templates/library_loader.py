"""Template library loading and validation."""

from __future__ import annotations

import json
import os

from ...config import get_backfill_window, get_dataset_expression_policy
from ...exceptions import BrainAPIError
from ...models.domain import TemplateLibrary, TemplateLibraryItem
from .library_paths import is_builtin_template_path, resolve_builtin_template_library_file

_OPTIONAL_TEMPLATE_METADATA_KEYS = (
    "family",
    "layer",
    "stage",
    "requires_partner_field",
    "field_kinds",
    "dataset_tags",
)


def infer_template_stage(item: dict[str, object]) -> str:
    """Infer stage for templates without an explicit stage field."""
    explicit_stage = str(item.get("stage", "")).strip().lower()
    if explicit_stage:
        return explicit_stage
    layer = str(item.get("layer", "")).strip().lower()
    name = str(item.get("name", "")).strip().lower()
    dataset_tags = item.get("dataset_tags")
    if isinstance(dataset_tags, list):
        lowered_tags = {str(tag).strip().lower() for tag in dataset_tags}
    else:
        lowered_tags = set()
    if "event" in layer or "event" in name or any("event" in tag for tag in lowered_tags):
        return "event_conditioned"
    if layer in {"group", "composite", "set", "account"}:
        return "group_second_order"
    return "first_order"


def resolve_placeholders(expression: str, backfill_window: int) -> str:
    """Replace template placeholders with runtime values."""
    return expression.replace("{backfill_window}", str(backfill_window))


def resolve_template_backfill_window(payload: dict[str, object], field_type: str) -> int:
    """Resolve backfill_window for a template group using dataset policy when present."""
    dataset_id = str(payload.get("_dataset_id", "")).strip()
    fallback = get_backfill_window()
    if not dataset_id:
        return fallback

    policy = get_dataset_expression_policy(dataset_id)
    normalized = field_type.strip().upper()
    if normalized == "VECTOR":
        configured = policy.vector_field_transform.backfill_window
    elif normalized == "MATRIX":
        configured = policy.matrix_field_transform.backfill_window
    else:
        configured = policy.default_field_transform.backfill_window
    return configured or fallback


def load_template_library(path: str) -> TemplateLibrary:
    """Load and validate a JSON template library."""
    if not path or (not os.path.exists(path) and is_builtin_template_path(path)):
        path = resolve_builtin_template_library_file()

    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        raise BrainAPIError(f"读取模板库文件失败 {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise BrainAPIError(f"模板库文件 {path} 必须包含一个 JSON 对象。")

    validated: TemplateLibrary = {}
    for field_type, templates in payload.items():
        if field_type.startswith("_"):
            continue
        if not isinstance(field_type, str):
            raise BrainAPIError("模板库的键必须是字符串。")
        if not isinstance(templates, list):
            raise BrainAPIError(f"模板库条目 '{field_type}' 必须是一个列表。")
        backfill_window = resolve_template_backfill_window(payload, field_type)
        validated[field_type] = []
        for index, item in enumerate(templates):
            if not isinstance(item, dict):
                raise BrainAPIError(f"模板 '{field_type}[{index}]' 必须是一个对象。")
            if "name" not in item or "expression" not in item:
                raise BrainAPIError(
                    f"模板 '{field_type}[{index}]' 必须包含 name 和 expression 字段。"
                )
            if not isinstance(item["name"], str) or not item["name"].strip():
                raise BrainAPIError(f"模板 '{field_type}[{index}]' 的 name 必须是非空字符串。")
            if not isinstance(item["expression"], str) or not item["expression"].strip():
                raise BrainAPIError(
                    f"模板 '{field_type}[{index}]' 的 expression 必须是非空字符串。"
                )
            priority = item.get("priority", 0)
            if not isinstance(priority, int):
                raise BrainAPIError(f"模板 '{field_type}[{index}]' 的 priority 必须是整数。")
            resolved_expression = resolve_placeholders(item["expression"].strip(), backfill_window)
            metadata = {
                key: item[key]
                for key in _OPTIONAL_TEMPLATE_METADATA_KEYS
                if key in item
            }
            validated[field_type].append(
                TemplateLibraryItem(
                    name=item["name"].strip(),
                    expression=resolved_expression,
                    priority=priority,
                    family=item.get("family"),
                    stage=infer_template_stage(item),
                    metadata=metadata,
                )
            )
    return validated


__all__ = [
    "infer_template_stage",
    "load_template_library",
    "resolve_placeholders",
    "resolve_template_backfill_window",
]
