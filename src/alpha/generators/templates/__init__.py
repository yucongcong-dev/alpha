"""Template library compatibility exports."""

from __future__ import annotations

from . import library_loader as _library_loader
from . import library_paths as _library_paths
from . import library_store as _library_store

_BUILTIN_TEMPLATE_LIBRARY_FILE = _library_paths._BUILTIN_TEMPLATE_LIBRARY_FILE
_LEGACY_BUILTIN_TEMPLATE_LIBRARY_FILE = _library_paths._LEGACY_BUILTIN_TEMPLATE_LIBRARY_FILE


def ensure_dataset_template_library(path: str, dataset_id: str) -> str:
    """Compatibility wrapper around the split template-library store."""
    return _library_store.ensure_dataset_template_library(path, dataset_id)


def load_template_library(path: str):
    """Compatibility wrapper around the split template-library loader."""
    return _library_loader.load_template_library(path)


__all__ = [
    "_BUILTIN_TEMPLATE_LIBRARY_FILE",
    "_LEGACY_BUILTIN_TEMPLATE_LIBRARY_FILE",
    "ensure_dataset_template_library",
    "load_template_library",
]
