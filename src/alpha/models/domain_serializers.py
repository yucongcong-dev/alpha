"""Serializers for domain dataclasses.

These helpers keep JSON/persistence shape decisions outside the core domain
objects while preserving backward-compatible instance methods.
"""

from __future__ import annotations

from .domain_conversion import serialize_failed_check
from .domain_types import ResultRow


def serialize_template_library_item(item: "TemplateLibraryItem") -> dict[str, object]:
    """Serialize a template-library item into its JSON shape."""
    return {
        "name": item.name,
        "expression": item.expression,
        "priority": item.priority,
        "family": item.family,
        "stage": item.stage,
        "metadata": item.metadata,
    }


def serialize_settings_variant(settings: "SettingsVariant") -> dict[str, object]:
    """Serialize a settings variant, omitting unset values."""
    serialized: dict[str, object] = {}
    key_map = {
        "instrument_type": "instrumentType",
        "unit_handling": "unitHandling",
        "nan_handling": "nanHandling",
        "max_trade": "maxTrade",
        "start_date": "startDate",
        "end_date": "endDate",
    }
    for key, value in settings.__dict__.items():
        if value is None:
            continue
        serialized[key_map.get(key, key)] = value
    return serialized


def serialize_template_field(field: "TemplateField") -> dict[str, object]:
    """Serialize a template field while preserving the original metadata payload."""
    return dict(field.metadata)


def serialize_field_test_result(result: "FieldTestResult") -> ResultRow:
    """Serialize a field test result into its persisted JSON row shape."""
    return {
        "field_id": result.field_id,
        "field_type": result.field_type,
        "field_name": result.field_name,
        "template_name": result.template_name,
        "template_family": result.template_family,
        "template_stage": result.template_stage,
        "template_role": result.template_role,
        "template_activation_scope": result.template_activation_scope,
        "simulation_id": result.simulation_id,
        "alpha_id": result.alpha_id,
        "status": result.status,
        "submittable": result.submittable,
        "submitted": result.submitted,
        "message": result.message,
        "expression": result.expression,
        "settings_fingerprint": result.settings_fingerprint,
        "template_library_fingerprint": result.template_library_fingerprint,
        "failed_stage": result.failed_stage,
        "failed_checks": [serialize_failed_check(check) for check in result.failed_checks]
        if result.failed_checks
        else None,
    }
