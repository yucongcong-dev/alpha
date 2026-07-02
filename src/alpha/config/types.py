"""
配置层类型定义。

从纯 dict[str, Any] 别名升级为 TypedDict + 明确语义类型，
提供更好的 IDE 自动补全和类型检查。
"""

from __future__ import annotations

from typing import Any, TypedDict


class YamlConfig(TypedDict, total=False):
    """完整 settings.yaml 合并配置（TypedDict 提供键名自动补全）。"""
    global_: ConfigSection  # type: ignore[name-defined]  # 对应 settings.yaml global 段
    dataset_profiles: dict[str, DatasetProfile]  # type: ignore[name-defined]
    expression_policies: dict[str, ExpressionPolicyOverrides]  # type: ignore[name-defined]


class ConfigSection(TypedDict, total=False):
    """任意一级配置段。"""
    pass  # 字段由具体路径决定


class DatasetProfile(TypedDict, total=False):
    """单个数据集的运行参数 profile。"""
    min_request_interval: float
    sleep_between_fields: float
    max_concurrent_simulations: int
    max_concurrent_creates: int
    max_templates_per_field: int
    field_template_batch_size: int
    simulation_max_wait_seconds: int
    simulation_max_queue_seconds: int
    queue_busy_cooldown_seconds: int
    template_disable_after: int


class ExpressionPolicyOverrides(TypedDict, total=False):
    """expression_policies 段中单个数据集的覆盖配置。"""
    use_curated_heuristics: bool
    partner_limit: int
    positive_raw_fields: list[str]
    negative_raw_fields: list[str]
    disabled_templates: list[str]
    template_priority_penalties: dict[str, int]


# 保留旧式别名向后兼容
YamlConfigCacheEntry = dict[str, Any]  # noqa: invalid-name - backward-compat

