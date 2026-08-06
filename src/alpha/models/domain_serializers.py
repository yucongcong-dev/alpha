"""Serializers for domain dataclasses.

These helpers keep JSON/persistence shape decisions outside the core domain
objects while preserving backward-compatible instance methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .domain_codecs import (
    serialize_field_test_result as _serialize_field_test_result,
)
from .domain_codecs import (
    serialize_settings_variant as _serialize_settings_variant,
)
from .domain_codecs import (
    serialize_template_field as _serialize_template_field,
)
from .domain_codecs import (
    serialize_template_library_item as _serialize_template_library_item,
)
from .domain_types import ResultRow

if TYPE_CHECKING:
    from .domain import FieldTestResult, SettingsVariant, TemplateField, TemplateLibraryItem


def serialize_template_library_item(item: TemplateLibraryItem) -> dict[str, object]:
    """Serialize a template-library item into its JSON shape."""
    return _serialize_template_library_item(item)


def serialize_settings_variant(settings: SettingsVariant) -> dict[str, object]:
    """Serialize a settings variant, omitting unset values."""
    return _serialize_settings_variant(settings)


def serialize_template_field(field: TemplateField) -> dict[str, object]:
    """Serialize a template field without losing its canonical identity attributes."""
    return _serialize_template_field(field)


def serialize_field_test_result(result: FieldTestResult) -> ResultRow:
    """Serialize a field test result into its persisted JSON row shape."""
    return _serialize_field_test_result(result)
