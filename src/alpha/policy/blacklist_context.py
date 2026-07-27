"""Process-local datasets-root context used by blacklist storage."""

from __future__ import annotations

from pathlib import Path

from ..io.common import resolve_datasets_root

_ACTIVE_DATASETS_ROOT: Path | None = None


def set_active_datasets_root(path: str = "") -> str:
    """Freeze the datasets root used by the current process."""
    global _ACTIVE_DATASETS_ROOT
    resolved = Path(path).expanduser().resolve() if path else resolve_datasets_root()
    _ACTIVE_DATASETS_ROOT = resolved
    return str(resolved)


def get_active_datasets_root() -> Path:
    """Return the currently active datasets root."""
    if _ACTIVE_DATASETS_ROOT is not None:
        return _ACTIVE_DATASETS_ROOT
    return resolve_datasets_root()


def clear_active_datasets_root() -> None:
    """Clear the process-local datasets-root override."""
    global _ACTIVE_DATASETS_ROOT
    _ACTIVE_DATASETS_ROOT = None
