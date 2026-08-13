"""Composed index for declarative CLI, YAML, and runtime settings.

Setting declarations live beside their runtime responsibility.  This module is
the single assembly point consumed by the parser and configuration resolver.
"""

from __future__ import annotations

from typing import Any

from .settings_spec_dataset import DATASET_SETTINGS, SIMULATION_SETTINGS
from .settings_spec_execution import EXECUTION_SETTINGS
from .settings_spec_planning import PLANNING_SETTINGS
from .settings_spec_quality import QUALITY_SETTINGS
from .settings_spec_runtime import RUNTIME_SETTINGS
from .settings_spec_types import SettingSpec, cast_setting_value

SETTINGS: tuple[SettingSpec, ...] = (
    DATASET_SETTINGS
    + SIMULATION_SETTINGS
    + PLANNING_SETTINGS
    + EXECUTION_SETTINGS
    + QUALITY_SETTINGS
    + RUNTIME_SETTINGS
)


def get_setting(dest: str) -> SettingSpec:
    """Return one setting by destination name."""
    for spec in SETTINGS:
        if spec.dest == dest:
            return spec
    raise KeyError(dest)


def yaml_default_settings() -> tuple[SettingSpec, ...]:
    """Return settings backed by a YAML default path."""
    return tuple(spec for spec in SETTINGS if spec.yaml is not None)


def dataset_profile_keys() -> tuple[str, ...]:
    """Return destinations that a dataset profile may override."""
    return tuple(spec.dest for spec in SETTINGS if spec.dataset_profile)


def settings_by_yaml_section(section: str) -> tuple[SettingSpec, ...]:
    """Return settings declared under one global YAML section."""
    return tuple(spec for spec in SETTINGS if spec.yaml is not None and spec.yaml[0] == section)


def section_settings(section: str) -> tuple[SettingSpec, ...]:
    """Return settings belonging to one typed runtime configuration section."""
    return tuple(spec for spec in SETTINGS if spec.section == section)


def section_args(section: str, args: object) -> dict[str, Any]:
    """Build one typed runtime section from resolved CLI arguments."""
    return {
        spec.dest: cast_setting_value(spec, getattr(args, spec.dest, spec.fallback))
        for spec in section_settings(section)
    }
