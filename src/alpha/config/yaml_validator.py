"""Schema and consistency validation for merged YAML configuration."""

from __future__ import annotations

import threading
from typing import Any

from .types import YamlConfig
from .yaml_sources import DEFAULT_CONFIG_NAMES, load_default_yamls, load_yaml_file

_schema_lock = threading.RLock()
_schema_keys_cache: dict[str, set[str]] | None = None

GLOBAL_KNOWN_KEYS = {
    "simulation",
    "limits",
    "concurrency",
    "retries",
    "filters",
    "quality",
    "http",
    "expression",
    "feedback",
    "runtime",
}


def clear_schema_cache() -> None:
    """Clear cached schema keys after YAML cache invalidation."""
    global _schema_keys_cache
    with _schema_lock:
        _schema_keys_cache = None


def _collect_leaf_paths(data: Any, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    """Collect all leaf key paths in a nested dict."""
    paths: set[tuple[str, ...]] = set()
    if not isinstance(data, dict):
        return paths
    for key, value in data.items():
        full = (*prefix, key)
        if isinstance(value, dict) and value:
            paths.update(_collect_leaf_paths(value, full))
        else:
            paths.add(full)
    return paths


def _collect_all_string_keys(data: Any) -> set[str]:
    """Collect every key name that appears in a nested dict."""
    keys: set[str] = set()
    if not isinstance(data, dict):
        return keys
    for key, value in data.items():
        keys.add(key)
        if isinstance(value, dict):
            keys.update(_collect_all_string_keys(value))
    return keys


def _get_schema_keys(resolved_files: dict[str, str]) -> dict[str, set[str]]:
    """Extract top-level keys from actual YAML source files."""
    global _schema_keys_cache
    with _schema_lock:
        if _schema_keys_cache is not None:
            return _schema_keys_cache

        keys_by_file: dict[str, set[str]] = {}
        keys_by_file["settings"] = {"global", "dataset_profiles", "expression_policies"}

        for name in DEFAULT_CONFIG_NAMES | {"dataset_profiles", "expression_policies"}:
            path = resolved_files.get(name)
            if path:
                data = load_yaml_file(path)
                if isinstance(data, dict):
                    keys_by_file[name] = set(data.keys())

        _schema_keys_cache = keys_by_file
        return keys_by_file


def _validate_top_level_keys(
    config: YamlConfig,
    schema_keys: dict[str, set[str]],
) -> list[str]:
    """Check that top-level keys come from known YAML files."""
    all_top_keys: set[str] = set()
    for keys in schema_keys.values():
        all_top_keys.update(keys)

    unknown = set(config.keys()) - all_top_keys
    if unknown:
        return [
            f"未知顶层 key: {sorted(unknown)}。可能是 YAML 中的拼写错误，请在对应 YAML 文件中检查。"
        ]
    return []


def _validate_global_section(config: YamlConfig, resolved_files: dict[str, str]) -> list[str]:
    """Validate merged YAML global subsection names."""
    if "settings" not in resolved_files:
        return []

    global_section = config.get("global", {})
    if not isinstance(global_section, dict):
        return []

    return [
        f"YAML global 段存在未知 key '{gkey}'，已知 key: {sorted(GLOBAL_KNOWN_KEYS)}"
        for gkey in global_section
        if gkey not in GLOBAL_KNOWN_KEYS
    ]


def _validate_cross_consistency(
    config: YamlConfig,
    resolved_files: dict[str, str],
) -> list[str]:
    """Validate overlapping global.* keys against default YAML sections."""
    overlap_sections = {"quality", "http", "expression", "feedback"}
    known_aliases: dict[str, dict[str, str]] = {
        "feedback": {
            "feedback_mutation_nearpass_threshold": "mutation_nearpass_threshold",
            "feedback_mutation_highscore_threshold": "mutation_highscore_threshold",
            "feedback_template_min_priority": "template_min_priority",
        },
        "http": {
            "backend": "@settings_only",
        },
    }

    warnings: list[str] = []
    defaults_data = load_default_yamls(resolved_files)
    if not defaults_data:
        return warnings

    global_section = config.get("global", {})
    if not isinstance(global_section, dict):
        return warnings

    for section in overlap_sections:
        gdata = global_section.get(section)
        if not isinstance(gdata, dict):
            continue

        defaults_section = defaults_data.get(section)
        if not isinstance(defaults_section, dict):
            continue

        defaults_keys = _collect_all_string_keys(defaults_section)
        if not defaults_keys:
            continue

        aliases = known_aliases.get(section, {})
        extra = []
        for skey in gdata:
            if skey in defaults_keys:
                continue
            if skey in aliases and (aliases[skey] in defaults_keys or aliases[skey] == "@settings_only"):
                continue
            extra.append(skey)

        if extra:
            warnings.append(
                f"交叉一致性警告: YAML global.{section} 中的 key "
                + f"{sorted(extra)} 在默认 YAML 的 {section} 段中不存在。"
                + f"可能是键名拼写错误。已知 key: {sorted(defaults_keys)}"
            )

    return warnings


def _validate_nested_paths(config: YamlConfig) -> list[str]:
    """Warn on unexpectedly deep generic settings sections."""
    warnings: list[str] = []
    skip_sections = {"global", "dataset_profiles", "expression_policies"}

    for section, section_data in config.items():
        if section in skip_sections or not isinstance(section_data, dict):
            continue

        if section in GLOBAL_KNOWN_KEYS:
            leaf_paths = _collect_leaf_paths(section_data, (section,))
            warnings.extend(
                f"嵌套过深: {' > '.join(path)}，请检查默认 YAML 中 {section} 段的结构。"
                for path in leaf_paths
                if len(path) > 4
            )

    return warnings


def validate_merged_config(config: Any, resolved_files: dict[str, str]) -> list[str]:
    """Validate merged YAML config and return warnings."""
    if not isinstance(config, dict):
        return []

    schema_keys = _get_schema_keys(resolved_files)

    warnings: list[str] = []
    warnings.extend(_validate_top_level_keys(config, schema_keys))
    warnings.extend(_validate_global_section(config, resolved_files))
    warnings.extend(_validate_cross_consistency(config, resolved_files))
    warnings.extend(_validate_nested_paths(config))
    return warnings
