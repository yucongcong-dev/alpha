"""Compatibility exports for template planning helpers."""

from __future__ import annotations

from .template_planning import (
    build_pending_template_variants,
    resolve_field_template_candidates,
)

__all__ = [
    "build_pending_template_variants",
    "resolve_field_template_candidates",
]
