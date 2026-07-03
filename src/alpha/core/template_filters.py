"""Compatibility exports for execution filter helpers.

.. deprecated:: 1.0.0
    This module is a compatibility facade. Import from ``alpha.core.execution_filters`` instead.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "alpha.core.template_filters is deprecated. Import from alpha.core.execution_filters instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .execution_filters import (
    is_template_actionable,
    should_skip_expression_by_history,
    should_skip_field,
)

__all__ = [
    "is_template_actionable",
    "should_skip_expression_by_history",
    "should_skip_field",
]
