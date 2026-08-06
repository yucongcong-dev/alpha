"""
策略层动态结构别名。

本模块集中声明黑名单策略链路中高频使用的 payload / cache 结构，
避免在多个 policy 模块里重复书写 `dict[str, Any]`。
"""

from __future__ import annotations

from typing import Any, Protocol

LEARNED_BLACKLIST_KEY = "learned_templates"
PATTERN_RULES_KEY = "expression_rules"

BlacklistPayload = dict[str, Any]
"""黑名单文件的完整 JSON payload。"""

BlacklistMatcherEntry = dict[str, str]
"""用于名称 / stage / family 命中的轻量匹配记录。"""

BlacklistPatternRule = dict[str, str]
"""模板名称或表达式的人工规避规则。"""

BlacklistCacheEntry = dict[str, Any]
"""单个数据集的黑名单缓存项。"""


class BlacklistRuntimePolicy(Protocol):
    """黑名单判断所需的最小运行时策略视图。"""

    @property
    def dataset_id(self) -> str: ...

    @property
    def protected_templates(self) -> set[str]: ...
