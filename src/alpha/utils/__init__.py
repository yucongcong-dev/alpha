"""
工具函数包

提供不依赖业务逻辑的通用工具函数。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from .helpers import first_non_empty, is_event_field_name

_EXPORT_MAP: ExportMap = {
    "first_non_empty": (".helpers", "first_non_empty"),
    "is_event_field_name": (".helpers", "is_event_field_name"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str) -> object:
    return resolve_export(
        name=name,
        export_map=_EXPORT_MAP,
        package=__package__ or "",
        namespace=__name__,
        target_globals=globals(),
    )


def __dir__() -> list[str]:
    return facade_dir(globals(), _EXPORT_MAP)
