"""
配置层类型定义。

从纯 dict[str, Any] 别名升级为 TypedDict + 明确语义类型，
提供更好的 IDE 自动补全和类型检查。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, TypedDict


class ConfigSource(Enum):
    """配置来源枚举"""
    CODE_CONSTANTS = "code_constants"           # 代码常量 (最低优先级)
    CONSTANTS_DEFAULTS = "constants_defaults"   # 代码级默认值
    TEMPLATES = "templates"                     # 模板默认值
    QUALITY_FEEDBACK = "quality_feedback"       # 质量反馈默认值
    DATASET_PROFILES = "dataset_profiles"       # 数据集profile
    EXPRESSION_POLICIES = "expression_policies" # 数据集策略
    SETTINGS = "settings"                       # 主配置文件
    CUSTOM_CONFIG = "custom_config"            # 自定义配置文件
    RUNTIME_OVERRIDE = "runtime_override"      # 运行时覆盖
    COMMAND_LINE = "command_line"               # 命令行参数 (最高优先级)

    @classmethod
    def from_yaml_name(cls, name: str) -> Optional[ConfigSource]:
        """从YAML文件名转换为ConfigSource"""
        mapping = {
            "constants_defaults": cls.CONSTANTS_DEFAULTS,
            "template_defaults": cls.TEMPLATES,
            "quality_feedback_defaults": cls.QUALITY_FEEDBACK,
            "dataset_profiles": cls.DATASET_PROFILES,
            "expression_policies": cls.EXPRESSION_POLICIES,
            "settings": cls.SETTINGS,
        }
        return mapping.get(name)

    @property
    def priority(self) -> int:
        """获取配置源优先级（数值越大优先级越高）"""
        priority_map = {
            self.CODE_CONSTANTS: 10,
            self.CONSTANTS_DEFAULTS: 20,
            self.TEMPLATES: 30,
            self.QUALITY_FEEDBACK: 40,
            self.DATASET_PROFILES: 50,
            self.EXPRESSION_POLICIES: 60,
            self.SETTINGS: 70,
            self.CUSTOM_CONFIG: 80,
            self.RUNTIME_OVERRIDE: 90,
            self.COMMAND_LINE: 100,
        }
        return priority_map[self]


class YamlConfig(TypedDict, total=False):
    """完整合并 YAML 配置（TypedDict 提供键名自动补全）。"""
    global_: ConfigSection  # type: ignore[name-defined]  # 对应合并 YAML global 段
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
YamlConfigCacheEntry = dict[str, Any]
