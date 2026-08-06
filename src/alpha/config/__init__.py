"""Compatibility facade for the config package.

This module preserves the historical ``alpha.config`` import surface while
avoiding eager wildcard imports across constants, models, and YAML
helpers. Internal modules should prefer importing focused submodules directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .constants import __all__ as _constant_exports
from .._facade import facade_dir, resolve_export

if TYPE_CHECKING:
    from .application import ApplicationConfig
    from .application_sections import (
        CredentialsConfig,
        DatasetConfig,
        ExecutionConfig,
        PlanningConfig,
        QualityConfig,
        RuntimeFlagsConfig,
        SimulationConfig,
    )
    from .constants import *
    from .defaults import apply_yaml_global_defaults
    from .models import (
        DatasetExpressionPolicy,
        FeedbackLoopPolicy,
        FeedbackPhasePolicy,
        FieldTransformSpec,
        FieldTransformStage,
    )
    from .profiles import DEFAULT_PROFILE, get_dataset_profile
    from .runtime_values import clear_runtime_config_cache, get_runtime_config
    from .yaml import (
        clear_yaml_caches,
        get_yaml_config,
        load_yaml_config,
        validate_yaml_config,
    )

_EXPORT_MAP: dict[str, tuple[str, str]] = {
    **{name: (".constants", name) for name in _constant_exports},
    "ApplicationConfig": (".application", "ApplicationConfig"),
    "CredentialsConfig": (".application_sections", "CredentialsConfig"),
    "DatasetConfig": (".application_sections", "DatasetConfig"),
    "ExecutionConfig": (".application_sections", "ExecutionConfig"),
    "PlanningConfig": (".application_sections", "PlanningConfig"),
    "QualityConfig": (".application_sections", "QualityConfig"),
    "RuntimeFlagsConfig": (".application_sections", "RuntimeFlagsConfig"),
    "SimulationConfig": (".application_sections", "SimulationConfig"),
    "apply_yaml_global_defaults": (".defaults", "apply_yaml_global_defaults"),
    "DatasetExpressionPolicy": (".models", "DatasetExpressionPolicy"),
    "FeedbackLoopPolicy": (".models", "FeedbackLoopPolicy"),
    "FeedbackPhasePolicy": (".models", "FeedbackPhasePolicy"),
    "FieldTransformSpec": (".models", "FieldTransformSpec"),
    "FieldTransformStage": (".models", "FieldTransformStage"),
    "DEFAULT_PROFILE": (".profiles", "DEFAULT_PROFILE"),
    "get_dataset_profile": (".profiles", "get_dataset_profile"),
    "clear_yaml_caches": (".yaml", "clear_yaml_caches"),
    "get_yaml_config": (".yaml", "get_yaml_config"),
    "load_yaml_config": (".yaml", "load_yaml_config"),
    "validate_yaml_config": (".yaml", "validate_yaml_config"),
    "clear_runtime_config_cache": (".runtime_values", "clear_runtime_config_cache"),
    "get_runtime_config": (".runtime_values", "get_runtime_config"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str) -> object:
    return resolve_export(
        name=name,
        export_map=_EXPORT_MAP,
        package=__package__,
        namespace=__name__,
        target_globals=globals(),
    )


def __dir__() -> list[str]:
    return facade_dir(globals(), _EXPORT_MAP)
