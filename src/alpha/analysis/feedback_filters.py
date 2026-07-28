"""Compatibility wrapper for selection feedback policies."""

from ..selection.feedback_filters import (
    is_legacy_family_disabled,
    is_template_disabled,
    should_keep_template_for_feedback,
    should_skip_field_template_family,
)

__all__ = [
    "is_legacy_family_disabled",
    "is_template_disabled",
    "should_keep_template_for_feedback",
    "should_skip_field_template_family",
]
