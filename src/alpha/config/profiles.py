"""
数据集运行参数 profiles。

本模块维护 dataset_profiles 的代码 fallback；数据集专属配置仍以
config/dataset_profiles.yaml 或 config/settings.yaml 的 dataset_profiles 段为推荐来源。
"""

from __future__ import annotations

from typing import cast

from .static_config import get_static_config
from .types import DatasetProfile, YamlConfig

DEFAULT_PROFILE: DatasetProfile = {
    "min_request_interval": get_static_config().default_min_request_interval,
    "sleep_between_fields": get_static_config().default_sleep_between_fields,
    "max_concurrent_simulations": get_static_config().default_max_concurrent_simulations,
    "max_concurrent_creates": get_static_config().default_max_concurrent_creates,
    "max_templates_per_field": get_static_config().default_max_templates_per_field,
    "field_template_batch_size": get_static_config().default_field_template_batch_size,
    "simulation_max_wait_seconds": get_static_config().default_simulation_max_wait_seconds,
    "simulation_max_queue_seconds": get_static_config().default_simulation_max_queue_seconds,
    "queue_busy_cooldown_seconds": get_static_config().default_queue_busy_cooldown_seconds,
}
"""未在 YAML dataset_profiles 中匹配时使用的默认运行参数。"""


def get_dataset_profile(
    dataset_id: str,
    yaml_config: YamlConfig | None = None,
) -> DatasetProfile:
    """返回指定数据集的运行参数配置。"""
    profile = dict(DEFAULT_PROFILE)
    if yaml_config:
        yaml_profiles = yaml_config.get("dataset_profiles", {})
        if isinstance(yaml_profiles, dict):
            yaml_profile = yaml_profiles.get(dataset_id)
            if isinstance(yaml_profile, dict):
                profile.update(yaml_profile)
    return cast(DatasetProfile, profile)
