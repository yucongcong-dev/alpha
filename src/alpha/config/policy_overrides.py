"""YAML expression-policy override parsing."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .constants import DEFAULT_SETTINGS_VARIANT_BUDGET, STATS_DEFAULT_SCORE
from .models import (
    DatasetExpressionPolicy,
    FeedbackLoopPolicy,
    FeedbackPhasePolicy,
    FieldTransformSpec,
    FieldTransformStage,
)
from .types import ExpressionPolicyOverrides, YamlConfig


def _tuple_tuple_int(value: Any, width: int) -> tuple[tuple[int, ...], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    rows: list[tuple[int, ...]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != width:
            continue
        try:
            rows.append(tuple(int(part) for part in item))
        except (TypeError, ValueError):
            continue
    return tuple(rows)


def _tuple_tuple_str_int(value: Any) -> tuple[tuple[str, str, int], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    rows: list[tuple[str, str, int]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            continue
        name, expression, priority = item
        if not isinstance(name, str) or not isinstance(expression, str):
            continue
        try:
            rows.append((name, expression, int(priority)))
        except (TypeError, ValueError):
            continue
    return tuple(rows)


def _coerce_field_transform_stage(value: Any) -> FieldTransformStage | None:
    if not isinstance(value, dict):
        return None
    kind = str(value.get("kind", "")).strip()
    if not kind:
        return None
    try:
        window = int(value.get("window", 0) or 0)
    except (TypeError, ValueError):
        window = 0
    std_value = value.get("std")
    try:
        std = float(std_value) if std_value is not None else None
    except (TypeError, ValueError):
        std = None
    return FieldTransformStage(kind=kind, window=window, std=std)


def _coerce_field_transform_spec(value: Any) -> FieldTransformSpec | None:
    if not isinstance(value, dict):
        return None
    stages_raw = value.get("stages", ())
    stages: list[FieldTransformStage] = []
    if isinstance(stages_raw, (list, tuple)):
        for item in stages_raw:
            stage = _coerce_field_transform_stage(item)
            if stage is not None:
                stages.append(stage)
    try:
        backfill_window = int(value.get("backfill_window", 0) or 0)
    except (TypeError, ValueError):
        backfill_window = 0
    winsorize_value = value.get("winsorize_std")
    try:
        winsorize_std = float(winsorize_value) if winsorize_value is not None else None
    except (TypeError, ValueError):
        winsorize_std = None
    return FieldTransformSpec(
        stages=tuple(stages),
        backfill_window=backfill_window,
        winsorize_std=winsorize_std,
    )


def _coerce_feedback_phase_policy(value: Any) -> FeedbackPhasePolicy | None:
    if not isinstance(value, dict):
        return None
    preferred_raw = value.get("preferred_template_stages", ())
    preferred_template_stages = ()
    if isinstance(preferred_raw, (list, tuple)):
        preferred_template_stages = tuple(str(item) for item in preferred_raw if str(item).strip())
    try:
        min_attempted_templates = int(value.get("min_attempted_templates", 0) or 0)
    except (TypeError, ValueError):
        min_attempted_templates = 0
    try:
        min_best_score = float(value.get("min_best_score", STATS_DEFAULT_SCORE))
    except (TypeError, ValueError):
        min_best_score = STATS_DEFAULT_SCORE
    try:
        settings_variant_budget = int(value.get("settings_variant_budget", DEFAULT_SETTINGS_VARIANT_BUDGET) or DEFAULT_SETTINGS_VARIANT_BUDGET)
    except (TypeError, ValueError):
        settings_variant_budget = DEFAULT_SETTINGS_VARIANT_BUDGET
    return FeedbackPhasePolicy(
        min_attempted_templates=min_attempted_templates,
        min_best_score=min_best_score,
        settings_variant_budget=settings_variant_budget,
        enable_template_pruning=bool(value.get("enable_template_pruning", False)),
        enable_resimulation_mutations=bool(value.get("enable_resimulation_mutations", False)),
        preferred_template_stages=preferred_template_stages,
    )


def _coerce_feedback_loop_policy(value: Any) -> FeedbackLoopPolicy | None:
    if not isinstance(value, dict):
        return None
    generate = _coerce_feedback_phase_policy(value.get("generate"))
    prune = _coerce_feedback_phase_policy(value.get("prune"))
    resimulate = _coerce_feedback_phase_policy(value.get("resimulate"))
    if generate is None and prune is None and resimulate is None:
        return None
    return FeedbackLoopPolicy(
        generate=generate or FeedbackPhasePolicy(),
        prune=prune or FeedbackPhasePolicy(),
        resimulate=resimulate or FeedbackPhasePolicy(),
    )


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


def _resolve_priority_tiers(merged: ExpressionPolicyOverrides) -> dict[str, int]:
    """提取并解析 __default__.priority_tiers，供 @tier_name 引用使用。"""
    tiers_raw = merged.get("priority_tiers", {})
    if not isinstance(tiers_raw, dict):
        return {}
    resolved: dict[str, int] = {}
    for name, value in tiers_raw.items():
        try:
            resolved[str(name)] = int(value)
        except (TypeError, ValueError):
            continue
    return resolved


def _resolve_tier_value(raw_value: Any, tiers: dict[str, int]) -> int | None:
    """若值为 @tier_name 引用则解析为 int；否则直接返回 int / None。"""
    if isinstance(raw_value, str) and raw_value.startswith("@"):
        tier_name = raw_value[1:]
        return tiers.get(tier_name)
    if isinstance(raw_value, (int, float)):
        return int(raw_value)
    return None


def _coerce_template_prefix_penalties(
    value: Any,
    tiers: dict[str, int] | None = None,
) -> dict[tuple[str, ...], int]:
    """将 YAML 的 template_prefix_penalties 转换成语义统一的 dict[tuple[str,...], int]。

    支持两种 YAML 格式：
      1. dict 格式（推荐）："delta_|group_delta_|rank_delta_": "@deep_penalty"
      2. list[dict] 格式（旧）：- prefixes: [delta_, group_delta_] / penalty: -760

    key 中的 | 分隔符表示 "或" 语义，即任一前缀命中即应用该惩罚。
    """
    tiers = tiers or {}
    coerced_prefix_penalties: dict[tuple[str, ...], int] = {}
    if isinstance(value, dict):
        iterable = value.items()
    elif isinstance(value, (list, tuple)):
        # 旧格式兼容：list[dict] -> dict[tuple, int]
        iterable = (
            (item.get("prefixes", ()), item.get("penalty"))
            for item in value
            if isinstance(item, dict)
        )
    else:
        return coerced_prefix_penalties

    for prefixes, score in iterable:
        if isinstance(prefixes, str):
            parsed_prefixes = tuple(part.strip() for part in prefixes.split("|") if part.strip())
        elif isinstance(prefixes, (list, tuple)):
            parsed_prefixes = tuple(str(part).strip() for part in prefixes if str(part).strip())
        else:
            continue
        if not parsed_prefixes:
            continue
        resolved = _resolve_tier_value(score, tiers)
        if resolved is not None:
            coerced_prefix_penalties[parsed_prefixes] = resolved
    return coerced_prefix_penalties


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
    tiers = _resolve_priority_tiers(overrides)

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
                resolved = _resolve_tier_value(score, tiers)
                if resolved is not None:
                    coerced[name] = resolved
            update_map[key] = coerced
        elif key == "template_prefix_penalties":
            update_map[key] = _coerce_template_prefix_penalties(value, tiers=tiers)
        elif key in int_fields:
            resolved = _resolve_tier_value(value, tiers)
            if resolved is not None:
                update_map[key] = resolved
        elif key in tuple_pair_fields and isinstance(value, (list, tuple)):
            update_map[key] = {
                (str(item[0]), str(item[1]))
                for item in value
                if isinstance(item, (list, tuple)) and len(item) == 2
            }
        elif key in tuple_window3_fields:
            update_map[key] = _tuple_tuple_int(value, 3)
        elif key in tuple_window2_fields:
            update_map[key] = _tuple_tuple_int(value, 2)
        elif key in template_spec_fields:
            update_map[key] = _tuple_tuple_str_int(value)
        elif key in transform_fields:
            transform = _coerce_field_transform_spec(value)
            if transform is not None:
                update_map[key] = transform
        elif key == "feedback_loop_policy":
            loop_policy = _coerce_feedback_loop_policy(value)
            if loop_policy is not None:
                update_map[key] = loop_policy
        else:
            update_map[key] = value

    return replace(policy, **update_map)
