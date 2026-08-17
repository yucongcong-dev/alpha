"""Shared types for declarative CLI and runtime settings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_UNSET = object()


@dataclass(frozen=True, slots=True)
class SettingSpec:
    """One setting shared by the CLI, YAML, and typed runtime configuration."""

    dest: str
    yaml: tuple[str, ...] | None
    default: Any
    cli: str | None = None
    arg_type: Callable[[str], Any] | type = str
    help: str = ""
    help_disable: str = ""
    choices: tuple[str, ...] = ()
    kind: str = "plain"
    dataset_profile: bool = False
    section: str = ""
    fallback: Any = _UNSET
    or_default: Any = _UNSET
    coerce: bool = True


def setting_or_default(spec: SettingSpec) -> Any:
    """Return the fallback used for legacy ``value or default`` coercion."""
    if spec.or_default is not _UNSET:
        return spec.or_default
    if spec.arg_type is int:
        return 0
    if spec.arg_type is float:
        return 0.0
    return ""


def cast_setting_value(spec: SettingSpec, value: object) -> object:
    """Normalize an args value using the setting's declared type semantics."""
    raw: Any = value
    if spec.arg_type is int:
        return int(raw or setting_or_default(spec))
    if spec.arg_type is float:
        return float(raw or setting_or_default(spec))
    if spec.arg_type is bool:
        return bool(raw)
    if spec.coerce:
        return str(raw or setting_or_default(spec))
    return raw
