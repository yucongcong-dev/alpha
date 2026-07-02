"""Template library file creation and normalization helpers."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from ...exceptions import BrainAPIError
from ...io.common import atomic_write_json
from .library_paths import is_builtin_template_path, resolve_builtin_template_library_file

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
    """Ensure a dataset-specific template library exists."""
    target_path = path or resolve_builtin_template_library_file()
    if Path(target_path).exists():
        if is_builtin_template_path(target_path):
            return target_path
        try:
            with open(target_path, encoding="utf-8") as handle:
                existing_payload = json.load(handle)
            if isinstance(existing_payload, dict) and add_missing_template_priorities(
                existing_payload
            ):
                atomic_write_json(target_path, existing_payload)
                logger.info("[templates] filled missing template priorities: %s", target_path)
        except Exception as exc:
            raise BrainAPIError(f"读取模板库文件失败 {target_path}: {exc}") from exc
        return target_path

    base_path = resolve_builtin_template_library_file()
    if not Path(base_path).exists():
        raise BrainAPIError(f"基础模板库文件不存在，无法生成专属模板库: {base_path}")

    try:
        with open(base_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        raise BrainAPIError(f"读取基础模板库文件失败 {base_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise BrainAPIError(f"基础模板库文件 {base_path} 必须包含一个 JSON 对象。")

    generated = dict(payload)
    generated.setdefault("_generated_from", os.path.relpath(base_path, Path(target_path).parent))
    generated["_dataset_id"] = dataset_id
    generated["_comment_dataset_template"] = (
        "Auto-generated dataset-specific template library. "
        "Edit this file for dataset-level template tuning; base templates remain unchanged."
    )
    add_missing_template_priorities(generated)

    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target_path, generated)
    logger.info(
        "[templates] generated dataset template library from base: %s -> %s",
        base_path,
        target_path,
    )
    return target_path


__all__ = [
    "DEFAULT_TEMPLATE_PRIORITY_START",
    "add_missing_template_priorities",
    "default_priority_for_index",
    "ensure_dataset_template_library",
]
