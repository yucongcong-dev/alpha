"""Template library path resolution helpers."""

from __future__ import annotations

import os
from pathlib import Path

_BUILTIN_TEMPLATE_LIBRARY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "templates",
    "base",
    "library.json",
)
_LEGACY_BUILTIN_TEMPLATE_LIBRARY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "worldquant_template_library.json",
)


def resolve_builtin_template_library_file() -> str:
    """Prefer the new base template path, with a legacy fallback."""
    if os.path.exists(_BUILTIN_TEMPLATE_LIBRARY_FILE):
        return _BUILTIN_TEMPLATE_LIBRARY_FILE
    if os.path.exists(_LEGACY_BUILTIN_TEMPLATE_LIBRARY_FILE):
        return _LEGACY_BUILTIN_TEMPLATE_LIBRARY_FILE
    return _BUILTIN_TEMPLATE_LIBRARY_FILE


def is_builtin_template_path(path: str) -> bool:
    """Return whether the path points to a versioned built-in template library."""
    try:
        resolved = Path(path).resolve()
        return resolved in {
            Path(_BUILTIN_TEMPLATE_LIBRARY_FILE).resolve(),
            Path(_LEGACY_BUILTIN_TEMPLATE_LIBRARY_FILE).resolve(),
        }
    except OSError:
        normalized = os.path.abspath(path)
        return normalized in {
            os.path.abspath(_BUILTIN_TEMPLATE_LIBRARY_FILE),
            os.path.abspath(_LEGACY_BUILTIN_TEMPLATE_LIBRARY_FILE),
        }


__all__ = [
    "is_builtin_template_path",
    "resolve_builtin_template_library_file",
]
