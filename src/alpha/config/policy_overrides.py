"""YAML expression-policy override parsing."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from .models import DatasetExpressionPolicy
from .policy_coercers import (
    coerce_feedback_loop_policy,
    coerce_field_transform_spec,
    coerce_template_prefix_penalties,
    resolve_priority_tiers,
    resolve_tier_value,
    tuple_tuple_int,
    tuple_tuple_str_int,
)
from .types import ExpressionPolicyOverrides, YamlConfig


def _merge_policy_values(base: Any, override: Any, *, key: str = "") -> Any:
    replace_list_keys = {"stages", "preferred_template_stages"}
    if isinstance(base, dict) and isinstance(override, dict):
        merged_dict = dict(base)
        for child_key, value in override.items():
            merged_dict[child_key] = _merge_policy_values(
                merged_dict.get(child_key),
                value,
                key=child_key,
            )
        return merged_dict
    if isinstance(base, list) and isinstance(override, list):
        if key in replace_list_keys:
            return list(override)
        return [*base, *override]
    if isinstance(base, tuple) and isinstance(override, tuple):
        if key in replace_list_keys:
            return tuple(override)
        return (*base, *override)
    return override


def _policy_config_for_dataset(
    dataset_id: str,
    *,
    use_curated_heuristics: bool | None = None,
    yaml_config: YamlConfig | None = None,
) -> ExpressionPolicyOverrides:
    if yaml_config is None:
        from . import get_yaml_config

        yaml_config = get_yaml_config()
    section = yaml_config.get("expression_policies", {})
    if not isinstance(section, dict):
        return {}

    merged: ExpressionPolicyOverrides = {}
    default_cfg = section.get("__default__", {})
    if isinstance(default_cfg, dict):
        merged = _merge_policy_values(merged, default_cfg)
    if use_curated_heuristics:
        curated_cfg = section.get("__curated__", {})
        if isinstance(curated_cfg, dict):
            merged = _merge_policy_values(merged, curated_cfg)
    dataset_cfg = section.get(dataset_id, {})
    if isinstance(dataset_cfg, dict):
        merged = _merge_policy_values(merged, dataset_cfg)
    return merged


def apply_yaml_expression_policy_overrides(
    policy: DatasetExpressionPolicy,
    *,
    dataset_id: str,
    use_curated_heuristics: bool | None = None,
    yaml_config: YamlConfig | None = None,
) -> DatasetExpressionPolicy:
    """Apply YAML expression-policy overrides to a base policy.

    支持 @tier_name 引用语法：在 priority_tiers 中定义命名 tier，
    然后在 int 型字段中使用 @account_boost、@heavy_penalty 等引用。
    """
    overrides = _policy_config_for_dataset(
        dataset_id,
        use_curated_heuristics=use_curated_heuristics,
        yaml_config=yaml_config,
    )
    if not overrides:
        return policy

    # 解析 priority_tiers 供 @tier_name 引用
    tiers = resolve_priority_tiers(cast(dict[str, Any], overrides))

    update_map: dict[str, Any] = {}
    set_fields = {
        "disabled_templates",
        "protected_templates",
        "positive_raw_fields",
        "negative_raw_fields",
        "overtested_weak_fields",
        "always_keep_families",
        "slow_template_names",
        "concentrated_weak_families",
        "concentrated_weak_names",
        "low_sharpe_weak_ratio_families",
        "weak_mean_spread_fields",
        "broken_zscore_spread_fields",
        "weak_ratio_standalone_fields",
        "event_allowed_template_families",
    }
    tuple_fields = {
        "blacklisted_template_name_substrings",
        "slow_template_prefixes",
        "concentrated_weak_prefixes",
        "low_sharpe_weak_ratio_prefixes",
        "event_field_prefixes",
        "event_allowed_template_stages",
        "event_allowed_template_prefixes",
    }
    dict_tuple_fields = {"ratio_partner_candidates", "ratio_keywords"}
    dict_int_fields = {
        "template_priority_penalties",
        "preferred_partner_score_bonuses",
        "preferred_field_order",
    }
    # 单一 int 字段，支持 @tier 引用
    int_fields = {
        "account_template_boost",
        "high_conviction_ratio_priority_boost",
        "partner_limit",
    }
    tuple_pair_fields = {"high_conviction_ratio_pairs"}
    tuple_window3_fields = {"matrix_delta_over_std_windows", "ratio_delta_over_std_windows"}
    tuple_window2_fields = {"ratio_delta_rank_windows"}
    template_spec_fields = {
        "matrix_diversified_template_specs",
        "ratio_diversified_template_specs",
        "ratio_legacy_template_specs",
    }
    transform_fields = {
        "default_field_transform",
        "matrix_field_transform",
        "vector_field_transform",
        "ratio_numerator_transform",
        "ratio_denominator_transform",
    }

    for key, value in overrides.items():
        if key == "priority_tiers":
            continue  # meta 字段，不映射到 DatasetExpressionPolicy
        if not hasattr(policy, key):
            continue
        if key in set_fields and isinstance(value, (list, tuple, set)):
            update_map[key] = {str(item) for item in value}
        elif key in tuple_fields and isinstance(value, (list, tuple)):
            update_map[key] = tuple(str(item) for item in value)
        elif key in dict_tuple_fields and isinstance(value, dict):
            update_map[key] = {
                str(name): tuple(str(item) for item in items)
                for name, items in value.items()
                if isinstance(items, (list, tuple))
            }
        elif key in dict_int_fields and isinstance(value, dict):
            coerced: dict[Any, int] = {}
            for name, score in value.items():
                resolved = resolve_tier_value(score, tiers)
                if resolved is not None:
                    coerced[name] = resolved
            update_map[key] = coerced
        elif key == "template_prefix_penalties":
            update_map[key] = coerce_template_prefix_penalties(value, tiers=tiers)
        elif key in int_fields:
            resolved = resolve_tier_value(value, tiers)
            if resolved is not None:
                update_map[key] = resolved
        elif key in tuple_pair_fields and isinstance(value, (list, tuple)):
            update_map[key] = {
                (str(item[0]), str(item[1]))
                for item in value
                if isinstance(item, (list, tuple)) and len(item) == 2
            }
        elif key in tuple_window3_fields:
            update_map[key] = tuple_tuple_int(value, 3)
        elif key in tuple_window2_fields:
            update_map[key] = tuple_tuple_int(value, 2)
        elif key in template_spec_fields:
            update_map[key] = tuple_tuple_str_int(value)
        elif key in transform_fields:
            transform = coerce_field_transform_spec(value)
            if transform is not None:
                update_map[key] = transform
        elif key == "feedback_loop_policy":
            loop_policy = coerce_feedback_loop_policy(value)
            if loop_policy is not None:
                update_map[key] = loop_policy
        else:
            update_map[key] = value

    return replace(policy, **update_map)
