"""
配置层动态结构别名。

集中声明 YAML 配置、dataset profile 和 expression policy override
等高动态结构，避免 `config/*` 多个模块重复书写宽类型。
"""

from __future__ import annotations

from typing import Any

YamlConfig = dict[str, Any]
"""完整 settings.yaml 配置。"""

ConfigSection = dict[str, Any]
"""任意一级配置段。"""

DatasetProfile = dict[str, Any]
"""单个数据集的运行参数 profile。"""

ExpressionPolicyOverrides = dict[str, Any]
"""expression_policies 合并后的 override 映射。"""

YamlConfigCacheEntry = dict[str, Any]
"""YAML 缓存项，包含 path / signature / data。"""
