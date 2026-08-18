"""YAML 值解析辅助 — 从 constants.py 中抽取的纯工具函数。

本模块不定义任何业务常量，只提供 _yaml_val / _yaml_int / _yaml_float 等
类型安全的 YAML 值读取辅助。constants.py 的各分类子模块导入本模块即可。
"""

from __future__ import annotations

from typing import Any


def _resolve_yaml_key(yaml_data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """在 yaml_data 中沿 keys 路径导航，返回最终值或 None（表示未找到）。"""
    node: Any = yaml_data
    for key in keys:
        if isinstance(node, dict):
            node = node.get(key)
            if node is None:
                return None
        else:
            return None
    return node


def _yaml_val(*keys: str, default: Any = None, cast: type | None = str) -> Any:
    """从完整合并 YAML 配置中读取嵌套值。

    查找顺序：
      1. global.<keys> — config/settings.yaml 中的用户覆盖（高优先级）
      2. <keys> — 对应 canonical default YAML 文件中的基础默认值

    任一 canonical default YAML 若缺少该 key，会被视为配置漂移并直接报错，
    避免静默退回代码默认值。cast=None 表示不做类型转换，直接返回原始值。
    """
    from .yaml import get_yaml_config

    yaml_data: dict[str, Any] = dict(get_yaml_config())
    key_path = ".".join(keys)

    # 1. 优先查找 global.* 路径
    node = _resolve_yaml_key(yaml_data, ("global", *keys))

    # 2. 回退到扁平路径
    if node is None:
        node = _resolve_yaml_key(yaml_data, keys)

    if node is None:
        raise ValueError(
            f"YAML 配置 key '{key_path}' 在默认配置中缺失，请恢复 config 默认 YAML 中的对应项。"
        )

    if cast is None:
        return node

    try:
        if cast is bool:
            return bool(node)
        return cast(node)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"YAML 配置 key '{key_path}' 的值 {node!r} 无法转换为 {cast.__name__}"
        ) from exc


def _yaml_int(*keys: str, default: int = 0) -> int:
    return int(_yaml_val(*keys, default=default, cast=int))


def _yaml_float(*keys: str, default: float = 0.0) -> float:
    return float(_yaml_val(*keys, default=default, cast=float))


def _yaml_str(*keys: str, default: str = "") -> str:
    return str(_yaml_val(*keys, default=default, cast=str))


def _yaml_dict(*keys: str, default: dict | None = None) -> dict:
    result = _yaml_val(*keys, default=default, cast=None)
    return result if isinstance(result, dict) else (default or {})


def _yaml_set(*keys: str, default: set | None = None) -> set:
    result = _yaml_val(*keys, default=default, cast=None)
    if isinstance(result, (list, tuple)):
        return set(result)
    return default or set()


def _yaml_tuple_str_int(*keys: str) -> tuple[tuple[str, str, int], ...]:
    """从 YAML [[name, expr, priority], ...] 读取 tuple[tuple[str, str, int], ...]。"""
    result = _yaml_val(*keys, default=None, cast=None)
    if not isinstance(result, (list, tuple)):
        return ()
    rows: list[tuple[str, str, int]] = []
    for item in result:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            try:
                rows.append((str(item[0]), str(item[1]), int(item[2])))
            except (TypeError, ValueError):
                continue
    return tuple(rows)


def _yaml_tuple_int2(*keys: str) -> tuple[tuple[int, int], ...]:
    """从 YAML [[a, b], ...] 读取 tuple[tuple[int, int], ...]。"""
    result = _yaml_val(*keys, default=None, cast=None)
    if not isinstance(result, (list, tuple)):
        return ()
    rows: list[tuple[int, int]] = []
    for item in result:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                rows.append((int(item[0]), int(item[1])))
            except (TypeError, ValueError):
                continue
    return tuple(rows)


def _yaml_tuple_int3(*keys: str) -> tuple[tuple[int, int, int], ...]:
    """从 YAML [[a, b, c], ...] 读取 tuple[tuple[int, int, int], ...]。"""
    result = _yaml_val(*keys, default=None, cast=None)
    if not isinstance(result, (list, tuple)):
        return ()
    rows: list[tuple[int, int, int]] = []
    for item in result:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            try:
                rows.append((int(item[0]), int(item[1]), int(item[2])))
            except (TypeError, ValueError):
                continue
    return tuple(rows)


def _yaml_dict_tuple(*keys: str) -> dict[str, tuple[str, ...]]:
    """从 YAML {key: [v1, v2, ...]} 读取 dict[str, tuple[str, ...]]。"""
    result = _yaml_val(*keys, default=None, cast=None)
    if not isinstance(result, dict):
        return {}
    return {
        str(k): tuple(str(v) for v in val)
        for k, val in result.items()
        if isinstance(val, (list, tuple))
    }
