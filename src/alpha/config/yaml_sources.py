"""YAML configuration source discovery, loading, merging, and signatures."""

from __future__ import annotations

import os
from typing import cast

from ..workspace import DEFAULT_WORKSPACE
from .types import YamlConfig

PROJECT_ROOT = DEFAULT_WORKSPACE.config_dir.parent

DEFAULT_CONFIG_FILE_NAMES: tuple[str, ...] = (
    "constants_defaults",
    "quality_feedback_defaults",
    "template_defaults",
)
"""Logical names for code-level default YAML files, in canonical order."""

DEFAULT_CONFIG_NAMES: frozenset[str] = frozenset(DEFAULT_CONFIG_FILE_NAMES)
"""Set form used by schema validation when selecting default sources."""

YAML_FILES: list[tuple[str, list[str]]] = [
    ("constants_defaults", ["config/constants_defaults.yaml"]),
    ("quality_feedback_defaults", ["config/quality_feedback.yaml"]),
    ("template_defaults", ["config/templates.yaml"]),
    ("strategy_profiles", ["config/strategy_profiles.yaml"]),
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
    """Load one YAML file.

    A missing file yields an empty mapping.  A present file that cannot be
    parsed or is not a top-level mapping raises ``ValueError`` so configuration
    errors fail loudly instead of silently dropping defaults.
    """
    try:
        import yaml
    except ImportError:
        return {}

    if not os.path.isfile(path):
        return {}

    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
        raise ValueError(f"无法读取 YAML 配置 {path}: {exc}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML 配置 {path} 顶层必须是 mapping，而不是 {type(data).__name__}")
    return data


def default_yaml_section_owners(
    resolved_files: dict[str, str],
) -> dict[str, tuple[str, ...]]:
    """Return the canonical owner(s) for each top-level default section.

    The three code-level default files are deliberately split by
    responsibility.  A top-level section appearing in more than one of them
    would make ``deep_merge`` silently choose whichever file happens to be
    loaded later, so ownership is kept explicit and auditable.
    """
    owners: dict[str, list[str]] = {}
    for name in DEFAULT_CONFIG_FILE_NAMES:
        path = resolved_files.get(name)
        if not path:
            continue
        data = load_yaml_file(path)
        for section in data:
            owners.setdefault(str(section), []).append(name)
    return {section: tuple(names) for section, names in owners.items()}


def validate_default_yaml_ownership(resolved_files: dict[str, str]) -> list[str]:
    """Report default sections that have more than one canonical source."""
    conflicts = [
        (section, names)
        for section, names in default_yaml_section_owners(resolved_files).items()
        if len(names) > 1
    ]
    return [
        f"默认 YAML section '{section}' 同时定义在 {', '.join(names)}；"
        "请保留一个 canonical owner，避免按文件顺序静默覆盖。"
        for section, names in sorted(conflicts)
    ]


def validate_explicit_yaml_file(path: str) -> str:
    """Require an explicitly selected settings file to be a valid YAML mapping."""
    import yaml

    raw_path = str(path or "").strip()
    if not raw_path:
        raise ValueError("--config requires a non-empty file path")
    resolved_path = os.path.abspath(os.path.expanduser(raw_path))
    if not os.path.isfile(resolved_path):
        raise ValueError(f"--config does not exist or is not a file: {resolved_path}")
    try:
        with open(resolved_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ValueError(f"--config contains invalid YAML: {resolved_path}: {exc}") from exc
    except (UnicodeDecodeError, OSError) as exc:
        raise ValueError(f"--config cannot be read as UTF-8: {resolved_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"--config must contain a YAML mapping at the top level: {resolved_path}")
    return resolved_path


def deep_merge(base: YamlConfig, override: YamlConfig, max_depth: int = 6) -> YamlConfig:
    """Deep-merge dictionaries with override winning."""
    if max_depth <= 0:
        raise ValueError("YAML 配置嵌套层级超过合并上限，请检查配置文件结构。")
    result: YamlConfig = cast(YamlConfig, dict(base))
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(
                cast(YamlConfig, result[key]), cast(YamlConfig, value), max_depth - 1
            )
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


def config_file_signature(path: str | None) -> tuple[int, int, int] | None:
    """Return a file signature as ``(mtime_ns, ctime_ns, size)``.

    ``ctime_ns`` is the inode change time on POSIX, so overwriting a file with
    the same size and then restoring its mtime still changes the signature,
    without requiring a full content read on every cache lookup.
    """
    if not path or not os.path.isfile(path):
        return None
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)


def all_files_signature(
    settings_path: str | None = None,
) -> tuple[tuple[str, int, int, int], ...] | None:
    """Return an aggregate signature for all resolved YAML files."""
    sigs: list[tuple[str, int, int, int]] = []
    resolved_files = resolve_all_yaml_files(settings_path)

    for path in resolved_files.values():
        sig = config_file_signature(path)
        if sig:
            sigs.append((path, sig[0], sig[1], sig[2]))

    return tuple(sigs) if sigs else None
