"""Resume-index and field-position helpers for the run loop."""

from __future__ import annotations

from .config.constants import SENTINEL_UNKNOWN
from .models.runtime import TemplateField
from .utils.helpers import first_non_empty


def build_field_resume_positions(fields: list[TemplateField]) -> dict[str, int]:
    """Build stable original-order resume positions for each field id."""
    return {
        str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)): (index + 1)
        for index, field in enumerate(fields)
    }


def clamp_resume_index(resume_index: int, total_fields: int) -> int:
    """Clamp resume index into the current field range while preserving terminal completion."""
    if total_fields <= 0:
        return 0
    return max(0, min(resume_index, total_fields))


def normalize_resume_index(resume_index: int, total_fields: int) -> int:
    """Normalize resume index modulo current field count for legacy callers."""
    if total_fields <= 0:
        return 0
    return resume_index % total_fields
