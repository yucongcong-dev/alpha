"""Compatibility exports for template planning helpers.

.. deprecated:: 1.0.0
    This module is a compatibility facade. Import from ``alpha.core.template_planning`` instead.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "alpha.core.template_queue is deprecated. Import from alpha.core.template_planning instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .template_planning import (
    build_pending_template_variants,
    resolve_field_template_candidates,
)

__all__ = [
    "build_pending_template_variants",
    "resolve_field_template_candidates",
]
