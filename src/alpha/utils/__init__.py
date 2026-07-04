"""
工具函数包

提供不依赖业务逻辑的通用工具函数。
"""

from __future__ import annotations

from .helpers import first_non_empty, is_event_field_name

__all__ = [
    "first_non_empty",
    "is_event_field_name",
]