"""Compatibility facade for the config package.

This module preserves the historical ``alpha.config`` import surface while
avoiding eager wildcard imports across constants, getters, models, and YAML
helpers. Internal modules should prefer importing focused submodules directly.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from .constants import __all__ as _CONSTANT_EXPORTS
from .getters import __all__ as _GETTER_EXPORTS

if TYPE_CHECKING:
    from .constants import *
    from .defaults import apply_yaml_global_defaults
    from .getters import *
    from .models import (
        DatasetExpressionPolicy,
        FeedbackLoopPolicy,
        FeedbackPhasePolicy,
        FieldTransformSpec,
        FieldTransformStage,
    )
    from .profiles import DATASET_PROFILES, DEFAULT_PROFILE, get_dataset_profile
    from .runtime_values import clear_runtime_config_cache, get_runtime_config
    from .yaml import (
        clear_yaml_caches,
        get_yaml_config,
        load_yaml_config,
        validate_yaml_config,
    )

__all__ = [
    *_CONSTANT_EXPORTS,
    *_GETTER_EXPORTS,
    "DatasetExpressionPolicy",
    "FeedbackLoopPolicy",
    "FeedbackPhasePolicy",
    "FieldTransformSpec",
    "FieldTransformStage",
    "DATASET_PROFILES",
    "DEFAULT_PROFILE",
    "get_dataset_profile",
    "clear_yaml_caches",
    "get_yaml_config",
    "load_yaml_config",
    "validate_yaml_config",
    "clear_runtime_config_cache",
    "get_runtime_config",
    "apply_yaml_global_defaults",
]

_EXPORT_MAP: dict[str, tuple[str, str]] = {
    **{name: (".constants", name) for name in _CONSTANT_EXPORTS},
    **{name: (".getters", name) for name in _GETTER_EXPORTS},
    "apply_yaml_global_defaults": (".defaults", "apply_yaml_global_defaults"),
    "DatasetExpressionPolicy": (".models", "DatasetExpressionPolicy"),
    "FeedbackLoopPolicy": (".models", "FeedbackLoopPolicy"),
    "FeedbackPhasePolicy": (".models", "FeedbackPhasePolicy"),
    "FieldTransformSpec": (".models", "FieldTransformSpec"),
    "FieldTransformStage": (".models", "FieldTransformStage"),
    "DATASET_PROFILES": (".profiles", "DATASET_PROFILES"),
    "DEFAULT_PROFILE": (".profiles", "DEFAULT_PROFILE"),
    "get_dataset_profile": (".profiles", "get_dataset_profile"),
    "clear_yaml_caches": (".yaml", "clear_yaml_caches"),
    "get_yaml_config": (".yaml", "get_yaml_config"),
    "load_yaml_config": (".yaml", "load_yaml_config"),
    "validate_yaml_config": (".yaml", "validate_yaml_config"),
    "clear_runtime_config_cache": (".runtime_values", "clear_runtime_config_cache"),
    "get_runtime_config": (".runtime_values", "get_runtime_config"),
}


def __getattr__(name: str) -> object:
    try:
        module_name, attr_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name, __package__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
