"""
模板库管理模块

本模块负责从 JSON 配置文件加载 Alpha 表达式模板库。
模板数据已外部化为 JSON 文件（data/worldquant_template_library.json），
方便修改和扩展而无需修改 Python 代码。

模块内容：
    - load_template_library(path) -> TemplateLibrary: 从 JSON 文件加载模板库
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from ..config import get_backfill_window
from ..exceptions import BrainAPIError
from ..io.output import atomic_write_json
from ..models.base import TemplateLibrary

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PRIORITY_START = 200
"""模板文件缺省优先级起点；文件越靠前，自动补齐的 priority 越高。"""

# 内置默认模板库 JSON 文件的路径回退
_BUILTIN_TEMPLATE_LIBRARY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "worldquant_template_library.json",
)


def _default_priority_for_index(index: int) -> int:
    """按模板在同一分组内的顺序生成默认优先级，越靠前越高。"""
    return max(1, DEFAULT_TEMPLATE_PRIORITY_START - index)


def _add_missing_template_priorities(payload: dict[str, object]) -> bool:
    """
    为模板库中缺失 priority 的模板补默认优先级。

    只补缺失值，不覆盖已有手工 priority。每个字段类型分组内按文件顺序
    从高到低递减，使专属模板文件可以稳定地“先跑优先级高的模板”。
    """
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
                item["priority"] = _default_priority_for_index(template_index)
                changed = True
            template_index += 1
    return changed


def ensure_dataset_template_library(path: str, dataset_id: str) -> str:
    """
    确保 dataset 专属模板库文件存在，不存在时从基础模板库生成。

    基础模板库固定为 data/worldquant_template_library.json；专属模板库默认
    由 CLI 路径规范化为 data/worldquant_template_library_<dataset_id>.json。
    如果专属文件已存在，保持原文件不覆盖，避免丢失人工优化。

    Args:
        path: dataset 专属模板库目标路径。
        dataset_id: 数据集 ID，用于写入生成元数据。

    Returns:
        str: 最终可加载的模板库路径。path 为空时返回基础模板库路径。
    """
    target_path = path or _BUILTIN_TEMPLATE_LIBRARY_FILE
    if os.path.exists(target_path):
        try:
            with open(target_path, encoding="utf-8") as handle:
                existing_payload = json.load(handle)
            if isinstance(existing_payload, dict) and _add_missing_template_priorities(
                existing_payload
            ):
                atomic_write_json(target_path, existing_payload)
                logger.info("[templates] filled missing template priorities: %s", target_path)
        except Exception as exc:
            raise BrainAPIError(f"读取模板库文件失败 {target_path}: {exc}") from exc
        return target_path

    base_path = _BUILTIN_TEMPLATE_LIBRARY_FILE
    if not os.path.exists(base_path):
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
    _add_missing_template_priorities(generated)

    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target_path, generated)
    logger.info(
        "[templates] generated dataset template library from base: %s -> %s",
        base_path,
        target_path,
    )
    return target_path


def _resolve_placeholders(expression: str, backfill_window: int) -> str:
    """将模板表达式中的 {backfill_window} 占位符替换为实际值。"""
    return expression.replace("{backfill_window}", str(backfill_window))


def load_template_library(path: str) -> TemplateLibrary:
    """
    从 JSON 文件加载并校验模板库。

    模板数据已外部化为 JSON 配置文件，无需修改 Python 代码即可
    增删模板或调整优先级。表达式中的 {backfill_window} 占位符
    会在加载时自动替为 settings.yaml 中的实际值。

    Args:
        path (str): 模板库 JSON 文件的路径。如果为空字符串或文件不存在，
            将回退到内置默认模板库 data/worldquant_template_library.json。

    Returns:
        TemplateLibrary: 加载并校验后的模板库字典。

    Raises:
        BrainAPIError: 当 JSON 文件格式错误或不符合模板库结构要求时抛出。

    JSON 文件格式要求：
        - 文件必须包含一个 JSON 对象（字典）
        - 键必须是字符串，表示字段类型（如 "default", "VECTOR" 等）
        - 值必须是列表，包含该类型的模板对象
        - 每个模板对象必须包含：
            - name: 非空字符串，模板名称
            - expression: 非空字符串，模板表达式
            - priority: 可选整数，模板优先级（默认为 0）
        - 表达式支持以下占位符：
            - {field}: 运行时替换为字段名
            - {backfill_window}: 加载时替换为 settings.yaml 中的 backfill_window 值

    Example:
        >>> # 加载外部模板库文件
        >>> library = load_template_library("templates.json")
        >>> print(library.keys())
        dict_keys(['default', 'MATRIX'])

        >>> # 文件不存在时回退到内置默认模板库
        >>> library = load_template_library("")
        >>> print(len(library))
        8

        >>> # JSON 文件示例
        >>> # {
        >>> #     "default": [
        >>> #         {"name": "simple_rank", "expression": "rank({field})", "priority": 100}
        >>> #     ]
        >>> # }

    Note:
        模板表达式中的 {field} 占位符将在运行时替换为实际的字段名称。
        {backfill_window} 占位符在加载时替换为 backfill_window 配置值。
        优先级越高的模板在候选排序时越靠前。
    """
    # 回退：路径为空时使用内置基础模板库；指定路径不存在时由调用方先生成。
    if not path:
        path = _BUILTIN_TEMPLATE_LIBRARY_FILE

    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        raise BrainAPIError(f"读取模板库文件失败 {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise BrainAPIError(f"模板库文件 {path} 必须包含一个 JSON 对象。")

    # 获取 backfill_window 配置值，用于下文的占位符替换
    backfill_window = get_backfill_window()

    validated: TemplateLibrary = {}
    for field_type, templates in payload.items():
        # 跳过元数据键（如 _comment / _dataset_id / _generated_from）
        if field_type.startswith("_"):
            continue
        if not isinstance(field_type, str):
            raise BrainAPIError("模板库的键必须是字符串。")
        if not isinstance(templates, list):
            raise BrainAPIError(f"模板库条目 '{field_type}' 必须是一个列表。")
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
            resolved_expression = _resolve_placeholders(
                item["expression"].strip(), backfill_window
            )
            validated[field_type].append(
                {
                    "name": item["name"].strip(),
                    "expression": resolved_expression,
                    "priority": priority,
                }
            )
    return validated
