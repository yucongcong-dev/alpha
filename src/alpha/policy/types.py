"""
策略层动态结构别名。

本模块集中声明黑名单策略链路中高频使用的 payload / cache /
runtime summary 结构，避免在多个 policy 模块里重复书写
`dict[str, Any]`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BlacklistPayload = dict[str, Any]
"""黑名单文件的完整 JSON payload。"""

BlacklistMatcherEntry = dict[str, str]
"""用于名称 / stage / family 命中的轻量匹配记录。"""

BlacklistPatternRule = dict[str, str]
"""表达式自动规避规则。"""

BlacklistCacheEntry = dict[str, Any]
"""单个数据集的黑名单缓存项。"""

DefaultAvoidRulesCache = dict[str, Any]
"""跨数据集默认规避规则缓存项。"""


@dataclass
class BlacklistRuntimeSummary:
    """单个模板在运行期聚合出的黑名单统计摘要。"""

    template_name: str
    field_type: str = ""
    template_family: str = ""
    template_stage: str = ""
    fields_tested: list[str] = field(default_factory=list)
    _field_names_seen: set[str] = field(default_factory=set)
    submittable: int = 0
    low_sharpe: int = 0
    low_fitness: int = 0
    concentrated_weight: int = 0
    sharpe_sum: float = 0.0
    sharpe_count: int = 0
    fitness_sum: float = 0.0
    fitness_count: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        """兼容 dict 风格的 get 方法。"""
        return getattr(self, key, default)


BlacklistRuntimeStats = dict[str, BlacklistRuntimeSummary]
"""按模板名聚合的运行期黑名单统计。"""


@dataclass
class BlacklistTemplateEntry:
    """单条 blacklisted_templates 记录。"""

    name: str
    dataset_id: str
    source: str = "auto_detected"
    field_type: str = ""
    template_family: str = ""
    template_stage: str = ""
    reason: str = ""
    fields_tested: list[str] = field(default_factory=list)
    low_sharpe: int = 0
    low_fitness: int = 0
    date_blacklisted: str = ""
    avg_sharpe: float | None = None
    avg_fitness: float | None = None
    concentrated_weight: int | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """兼容 dict 风格的 get 方法。"""
        return getattr(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典表示，用于 JSON 序列化。"""
        result = {
            "name": self.name,
            "dataset_id": self.dataset_id,
            "source": self.source,
            "field_type": self.field_type,
            "template_family": self.template_family,
            "template_stage": self.template_stage,
            "reason": self.reason,
            "fields_tested": self.fields_tested,
            "low_sharpe": self.low_sharpe,
            "low_fitness": self.low_fitness,
            "date_blacklisted": self.date_blacklisted,
        }
        if self.avg_sharpe is not None:
            result["avg_sharpe"] = self.avg_sharpe
        if self.avg_fitness is not None:
            result["avg_fitness"] = self.avg_fitness
        if self.concentrated_weight is not None:
            result["concentrated_weight"] = self.concentrated_weight
        return result
