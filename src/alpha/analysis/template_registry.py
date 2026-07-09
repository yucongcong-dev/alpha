"""Compatibility export layer for template registry helpers."""

from __future__ import annotations

from .template_registry_budget import (
    choose_family_settings_budget,
    choose_field_cluster_settings_budget,
    choose_registry_settings_budget,
)
from .template_registry_rules import (
    compile_template_family_registry,
    compile_template_registry_summary,
    merge_registry_recommendations_into_template_stats,
    normalize_activation_scope,
    normalize_template_role,
    recommend_template_role_transition,
)
from .template_registry_store import (
    DEFAULT_OVERRIDE_PAYLOAD,
    build_template_registry_index,
    load_persisted_template_registry,
    load_registry_overrides,
    resolve_registry_override,
)

__all__ = [
    "DEFAULT_OVERRIDE_PAYLOAD",
    "build_template_registry_index",
    "choose_family_settings_budget",
    "choose_field_cluster_settings_budget",
    "choose_registry_settings_budget",
    "compile_template_family_registry",
    "compile_template_registry_summary",
    "load_persisted_template_registry",
    "load_registry_overrides",
    "merge_registry_recommendations_into_template_stats",
    "normalize_activation_scope",
    "normalize_template_role",
    "resolve_registry_override",
    "recommend_template_role_transition",
]
