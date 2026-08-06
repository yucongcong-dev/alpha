"""Pure JSON-shape codecs used by domain dataclasses and compatibility wrappers."""

from __future__ import annotations

from typing import Any

from .domain_types import ResultRow


def failed_check_values(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(data.get("name", "")),
        "value": data.get("value"),
        "limit": data.get("limit"),
        "result": data.get("result"),
    }


def template_library_item_values(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item["name"]),
        "expression": str(item["expression"]),
        "priority": int(item.get("priority", 0)),
        "family": item.get("family"),
        "stage": item.get("stage"),
        "metadata": item.get("metadata", {}),
    }


def settings_variant_values(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "decay": data.get("decay"),
        "neutralization": data.get("neutralization"),
        "truncation": data.get("truncation"),
        "pasteurization": data.get("pasteurization"),
        "unit_handling": data.get("unit_handling", data.get("unitHandling")),
        "nan_handling": data.get("nan_handling", data.get("nanHandling")),
        "max_trade": data.get("max_trade", data.get("maxTrade")),
        "language": data.get("language"),
        "instrument_type": data.get("instrument_type", data.get("instrumentType")),
        "region": data.get("region"),
        "universe": data.get("universe"),
        "delay": data.get("delay"),
        "start_date": data.get("start_date", data.get("startDate")),
        "end_date": data.get("end_date", data.get("endDate")),
        "visualization": data.get("visualization"),
    }


def template_field_values(field: dict[str, Any]) -> dict[str, Any]:
    if "field_id" in field and "metadata" in field and isinstance(field.get("metadata"), dict):
        return {
            "field_id": str(field.get("field_id", "")),
            "field_name": str(field.get("field_name", "")),
            "field_type": str(field.get("field_type", "UNKNOWN")).upper(),
            "metadata": dict(field["metadata"]),
        }
    return {
        "field_id": str(field.get("id") or field.get("name") or field.get("mnemonic") or ""),
        "field_name": str(field.get("name") or field.get("id") or field.get("mnemonic") or ""),
        "field_type": str(
            field.get("type") or field.get("fieldType") or field.get("category") or "UNKNOWN"
        ).upper(),
        "metadata": dict(field),
    }


def serialize_template_library_item(item: Any) -> dict[str, object]:
    return {
        "name": item.name,
        "expression": item.expression,
        "priority": item.priority,
        "family": item.family,
        "stage": item.stage,
        "metadata": item.metadata,
    }


def serialize_settings_variant(settings: Any) -> dict[str, object]:
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
        if value is not None:
            serialized[key_map.get(key, key)] = value
    return serialized


def serialize_template_field(field: Any) -> dict[str, object]:
    serialized: dict[str, object] = dict(field.metadata)
    serialized["id"] = field.field_id
    serialized["name"] = field.field_name
    serialized["type"] = field.field_type
    return serialized


def serialize_field_test_result(result: Any) -> ResultRow:
    failed_checks = result.failed_checks
    return {
        "field_id": result.field_id,
        "field_type": result.field_type,
        "field_name": result.field_name,
        "template_name": result.template_name,
        "template_family": result.template_family,
        "template_stage": result.template_stage,
        "template_role": result.template_role,
        "template_activation_scope": result.template_activation_scope,
        "policy_version": result.policy_version,
        "simulation_id": result.simulation_id,
        "alpha_id": result.alpha_id,
        "status": result.status,
        "submittable": result.submittable,
        "submitted": result.submitted,
        "message": result.message,
        "expression": result.expression,
        "settings_fingerprint": result.settings_fingerprint,
        "template_library_fingerprint": result.template_library_fingerprint,
        "settings": dict(result.settings),
        "metrics": dict(result.metrics),
        "region": result.region,
        "universe": result.universe,
        "instrument_type": result.instrument_type,
        "delay": result.delay,
        "run_name": result.run_name,
        "source_summary": result.source_summary,
        "created_at": result.created_at,
        "updated_at": result.updated_at,
        "revision": result.revision,
        "failed_stage": result.failed_stage,
        "failed_checks": [check.to_dict() for check in failed_checks] if failed_checks else None,
    }
