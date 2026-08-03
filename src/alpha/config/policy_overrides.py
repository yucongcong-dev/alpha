"""YAML expression-policy override parsing."""

from __future__ import annotations

from dataclasses import replace
import logging
from typing import Any, cast

from .expression_policy_coercion import coerce_expression_policy_override
from .expression_policy_merging import expression_policy_overrides_for_dataset
from .expression_policy_schema import (
    EXPRESSION_POLICY_META_FIELDS,
)
from .models import DatasetExpressionPolicy
from .policy_coercers import resolve_priority_tiers
from .types import YamlConfig

logger = logging.getLogger(__name__)


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
    overrides = expression_policy_overrides_for_dataset(
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
        should_update, coerced_value = coerce_expression_policy_override(key, value, tiers=tiers)
        if should_update:
            update_map[key] = coerced_value

    return replace(policy, **update_map)
