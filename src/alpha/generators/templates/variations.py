"""Compatibility facade for explicit template wrappers."""

from __future__ import annotations

from .wrappers import (
    build_bucket_group_templates,
    build_trade_when_templates,
    invert_expression,
)

__all__ = [
    "build_bucket_group_templates",
    "build_trade_when_templates",
    "invert_expression",
]
