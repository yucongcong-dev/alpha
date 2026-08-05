"""Named strategy profile boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .strategy_profile_schema import (
    STRATEGY_PROFILE_CHOICES,
    validate_runtime_defaults,
)
from .types import YamlConfig
from .yaml import get_yaml_config

STRATEGY_PROFILE_EXPLORE = "explore"
STRATEGY_PROFILE_REFINE = "refine"
STRATEGY_PROFILE_SUBMIT_FOCUSED = "submit-focused"
DEFAULT_STRATEGY_PROFILE = STRATEGY_PROFILE_EXPLORE


@dataclass(frozen=True, slots=True)
class StrategyProfileSchema:
    """Descriptive schema for one named strategy profile."""

    name: str
    purpose: str
    primary_goal: str
    tuning_keys: dict[str, tuple[str, ...]]
    runtime_defaults: dict[str, dict[str, object]]
    notes: tuple[str, ...] = ()


def normalize_strategy_profile(value: object) -> str:
    """Return a supported strategy profile name."""
    profile = str(value or DEFAULT_STRATEGY_PROFILE).strip().lower()
    if profile not in STRATEGY_PROFILE_CHOICES:
        allowed = ", ".join(STRATEGY_PROFILE_CHOICES)
        raise ValueError(f"unsupported strategy_profile: {profile!r}; expected one of {allowed}")
    return profile


def load_strategy_profile_schemas(
    yaml_config: YamlConfig | None = None,
) -> dict[str, StrategyProfileSchema]:
    """Load descriptive strategy profile schemas from merged YAML.

    The returned schemas document tunable boundaries only. They do not rewrite
    runtime parameters or expression-policy defaults.
    """
    if yaml_config is None:
        yaml_config = get_yaml_config()
    section = yaml_config.get("strategy_profiles", {})
    if not isinstance(section, dict):
        return {}

    schemas: dict[str, StrategyProfileSchema] = {}
    for raw_name, raw_profile in section.items():
        name = normalize_strategy_profile(raw_name)
        if not isinstance(raw_profile, dict):
            raise ValueError(f"strategy_profiles.{name} must be a mapping")
        runtime_defaults = raw_profile.get("runtime_defaults", {})
        runtime_default_errors = validate_runtime_defaults(name, runtime_defaults)
        if runtime_default_errors:
            raise ValueError("; ".join(runtime_default_errors))
        schemas[name] = StrategyProfileSchema(
            name=name,
            purpose=str(raw_profile.get("purpose", "") or ""),
            primary_goal=str(raw_profile.get("primary_goal", "") or ""),
            tuning_keys=_coerce_tuning_keys(raw_profile.get("tuning_keys", {})),
            runtime_defaults=_coerce_runtime_defaults(runtime_defaults),
            notes=tuple(str(item) for item in _list_like(raw_profile.get("notes", ()))),
        )
    return schemas


def get_strategy_profile_runtime_defaults(
    profile: str,
    yaml_config: YamlConfig | None = None,
) -> dict[str, object]:
    """Return flattened runtime defaults for a strategy profile."""
    schemas = load_strategy_profile_schemas(yaml_config)
    schema = schemas.get(normalize_strategy_profile(profile))
    if schema is None:
        return {}
    defaults: dict[str, object] = {}
    for section_defaults in schema.runtime_defaults.values():
        defaults.update(section_defaults)
    return defaults


def _coerce_tuning_keys(value: object) -> dict[str, tuple[str, ...]]:
    """Coerce tuning key groups from YAML."""
    if not isinstance(value, dict):
        return {}
    tuning_keys: dict[str, tuple[str, ...]] = {}
    for section, keys in value.items():
        tuning_keys[str(section)] = tuple(str(item) for item in _list_like(keys))
    return tuning_keys


def _coerce_runtime_defaults(value: object) -> dict[str, dict[str, object]]:
    """Coerce strategy runtime defaults from YAML."""
    if not isinstance(value, dict):
        return {}
    defaults: dict[str, dict[str, object]] = {}
    for section, section_defaults in value.items():
        if isinstance(section_defaults, dict):
            defaults[str(section)] = dict(section_defaults)
    return defaults


def _list_like(value: object) -> tuple[Any, ...]:
    """Normalize YAML scalar/list values into a tuple."""
    if isinstance(value, (list, tuple)):
        return tuple(value)
    if value:
        return (value,)
    return ()
