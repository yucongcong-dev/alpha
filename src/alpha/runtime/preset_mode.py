"""Helpers for detecting explicit, closed preset runs."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path


def is_explicit_template_preset(template_library_file: str) -> bool:
    """Return whether a template library lives under a dataset presets directory."""
    if not template_library_file:
        return False
    parts = {part.strip().lower() for part in Path(template_library_file).parts}
    return "presets" in parts


def resolve_preset_mode(
    *,
    template_library_file: str = "",
    include_fields_file: str = "",
    include_templates_file: str = "",
    include_fields: Collection[str] | None = None,
    include_templates: Collection[str] | None = None,
) -> bool:
    """Detect runs that should treat user-provided fields/templates as closed sets."""
    return bool(
        is_explicit_template_preset(template_library_file)
        or include_fields_file
        or include_templates_file
        or include_fields
        or include_templates
    )
