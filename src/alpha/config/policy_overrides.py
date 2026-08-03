"""YAML expression-policy override parsing."""

from __future__ import annotations

from dataclasses import replace
import logging
from typing import Any, cast

from .expression_policy_schema import (
    EXPRESSION_POLICY_DICT_INT_FIELDS,
    EXPRESSION_POLICY_DICT_TUPLE_FIELDS,
    EXPRESSION_POLICY_FEEDBACK_LOOP_FIELD,
    EXPRESSION_POLICY_INT_FIELDS,
    EXPRESSION_POLICY_META_FIELDS,
    EXPRESSION_POLICY_SET_FIELDS,
    EXPRESSION_POLICY_TEMPLATE_PREFIX_PENALTIES_FIELD,
    EXPRESSION_POLICY_TEMPLATE_SPEC_FIELDS,
    EXPRESSION_POLICY_TRANSFORM_FIELDS,
    EXPRESSION_POLICY_TUPLE_FIELDS,
    EXPRESSION_POLICY_TUPLE_PAIR_FIELDS,
    EXPRESSION_POLICY_TUPLE_WINDOW2_FIELDS,
    EXPRESSION_POLICY_TUPLE_WINDOW3_FIELDS,
)
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
from .yaml import get_yaml_config

logger = logging.getLogger(__name__)


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

    for key, value in overrides.items():
        if key in EXPRESSION_POLICY_META_FIELDS:
            continue  # meta 字段，不映射到 DatasetExpressionPolicy
        if not hasattr(policy, key):
            logger.warning(
                "[config] ignoring unknown expression policy key '%s' for dataset=%s",
                key,
                dataset_id,
            )
            continue
        if key in EXPRESSION_POLICY_SET_FIELDS and isinstance(value, (list, tuple, set)):
            update_map[key] = {str(item) for item in value}
        elif key in EXPRESSION_POLICY_TUPLE_FIELDS and isinstance(value, (list, tuple)):
            update_map[key] = tuple(str(item) for item in value)
        elif key in EXPRESSION_POLICY_DICT_TUPLE_FIELDS and isinstance(value, dict):
            update_map[key] = {
                str(name): tuple(str(item) for item in items)
                for name, items in value.items()
                if isinstance(items, (list, tuple))
            }
        elif key in EXPRESSION_POLICY_DICT_INT_FIELDS and isinstance(value, dict):
            coerced: dict[Any, int] = {}
            for name, score in value.items():
                resolved = resolve_tier_value(score, tiers)
                if resolved is not None:
                    coerced[name] = resolved
            update_map[key] = coerced
        elif key == EXPRESSION_POLICY_TEMPLATE_PREFIX_PENALTIES_FIELD:
            update_map[key] = coerce_template_prefix_penalties(value, tiers=tiers)
        elif key in EXPRESSION_POLICY_INT_FIELDS:
            resolved = resolve_tier_value(value, tiers)
            if resolved is not None:
                update_map[key] = resolved
        elif key in EXPRESSION_POLICY_TUPLE_PAIR_FIELDS and isinstance(value, (list, tuple)):
            update_map[key] = {
                (str(item[0]), str(item[1]))
                for item in value
                if isinstance(item, (list, tuple)) and len(item) == 2
            }
        elif key in EXPRESSION_POLICY_TUPLE_WINDOW3_FIELDS:
            update_map[key] = tuple_tuple_int(value, 3)
        elif key in EXPRESSION_POLICY_TUPLE_WINDOW2_FIELDS:
            update_map[key] = tuple_tuple_int(value, 2)
        elif key in EXPRESSION_POLICY_TEMPLATE_SPEC_FIELDS:
            update_map[key] = tuple_tuple_str_int(value)
        elif key in EXPRESSION_POLICY_TRANSFORM_FIELDS:
            transform = coerce_field_transform_spec(value)
            if transform is not None:
                update_map[key] = transform
        elif key == EXPRESSION_POLICY_FEEDBACK_LOOP_FIELD:
            loop_policy = coerce_feedback_loop_policy(value)
            if loop_policy is not None:
                update_map[key] = loop_policy
        else:
            update_map[key] = value

    return replace(policy, **update_map)
