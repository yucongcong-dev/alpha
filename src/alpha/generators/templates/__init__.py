"""Template library compatibility exports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..._facade import ExportMap, facade_dir, resolve_export

if TYPE_CHECKING:
    from .library_loader import load_template_library
    from .library_store import ensure_dataset_template_library

_EXPORT_MAP: ExportMap = {
    "ensure_dataset_template_library": (".library_store", "ensure_dataset_template_library"),
    "load_template_library": (".library_loader", "load_template_library"),
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
