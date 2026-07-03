"""YAML configuration source discovery, loading, merging, and signatures."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

from .types import YamlConfig


def find_project_root() -> Path:
    """Find the project root by walking up to pyproject.toml or config/settings.yaml."""
    current = Path(__file__).resolve().parent
    for _ in range(8):
        if (current / "pyproject.toml").is_file() or (current / "config" / "settings.yaml").is_file():
            return current
        if current.parent == current:
            break
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent.parent


PROJECT_ROOT = find_project_root()

DEFAULT_CONFIG_NAMES: set[str] = {
    "constants_defaults",
    "quality_feedback_defaults",
    "template_defaults",
}
"""Logical names for code-level default YAML files."""

YAML_FILES: list[tuple[str, list[str]]] = [
    ("constants_defaults", ["config/constants_defaults.yaml"]),
    ("quality_feedback_defaults", ["config/quality_feedback.yaml"]),
    ("template_defaults", ["config/templates.yaml"]),
    ("dataset_profiles", ["config/dataset_profiles.yaml"]),
    ("expression_policies", ["config/expression_policies.yaml"]),
    ("settings", ["config/settings.yaml"]),
]
"""YAML files in ascending priority order."""

ENV_CONFIG_PATH: str = "ALPHA_CONFIG_FILE"


def resolve_all_yaml_files(settings_path: str | None = None) -> dict[str, str]:
    """Resolve all existing YAML files as {logical_name: absolute_path}."""
    project_dir = str(PROJECT_ROOT)
    resolved: dict[str, str] = {}

    for name, search_paths in YAML_FILES:
        if name == "settings" and settings_path:
            candidate = os.path.abspath(settings_path)
            if os.path.isfile(candidate):
                resolved[name] = candidate
                continue

        for rel in search_paths:
            full = os.path.join(project_dir, rel) if not os.path.isabs(rel) else rel
            if os.path.isfile(full):
                resolved[name] = full
                break

    return resolved


def resolve_yaml_path() -> str | None:
    """Resolve the main config/settings.yaml path."""
    env_path = os.environ.get(ENV_CONFIG_PATH)
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)

    resolved = resolve_all_yaml_files()
    settings_path = resolved.get("settings")
    if settings_path:
        return settings_path

    candidate = PROJECT_ROOT / "config" / "settings.yaml"
    if candidate.is_file():
        return str(candidate)
    return None


def load_yaml_file(path: str) -> YamlConfig:
    """Load one YAML file. Missing or invalid files return an empty dict."""
    try:
        import yaml
    except ImportError:
        return {}

    if not os.path.isfile(path):
        return {}

    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            return data
    except (yaml.YAMLError, UnicodeDecodeError, OSError):
        pass

    return {}


def deep_merge(base: YamlConfig, override: YamlConfig, max_depth: int = 6) -> YamlConfig:
    """Deep-merge dictionaries with override winning."""
    if max_depth <= 0:
        return cast(YamlConfig, dict(override))
    result: YamlConfig = cast(YamlConfig, dict(base))
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(cast(YamlConfig, result[key]), cast(YamlConfig, value), max_depth - 1)
        else:
            result[key] = value
    return result


def load_all_yamls(settings_path: str | None = None) -> YamlConfig:
    """Load and merge all YAML files in ascending priority order."""
    merged: YamlConfig = {}
    resolved_files = resolve_all_yaml_files(settings_path)

    for name, _search_paths in YAML_FILES:
        path = resolved_files.get(name)
        if path:
            data = load_yaml_file(path)
            if data:
                merged = deep_merge(merged, data)

    return merged


def load_default_yamls(resolved_files: dict[str, str]) -> YamlConfig:
    """Load all code-level default YAML files for schema validation."""
    merged: YamlConfig = {}
    for name, _search_paths in YAML_FILES:
        if name not in DEFAULT_CONFIG_NAMES:
            continue
        path = resolved_files.get(name)
        if not path:
            continue
        data = load_yaml_file(path)
        if data:
            merged = deep_merge(merged, data)
    return merged


def config_file_signature(path: str | None) -> tuple[int, int] | None:
    """Return a file signature as (mtime_ns, size)."""
    if not path or not os.path.isfile(path):
        return None
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def all_files_signature(settings_path: str | None = None) -> tuple[tuple[str, int, int], ...] | None:
    """Return an aggregate signature for all resolved YAML files."""
    sigs: list[tuple[str, int, int]] = []
    resolved_files = resolve_all_yaml_files(settings_path)

    for path in resolved_files.values():
        sig = config_file_signature(path)
        if sig:
            sigs.append((path, sig[0], sig[1]))

    return tuple(sigs) if sigs else None
