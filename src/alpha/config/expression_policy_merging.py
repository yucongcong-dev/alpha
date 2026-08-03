"""Merge expression-policy YAML overrides for a dataset."""

from __future__ import annotations

from typing import Any

from .types import ExpressionPolicyOverrides, YamlConfig
from .yaml import get_yaml_config

EXPRESSION_POLICY_REPLACE_LIST_KEYS = {"stages", "preferred_template_stages"}


def merge_expression_policy_values(base: Any, override: Any, *, key: str = "") -> Any:
    """Deep-merge expression-policy values while preserving legacy list semantics."""
    if isinstance(base, dict) and isinstance(override, dict):
        merged_dict = dict(base)
        for child_key, value in override.items():
            merged_dict[child_key] = merge_expression_policy_values(
                merged_dict.get(child_key),
                value,
                key=child_key,
            )
        return merged_dict
    if isinstance(base, list) and isinstance(override, list):
        if key in EXPRESSION_POLICY_REPLACE_LIST_KEYS:
            return list(override)
        return [*base, *override]
    if isinstance(base, tuple) and isinstance(override, tuple):
        if key in EXPRESSION_POLICY_REPLACE_LIST_KEYS:
            return tuple(override)
        return (*base, *override)
    return override


def expression_policy_overrides_for_dataset(
    dataset_id: str,
    *,
    use_curated_heuristics: bool | None = None,
    yaml_config: YamlConfig | None = None,
) -> ExpressionPolicyOverrides:
    """Resolve merged expression-policy overrides for one dataset."""
    if yaml_config is None:
        yaml_config = get_yaml_config()
    section = yaml_config.get("expression_policies", {})
    if not isinstance(section, dict):
        return {}

    merged: ExpressionPolicyOverrides = {}
    default_cfg = section.get("__default__", {})
    if isinstance(default_cfg, dict):
        merged = merge_expression_policy_values(merged, default_cfg)
    if use_curated_heuristics:
        curated_cfg = section.get("__curated__", {})
        if isinstance(curated_cfg, dict):
            merged = merge_expression_policy_values(merged, curated_cfg)
    dataset_cfg = section.get(dataset_id, {})
    if isinstance(dataset_cfg, dict):
        merged = merge_expression_policy_values(merged, dataset_cfg)
    return merged
