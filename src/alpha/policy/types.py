"""
策略层动态结构别名。

本模块集中声明黑名单策略链路中高频使用的 payload / cache /
runtime summary 结构，避免在多个 policy 模块里重复书写
`dict[str, Any]`。
"""

from __future__ import annotations

from typing import Any

BlacklistPayload = dict[str, Any]
"""黑名单文件的完整 JSON payload。"""

BlacklistTemplateEntry = dict[str, Any]
"""单条 blacklisted_templates 记录。"""

BlacklistMatcherEntry = dict[str, str]
"""用于名称 / stage / family 命中的轻量匹配记录。"""

BlacklistPatternRule = dict[str, str]
"""表达式自动规避规则。"""

BlacklistRuntimeSummary = dict[str, Any]
"""单个模板在运行期聚合出的黑名单统计摘要。"""

BlacklistRuntimeStats = dict[str, BlacklistRuntimeSummary]
"""按模板名聚合的运行期黑名单统计。"""

BlacklistCacheEntry = dict[str, Any]
"""单个数据集的黑名单缓存项。"""

DefaultAvoidRulesCache = dict[str, Any]
"""跨数据集默认规避规则缓存项。"""
