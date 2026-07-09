"""配置常量 — 向后兼容的惰性导出枢纽。

所有常量按职责拆分到 `_constants_*` 子模块。本模块保留历史
`alpha.config.constants` / `alpha.config` 导入面，但避免在模块加载时
把所有常量子模块一次性导入。
"""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._constants_api import *
    from ._constants_paths import *
    from ._constants_strings import *
    from ._constants_templates import *
    from ._constants_thresholds import *

_CONSTANT_MODULES: tuple[str, ...] = (
    "._constants_api",
    "._constants_thresholds",
    "._constants_strings",
    "._constants_templates",
    "._constants_paths",
)


def _module_source_path(module_name: str) -> Path:
    return Path(__file__).with_name(f"{module_name.rsplit('.', 1)[-1]}.py")


def _discover_module_exports(module_name: str) -> tuple[str, ...]:
    """Discover top-level constant names without importing the target module eagerly."""
    tree = ast.parse(_module_source_path(module_name).read_text(encoding="utf-8"))
    exported: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id.isupper() and not target.id.startswith("_"):
                exported.append(target.id)
    return tuple(dict.fromkeys(exported))


_EXPORT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
    (module_name, _discover_module_exports(module_name)) for module_name in _CONSTANT_MODULES
)

__all__ = [name for _module_name, names in _EXPORT_GROUPS for name in names]

_EXPORT_MAP: dict[str, str] = {
    name: module_name
    for module_name, names in _EXPORT_GROUPS
    for name in names
}


def __getattr__(name: str) -> object:
    try:
        module_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name, __package__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
