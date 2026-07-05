"""Template library compatibility exports."""

from __future__ import annotations

from . import library_loader as _library_loader
from . import library_store as _library_store


def ensure_dataset_template_library(path: str, dataset_id: str) -> str:
    """Compatibility wrapper around the split template-library store."""
    return _library_store.ensure_dataset_template_library(path, dataset_id)


def load_template_library(path: str):
    """Compatibility wrapper around the split template-library loader."""
    return _library_loader.load_template_library(path)


__all__ = [
    "ensure_dataset_template_library",
    "load_template_library",
]
