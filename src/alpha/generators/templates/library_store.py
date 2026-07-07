"""Template library file creation and normalization helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ...exceptions import BrainAPIError
from ...io.common import atomic_write_json

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PRIORITY_START = 1000
"""模板文件缺省优先级起点；文件越靠前，自动补齐的 priority 越高。"""


def default_priority_for_index(index: int) -> int:
    """Generate a stable default priority from file order."""
    return max(1, DEFAULT_TEMPLATE_PRIORITY_START - index)


def add_missing_template_priorities(payload: dict[str, object]) -> bool:
    """Fill missing template priorities without overriding explicit values."""
    changed = False
    for field_type, templates in payload.items():
        if field_type.startswith("_") or not isinstance(templates, list):
            continue
        template_index = 0
        for item in templates:
            if not isinstance(item, dict):
                continue
            if "name" not in item or "expression" not in item:
                continue
            if "priority" not in item:
                item["priority"] = default_priority_for_index(template_index)
                changed = True
            template_index += 1
    return changed


def ensure_dataset_template_library(path: str, dataset_id: str) -> str:
    """Ensure a dataset-specific template library exists.

    Each dataset must have its own independent template library file.
    No base template inheritance — templates are designed per-dataset.
    """
    if not path:
        raise BrainAPIError(
            f"数据集 {dataset_id} 缺少模板库文件路径。"
            "请通过 --template-library-file 指定，或在 templates/{dataset_id}/library.json 创建专属模板库。"
        )

    if not Path(path).exists():
        raise BrainAPIError(
            f"模板库文件不存在: {path}。"
            f"请为数据集 {dataset_id} 创建专属模板库文件，不再支持从基础模板自动生成。"
        )

    try:
        with open(path, encoding="utf-8") as handle:
            existing_payload = json.load(handle)
        if isinstance(existing_payload, dict) and add_missing_template_priorities(
            existing_payload
        ):
            atomic_write_json(path, existing_payload)
            logger.info("[templates] filled missing template priorities: %s", path)
    except Exception as exc:
        raise BrainAPIError(f"读取模板库文件失败 {path}: {exc}") from exc
    return path


__all__ = [
    "DEFAULT_TEMPLATE_PRIORITY_START",
    "add_missing_template_priorities",
    "default_priority_for_index",
    "ensure_dataset_template_library",
]
