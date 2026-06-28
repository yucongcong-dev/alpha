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
import os

from ..config import get_backfill_window
from ..exceptions import BrainAPIError
from ..models.base import TemplateLibrary

# 内置默认模板库 JSON 文件的路径回退
_BUILTIN_TEMPLATE_LIBRARY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "worldquant_template_library.json",
)


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
    # 回退：路径为空或文件不存在时，使用内置默认模板库
    if not path or not os.path.exists(path):
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
