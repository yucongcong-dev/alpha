"""Process-local blacklist directory context."""

from __future__ import annotations

from pathlib import Path

from ..io.common import resolve_blacklists_dir

_ACTIVE_BLACKLISTS_DIR: Path | None = None


def set_active_blacklists_dir(path: str = "") -> str:
    """Freeze the blacklist root used by the current process."""
    global _ACTIVE_BLACKLISTS_DIR
    resolved = Path(path).expanduser().resolve() if path else resolve_blacklists_dir()
    _ACTIVE_BLACKLISTS_DIR = resolved
    return str(resolved)


def get_active_blacklists_dir() -> Path:
    """Return the currently active blacklist root."""
    if _ACTIVE_BLACKLISTS_DIR is not None:
        return _ACTIVE_BLACKLISTS_DIR
    return resolve_blacklists_dir()


def clear_active_blacklists_dir() -> None:
    """Clear the process-local blacklist root override."""
    global _ACTIVE_BLACKLISTS_DIR
    _ACTIVE_BLACKLISTS_DIR = None
