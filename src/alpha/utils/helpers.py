"""
公共工具模块

本模块提供通用的工具函数，用于解决模块间的循环依赖问题。
所有不依赖其他业务模块的纯函数都应放在这里。

模块内容：
    - first_non_empty(): 从多个候选值中返回第一个非空值
    - choose_field_name(): 从异构字段元数据中解析标准字段名
    - choose_field_type(): 将字段类型标准化为统一的大写标签
"""

from typing import Any

from ..config import SENTINEL_UNKNOWN


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


def choose_field_name(field: dict[str, Any]) -> str:
    """
    从异构字段元数据中解析标准字段名或标识。

    字段在不同来源端点可能使用不同的键名，此函数尝试从
    多个常见键中提取标准的字段标识符。

    Args:
        field (Dict[str, Any]): 字段的元数据字典。

    Returns:
        str: 字段的标准名称或标识符。

    支持的键名（优先级从高到低）：
        - "id"
        - "name"
        - "mnemonic"
        - "field"

    Example:
        >>> field = {"id": "sales", "name": "Sales Revenue"}
        >>> name = choose_field_name(field)
        >>> print(name)
        'sales'

        >>> field = {"mnemonic": "ebitda"}
        >>> name = choose_field_name(field)
        >>> print(name)
        'ebitda'
    """
    return str(
        first_non_empty(
            field.get("id"),
            field.get("name"),
            field.get("mnemonic"),
            field.get("field"),
        )
    )


def choose_field_type(field: dict[str, Any]) -> str:
    """
    将字段类型标准化为统一的大写标签，便于模板分发。

    字段类型在不同来源可能使用不同的键名和格式，此函数
    将其标准化为大写的统一标签，用于模板库路由。

    Args:
        field (Dict[str, Any]): 字段的元数据字典。

    Returns:
        str: 标准化的大写字段类型标签。

    支持的键名（优先级从高到低）：
        - "type"
        - "fieldType"
        - "category"

    如果所有键都为空，返回 "UNKNOWN"。

    Example:
        >>> field = {"type": "MATRIX"}
        >>> type_label = choose_field_type(field)
        >>> print(type_label)
        'MATRIX'

        >>> field = {"fieldType": "vector"}
        >>> type_label = choose_field_type(field)
        >>> print(type_label)
        'VECTOR'

        >>> field = {}
        >>> type_label = choose_field_type(field)
        >>> print(type_label)
        'UNKNOWN'
    """
    return str(
        first_non_empty(
            field.get("type"),
            field.get("fieldType"),
            field.get("category"),
            SENTINEL_UNKNOWN,
        )
    ).upper()
