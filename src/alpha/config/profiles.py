"""
数据集运行参数 profiles。

本模块维护 dataset_profiles 的代码 fallback；数据集专属配置仍以
config/dataset_profiles.yaml 或 config/settings.yaml 的 dataset_profiles 段为推荐来源。
"""

from __future__ import annotations

from typing import cast

from .constants import (
    DEFAULT_FIELD_TEMPLATE_BATCH_SIZE,
    DEFAULT_MAX_CONCURRENT_CREATES,
    DEFAULT_MAX_CONCURRENT_SIMULATIONS,
    DEFAULT_MAX_TEMPLATES_PER_FIELD,
    DEFAULT_MIN_REQUEST_INTERVAL,
    DEFAULT_QUEUE_BUSY_COOLDOWN_SECONDS,
    DEFAULT_SIMULATION_MAX_QUEUE_SECONDS,
    DEFAULT_SIMULATION_MAX_WAIT_SECONDS,
    DEFAULT_SLEEP_BETWEEN_FIELDS,
    DEFAULT_TEMPLATE_DISABLE_AFTER,
)
from .types import DatasetProfile, YamlConfig

DATASET_PROFILES: dict[str, DatasetProfile] = {}
"""向后兼容保留的空字典；数据集专属配置请维护在 config/*.yaml。"""

DEFAULT_PROFILE: DatasetProfile = {
    "min_request_interval": DEFAULT_MIN_REQUEST_INTERVAL,
    "sleep_between_fields": DEFAULT_SLEEP_BETWEEN_FIELDS,
    "max_concurrent_simulations": DEFAULT_MAX_CONCURRENT_SIMULATIONS,
    "max_concurrent_creates": DEFAULT_MAX_CONCURRENT_CREATES,
    "max_templates_per_field": DEFAULT_MAX_TEMPLATES_PER_FIELD,
    "field_template_batch_size": DEFAULT_FIELD_TEMPLATE_BATCH_SIZE,
    "simulation_max_wait_seconds": DEFAULT_SIMULATION_MAX_WAIT_SECONDS,
    "simulation_max_queue_seconds": DEFAULT_SIMULATION_MAX_QUEUE_SECONDS,
    "queue_busy_cooldown_seconds": DEFAULT_QUEUE_BUSY_COOLDOWN_SECONDS,
    "template_disable_after": DEFAULT_TEMPLATE_DISABLE_AFTER,
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
