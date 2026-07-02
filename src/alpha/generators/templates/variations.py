"""Compatibility facade for template variation strategies."""

from __future__ import annotations

from .feedback_mutations import build_feedback_mutations
from .historical_reuse import build_historical_reuse_templates
from .wrappers import (
    build_bucket_group_templates,
    build_trade_when_templates,
    invert_expression,
)

__all__ = [
    "build_bucket_group_templates",
    "build_feedback_mutations",
    "build_historical_reuse_templates",
    "build_trade_when_templates",
    "invert_expression",
]
