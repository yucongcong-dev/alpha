"""
Alpha 生成器包

负责 Alpha 表达式的生成、模板管理、字段管理和参数配置。

子模块：
    - templates: 模板库管理
    - expressions: 表达式构建与家族分类
    - fields: 字段缓存与配对发现
    - fingerprint: 稳定指纹生成
    - payload: 模拟请求体构建
    - variants: settings 变体构建
    - settings: 兼容导出层
"""

from __future__ import annotations
