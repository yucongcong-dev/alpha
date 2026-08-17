"""Thread-safe public YAML configuration API.

This module intentionally keeps only cache and compatibility concerns. Source
discovery/loading lives in ``yaml_sources``; schema validation lives in
``yaml_validator``.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import sys
import threading

from .types import YamlConfig
from .yaml_sources import (
    all_files_signature as _all_files_signature,
)
from .yaml_sources import (
    load_all_yamls as _load_all_yamls,
)
from .yaml_sources import (
    resolve_all_yaml_files as _resolve_all_yaml_files,
)
from .yaml_sources import (
    resolve_yaml_path as _resolve_yaml_path,
)
from .yaml_validator import clear_schema_cache, validate_merged_config

_log = logging.getLogger("alpha.config.yaml")

_ConfigSignature = tuple[tuple[str, int, int], ...] | None


@dataclass(frozen=True, slots=True)
class _ValidatedConfigEntry:
    """One validated merged configuration snapshot for a source signature."""

    path: str | None
    signature: _ConfigSignature
    data: YamlConfig


_config_lock = threading.RLock()
_config_cache: _ValidatedConfigEntry | None = None
_active_config_path: str | None = None


def set_active_config_path(config_path: str = "") -> str | None:
    """Bind the process-wide settings file used by no-argument config reads.

    CLI parsing resolves ``--config`` once at the application boundary.  All
    lower-level modules then call :func:`get_yaml_config` without needing to
    carry the path independently.
    """
    global _active_config_path, _config_cache
    resolved = os.path.abspath(os.path.expanduser(config_path)) if config_path else None
    with _config_lock:
        if resolved != _active_config_path:
            _active_config_path = resolved
            _config_cache = None
    return resolved


def get_active_config_path() -> str | None:
    """Return the explicitly bound settings path, if any."""
    with _config_lock:
        return _active_config_path


def get_yaml_config_version(
    config_path: str = "",
) -> tuple[str, tuple[tuple[str, int, int], ...] | None]:
    """Return a cache token that changes when any active YAML source changes."""
    explicit_path = os.path.abspath(os.path.expanduser(config_path)) if config_path else None
    settings_path = explicit_path or get_active_config_path() or _resolve_yaml_path()
    return settings_path or "__missing__", _all_files_signature(settings_path)


def activate_config_from_argv(argv: list[str] | None = None) -> str | None:
    """Bind ``--config`` before importing modules with YAML-backed constants.

    This intentionally performs only minimal option discovery; argparse remains
    the authoritative CLI validator later in startup.
    """
    tokens = list(sys.argv[1:] if argv is None else argv)
    for index, token in enumerate(tokens):
        if token == "--config" and index + 1 < len(tokens):
            return set_active_config_path(tokens[index + 1])
        if token.startswith("--config="):
            return set_active_config_path(token.split("=", 1)[1])
    return get_active_config_path()


def clear_yaml_caches() -> None:
    """Clear all YAML config caches and force reload on next access."""
    global _config_cache
    with _config_lock:
        _config_cache = None
    clear_schema_cache()


def validate_yaml_config(config_path: str = "") -> list[str]:
    """Validate YAML configuration and return warning messages."""
    merged = get_yaml_config(config_path)
    resolved_files = _resolve_all_yaml_files(config_path or None)
    return validate_merged_config(merged, resolved_files)


def get_yaml_config(config_path: str = "") -> YamlConfig:
    """Return one validated snapshot, reloading when its sources change.

    The cache retains only the most recently requested path.  A CLI process has
    one active configuration, while explicit one-off reads remain correct
    without retaining an unbounded collection of path-specific snapshots.
    """
    global _config_cache

    explicit_path = os.path.abspath(os.path.expanduser(config_path)) if config_path else None
    settings_path = explicit_path or get_active_config_path() or _resolve_yaml_path()
    signature = _all_files_signature(settings_path)

    with _config_lock:
        cached_entry = _config_cache
        if cached_entry is not None and (
            cached_entry.path == settings_path and cached_entry.signature == signature
        ):
            return cached_entry.data

        data = _load_all_yamls(settings_path)
        resolved_files = _resolve_all_yaml_files(settings_path)
        validation_warnings = validate_merged_config(data, resolved_files)
        if validation_warnings:
            for warning in validation_warnings:
                _log.warning("[schema] %s", warning)
        _config_cache = _ValidatedConfigEntry(
            path=settings_path,
            signature=signature,
            data=data,
        )
        return data
