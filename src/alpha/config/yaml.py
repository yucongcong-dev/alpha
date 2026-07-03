"""Thread-safe public YAML configuration API.

This module intentionally keeps only cache and compatibility concerns. Source
discovery/loading lives in ``yaml_sources``; schema validation lives in
``yaml_validator``.
"""

from __future__ import annotations

import logging
import os
import threading

from .types import YamlConfig, YamlConfigCacheEntry
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

_config_lock = threading.RLock()
_config_cache: dict[str, YamlConfigCacheEntry] = {}
_config_validated: bool = False


def clear_yaml_caches() -> None:
    """Clear all YAML config caches and force reload on next access."""
    global _config_validated
    with _config_lock:
        _config_cache.clear()
        _config_validated = False
    clear_schema_cache()


def validate_yaml_config(config_path: str = "") -> list[str]:
    """Validate YAML configuration and return warning messages."""
    merged = get_yaml_config(config_path)
    resolved_files = _resolve_all_yaml_files(config_path or None)
    return validate_merged_config(merged, resolved_files)


def load_yaml_config(config_path: str = "") -> YamlConfig:
    """Load all YAML files and merge them into one config dict.

    Backward compatibility: the original API only loaded settings.yaml. The
    merged config now also includes dataset profiles, expression policies, and
    split default YAML files.
    """
    return _load_all_yamls(config_path or None)


def get_yaml_config(config_path: str = "") -> YamlConfig:
    """Return cached merged YAML config, reloading when any source file changes."""
    global _config_validated

    settings_path = os.path.abspath(config_path) if config_path else _resolve_yaml_path()
    cache_key = settings_path or "__missing__"
    signature = _all_files_signature(settings_path)

    with _config_lock:
        cached_entry = _config_cache.get(cache_key)
        if (
            isinstance(cached_entry, dict)
            and cached_entry.get("signature") == signature
            and isinstance(cached_entry.get("data"), dict)
        ):
            return cached_entry["data"]

        data = _load_all_yamls(settings_path)

        if not _config_validated:
            resolved_files = _resolve_all_yaml_files(settings_path)
            validation_warnings = validate_merged_config(data, resolved_files)
            if validation_warnings:
                for warning in validation_warnings:
                    _log.warning("[schema] %s", warning)
            _config_validated = True

        _config_cache[cache_key] = {
            "path": settings_path,
            "signature": signature,
            "data": data,
        }
        return data
