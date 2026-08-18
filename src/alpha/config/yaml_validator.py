"""Schema and consistency validation for merged YAML configuration."""

from __future__ import annotations

import threading
from typing import Any

from .strategy_profile_schema import (
    STRATEGY_PROFILE_CHOICES,
    STRATEGY_PROFILE_SCHEMA_KEYS,
    STRATEGY_PROFILE_TUNING_KEYS,
    STRATEGY_PROFILE_TUNING_SECTIONS,
    validate_runtime_defaults,
)
from .types import YamlConfig
from .yaml_sources import (
    DEFAULT_CONFIG_NAMES,
    config_file_signature,
    load_default_yamls,
    load_yaml_file,
    validate_default_yaml_ownership,
)

_schema_lock = threading.RLock()
_SchemaSignature = tuple[tuple[str, tuple[int, int, int] | None], ...]
_schema_keys_cache: tuple[_SchemaSignature, dict[str, set[str]]] | None = None

_NESTED_CONFIG_SECTIONS = {
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

_GLOBAL_EXTRA_LEAF_KEYS: dict[str, frozenset[str]] = {
    "simulation": frozenset({"testPeriodYears", "testPeriodMonths"}),
    "http": frozenset(
        {
            "request_timeout",
            "rate_limit_default_wait",
            "polling_default_wait",
            "polling_no_retry_after_wait",
            "server_error_backoff_max",
            "server_error_backoff_step",
            "retry_operation_default_wait",
            "login_retry_wait",
            "simulation_retry_wait",
            "polling_retry_buffer",
        }
    ),
    "feedback": frozenset(
        {
            "mutation_highscore_threshold",
            "template_min_priority",
            "feedback_mutation_highscore_threshold",
            "feedback_template_min_priority",
            "delta_std_priority_boost",
            "expr_nearpass_boost_threshold",
            "expr_iter_boost_threshold",
            "expr_ratio_penalty_threshold",
            "expr_fail_penalty_threshold",
            "expr_mutation_extend_threshold",
        }
    ),
}


def clear_schema_cache() -> None:
    """Clear cached schema keys after YAML cache invalidation."""
    global _schema_keys_cache
    with _schema_lock:
        _schema_keys_cache = None


def _resolved_files_signature(resolved_files: dict[str, str]) -> _SchemaSignature:
    """Build a content-sensitive signature for the resolved YAML sources."""
    return tuple(
        (name, config_file_signature(path)) for name, path in sorted(resolved_files.items())
    )


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
    signature = _resolved_files_signature(resolved_files)
    with _schema_lock:
        if _schema_keys_cache is not None and _schema_keys_cache[0] == signature:
            return _schema_keys_cache[1]

        keys_by_file: dict[str, set[str]] = {}
        keys_by_file["settings"] = {"global", "dataset_profiles", "expression_policies"}

        for name in DEFAULT_CONFIG_NAMES | {
            "strategy_profiles",
            "dataset_profiles",
            "expression_policies",
        }:
            path = resolved_files.get(name)
            if path:
                data = load_yaml_file(path)
                if isinstance(data, dict):
                    keys_by_file[name] = set(data.keys())

        _schema_keys_cache = (signature, keys_by_file)
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
    if isinstance(global_section, dict):
        return []
    return ["YAML global 段必须是 mapping。"]


def global_leaf_path_schema() -> frozenset[tuple[str, ...]]:
    """Return every nested configuration path accepted below ``global``.

    The canonical default YAML owns static values, while ``SettingSpec`` owns
    CLI-resolved values.  Their union keeps both configuration paths valid and
    lets the validator reject a typo at its actual nested location.
    """
    from .settings_spec import yaml_default_settings
    from .yaml_sources import resolve_all_yaml_files

    paths = _collect_leaf_paths(load_default_yamls(resolve_all_yaml_files()))
    for spec in yaml_default_settings():
        if spec.yaml is not None:
            paths.add(spec.yaml)
    for section, keys in _GLOBAL_EXTRA_LEAF_KEYS.items():
        paths.update((section, key) for key in keys)
    return frozenset(paths)


def validate_global_leaf_keys(global_config: dict[str, object]) -> list[str]:
    """Report unknown or malformed nested configuration leaves below ``global``."""
    allowed_paths = global_leaf_path_schema()
    mapping_paths = {path[:depth] for path in allowed_paths for depth in range(1, len(path))}
    warnings: list[str] = []

    def visit(path: tuple[str, ...], value: object) -> None:
        display_path = f"global.{'.'.join(path)}"
        if isinstance(value, dict):
            if path in allowed_paths:
                warnings.append(f"{display_path} 必须是标量值，不能是 mapping。")
                return
            if path not in mapping_paths:
                warnings.append(f"{display_path} 是未知配置路径。")
                return
            for key, nested_value in value.items():
                visit((*path, str(key)), nested_value)
            return
        if path in allowed_paths:
            return
        if path in mapping_paths:
            warnings.append(f"{display_path} 必须是 mapping。")
            return
        warnings.append(f"{display_path} 是未知配置路径。")

    for section, value in global_config.items():
        visit((str(section),), value)
    return warnings


def _validate_cross_consistency(
    config: YamlConfig,
    resolved_files: dict[str, str],
) -> list[str]:
    """Validate overlapping global.* keys against default YAML sections."""
    overlap_sections = {"quality", "http", "expression", "feedback"}
    known_aliases: dict[str, dict[str, str]] = {
        "feedback": {
            "feedback_mutation_highscore_threshold": "mutation_highscore_threshold",
            "feedback_template_min_priority": "template_min_priority",
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
            if skey in aliases and (
                aliases[skey] in defaults_keys or aliases[skey] == "@settings_only"
            ):
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
    skip_sections = {"global", "strategy_profiles", "dataset_profiles", "expression_policies"}

    for section, section_data in config.items():
        if section in skip_sections or not isinstance(section_data, dict):
            continue

        if section in _NESTED_CONFIG_SECTIONS:
            leaf_paths = _collect_leaf_paths(section_data, (section,))
            warnings.extend(
                f"嵌套过深: {' > '.join(path)}，请检查默认 YAML 中 {section} 段的结构。"
                for path in leaf_paths
                if len(path) > 4
            )

    return warnings


def _validate_strategy_profiles_section(config: YamlConfig) -> list[str]:
    """Validate the descriptive strategy profile schema."""
    section = config.get("strategy_profiles", {})
    if not isinstance(section, dict):
        return []

    warnings: list[str] = []
    for profile_name, profile_data in section.items():
        if profile_name not in STRATEGY_PROFILE_CHOICES:
            warnings.append(
                f"strategy_profiles 存在未知 profile '{profile_name}'，"
                f"已知 profile: {list(STRATEGY_PROFILE_CHOICES)}"
            )
            continue
        if not isinstance(profile_data, dict):
            warnings.append(f"strategy_profiles.{profile_name} 必须是 mapping。")
            continue

        unknown_keys = set(profile_data) - STRATEGY_PROFILE_SCHEMA_KEYS
        if unknown_keys:
            warnings.append(
                f"strategy_profiles.{profile_name} 存在未知 key {sorted(unknown_keys)}，"
                f"已知 key: {sorted(STRATEGY_PROFILE_SCHEMA_KEYS)}"
            )

        warnings.extend(
            f"strategy_profiles.{profile_name}.{text_key} 必须是字符串。"
            for text_key in ("purpose", "primary_goal")
            if text_key in profile_data and not isinstance(profile_data[text_key], str)
        )
        notes = profile_data.get("notes", [])
        if not isinstance(notes, list) or any(not isinstance(item, str) for item in notes):
            warnings.append(f"strategy_profiles.{profile_name}.notes 必须是字符串列表。")

        tuning_keys = profile_data.get("tuning_keys", {})
        if not isinstance(tuning_keys, dict):
            warnings.append(f"strategy_profiles.{profile_name}.tuning_keys 必须是 mapping。")
            continue

        unknown_sections = set(tuning_keys) - STRATEGY_PROFILE_TUNING_SECTIONS
        if unknown_sections:
            warnings.append(
                f"strategy_profiles.{profile_name}.tuning_keys 存在未知 section "
                f"{sorted(unknown_sections)}，已知 section: "
                f"{sorted(STRATEGY_PROFILE_TUNING_SECTIONS)}"
            )
        for section_name, keys in tuning_keys.items():
            if not isinstance(keys, list) or any(not isinstance(item, str) for item in keys):
                warnings.append(
                    f"strategy_profiles.{profile_name}.tuning_keys.{section_name} "
                    "必须是字符串列表。"
                )
                continue
            known_keys = STRATEGY_PROFILE_TUNING_KEYS.get(section_name, set())
            unknown_tuning_keys = set(keys) - known_keys
            if unknown_tuning_keys:
                warnings.append(
                    f"strategy_profiles.{profile_name}.tuning_keys.{section_name} "
                    f"存在未知 key {sorted(unknown_tuning_keys)}，已知 key: {sorted(known_keys)}"
                )

        runtime_defaults = profile_data.get("runtime_defaults", {})
        warnings.extend(validate_runtime_defaults(profile_name, runtime_defaults))

    return warnings


def validate_merged_config(config: Any, resolved_files: dict[str, str]) -> list[str]:
    """Validate merged YAML config and return warnings."""
    if not isinstance(config, dict):
        return []

    schema_keys = _get_schema_keys(resolved_files)

    warnings: list[str] = []
    warnings.extend(validate_default_yaml_ownership(resolved_files))
    warnings.extend(_validate_top_level_keys(config, schema_keys))
    warnings.extend(_validate_global_section(config, resolved_files))
    global_section = config.get("global", {})
    if isinstance(global_section, dict):
        warnings.extend(validate_global_leaf_keys(global_section))
    warnings.extend(_validate_cross_consistency(config, resolved_files))
    warnings.extend(_validate_strategy_profiles_section(config))
    warnings.extend(_validate_nested_paths(config))
    return warnings
