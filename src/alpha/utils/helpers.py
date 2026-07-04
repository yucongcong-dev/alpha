"""
公共工具模块

本模块提供通用的纯工具函数，不依赖任何业务模块，用于解决模块间的循环依赖问题。

模块内容：
    - first_non_empty(): 从多个候选值中返回第一个非空值
    - is_event_field_name(): 判断字段名是否属于事件类字段
"""

from __future__ import annotations

from typing import Any


def first_non_empty(*values: Any) -> Any | None:
    """
    从多个候选值中返回第一个非空值。

    API 在不同端点的返回结构不一致，许多解析器需要
    一个"选择第一个有用值"的辅助函数。

    Args:
        *values: 可变数量的候选值。

    Returns:
        Optional[Any]: 第一个非空值，如果所有值都为空则返回 None。

    Example:
        >>> first_non_empty(None, "", "value")
        'value'
        >>> first_non_empty(None, [], {})
        None
        >>> first_non_empty({"key": "value"}, None)
        {'key': 'value'}
    """
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def is_event_field_name(field_name: str, prefixes: tuple[str, ...] = ()) -> bool:
    """按配置前缀判断字段是否属于事件类字段。"""
    normalized = str(field_name).strip().lower()
    if not normalized:
        return False
    return any(normalized.startswith(str(prefix).strip().lower()) for prefix in prefixes if str(prefix).strip())
