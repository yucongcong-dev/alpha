"""
配置层类型定义。

从纯 dict[str, Any] 别名升级为 TypedDict + 明确语义类型，
提供更好的 IDE 自动补全和类型检查。
"""

from __future__ import annotations

from typing import Any, TypedDict

YamlConfig = dict[str, Any]
"""完整合并 YAML 配置（dict 提供灵活的键名访问）。"""


class DatasetProfile(TypedDict, total=False):
    """单个数据集的运行参数 profile。"""

    default_preset: str
    paused: bool
    page_size: int
    min_request_interval: float
    sleep_between_fields: float
    max_concurrent_simulations: int
    max_concurrent_creates: int
    max_templates_per_field: int
    field_template_batch_size: int
    simulation_max_wait_seconds: float
    simulation_max_queue_seconds: float
    queue_busy_cooldown_seconds: float


class ExpressionPolicyOverrides(TypedDict, total=False):
    """expression_policies 段中单个数据集的覆盖配置。"""

    use_curated_heuristics: bool
    closed_default_template_library: bool
    partner_limit: int
    positive_raw_fields: list[str]
    negative_raw_fields: list[str]
    template_priority_penalties: dict[str, int]
