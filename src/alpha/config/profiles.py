"""
数据集运行参数 profiles。

本模块维护 dataset_profiles 的代码 fallback；数据集专属配置仍以
settings.yaml 的 dataset_profiles 段为唯一推荐来源。
"""

from __future__ import annotations

from typing import Any

DATASET_PROFILES: dict[str, dict[str, Any]] = {}
"""向后兼容保留的空字典；数据集专属配置请维护在 settings.yaml。"""

DEFAULT_PROFILE: dict[str, Any] = {
    "min_request_interval": 2.0,
    "sleep_between_fields": 5.0,
    "max_concurrent_simulations": 1,
    "max_concurrent_creates": 1,
    "max_templates_per_field": 12,
    "field_template_batch_size": 2,
    "simulation_max_wait_seconds": 900,
    "simulation_max_queue_seconds": 600,
    "queue_busy_cooldown_seconds": 120,
    "template_disable_after": 12,
}
"""未在 YAML dataset_profiles 中匹配时使用的默认运行参数。"""


def get_dataset_profile(dataset_id: str, yaml_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """返回指定数据集的运行参数配置。"""
    profile = dict(DEFAULT_PROFILE)
    if yaml_config:
        yaml_profiles = yaml_config.get("dataset_profiles", {})
        if isinstance(yaml_profiles, dict):
            yaml_profile = yaml_profiles.get(dataset_id)
            if isinstance(yaml_profile, dict):
                profile.update(yaml_profile)
    return profile
