"""YAML 值解析辅助 — 从 constants.py 中抽取的纯工具函数。

本模块不定义任何业务常量，只提供 _yaml_val / _yaml_int / _yaml_float 等
类型安全的 YAML 值读取辅助。constants.py 的各分类子模块导入本模块即可。
"""

from __future__ import annotations

import logging
import threading
from typing import Any

_log = logging.getLogger("alpha.config.constants")

# 线程安全的缺失 key 警告记录，防止重复日志 + 无限增长
_MISSING_KEY_LOCK: threading.Lock = threading.Lock()
_MISSING_KEY_WARNED: set[str] = set()
_MISSING_KEY_WARNED_MAX: int = 200  # 超过此上限后停止记录（防止内存泄漏）


def _warn_once(key_path: str, template: str, *fmt_args: object) -> None:
    """线程安全：每个 key_path 仅警告一次，达到上限后静默。"""
    with _MISSING_KEY_LOCK:
        if len(_MISSING_KEY_WARNED) >= _MISSING_KEY_WARNED_MAX:
            return
        if key_path in _MISSING_KEY_WARNED:
            return
        _MISSING_KEY_WARNED.add(key_path)
    _log.warning(template, *fmt_args)


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


def _yaml_val(*keys: str, default: Any = None, cast: type = str) -> Any:
    """从完整合并 YAML 配置中读取嵌套值。

    查找顺序：
      1. global.<keys> — config/settings.yaml 中的用户覆盖（高优先级）
      2. <keys> — config/constants_defaults.yaml 中的基础默认值
      3. 代码内 default

    cast=None 表示不做类型转换，直接返回 YAML 原始值。
    """
    from .yaml import get_yaml_config

    yaml_data = get_yaml_config()
    key_path = ".".join(keys)

    # 1. 优先查找 global.* 路径
    node = _resolve_yaml_key(yaml_data, ("global", *keys))

    # 2. 回退到扁平路径
    if node is None:
        node = _resolve_yaml_key(yaml_data, keys)

    if node is None:
        _warn_once(key_path, "YAML 配置 key '%s' 未找到，使用代码默认值。"
                   "建议在 config/constants_defaults.yaml 中添加此项。", key_path)
        return default

    if cast is None:
        return node

    try:
        if cast is bool:
            return bool(node)
        return cast(node)
    except (TypeError, ValueError):
        _warn_once(key_path, "配置 key '%s' 值类型转换失败 (cast=%s, got=%r)，使用默认值。",
                   key_path, cast.__name__, type(node).__name__)
        return default


def _yaml_int(*keys: str, default: int = 0) -> int:
    return _yaml_val(*keys, default=default, cast=int)


def _yaml_float(*keys: str, default: float = 0.0) -> float:
    return _yaml_val(*keys, default=default, cast=float)


def _yaml_str(*keys: str, default: str = "") -> str:
    return _yaml_val(*keys, default=default, cast=str)


def _yaml_dict(*keys: str, default: dict | None = None) -> dict:
    result = _yaml_val(*keys, default=default, cast=None)
    return result if isinstance(result, dict) else (default or {})


def _yaml_list(*keys: str, default: list | None = None) -> list:
    result = _yaml_val(*keys, default=default, cast=None)
    return result if isinstance(result, (list, tuple)) else (default or [])


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
