"""Template registry persistence and override helpers."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from typing import Any

from ..io.output_paths import build_output_sidecar_paths

DEFAULT_OVERRIDE_PAYLOAD = {
    "template_overrides": {},
    "family_overrides": {},
    "field_cluster_overrides": {},
}


def load_persisted_template_registry(output_path: str) -> list[dict[str, Any]]:
    """Load persisted template-registry sidecar rows when available."""
    if not output_path:
        return []
    registry_path = build_output_sidecar_paths(output_path)["template_registry"]
    if not os.path.exists(registry_path):
        return []
    try:
        with open(registry_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def load_registry_overrides(output_path: str) -> dict[str, Any]:
    """Load optional manual override control surface."""
    if not output_path:
        return dict(DEFAULT_OVERRIDE_PAYLOAD)
    override_path = build_output_sidecar_paths(output_path)["template_registry_overrides"]
    if not os.path.exists(override_path):
        return dict(DEFAULT_OVERRIDE_PAYLOAD)
    try:
        with open(override_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return dict(DEFAULT_OVERRIDE_PAYLOAD)
    if not isinstance(payload, dict):
        return dict(DEFAULT_OVERRIDE_PAYLOAD)
    normalized = dict(DEFAULT_OVERRIDE_PAYLOAD)
    for key in normalized:
        value = payload.get(key, {})
        normalized[key] = value if isinstance(value, dict) else {}
    return normalized


def build_template_registry_index(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build fast lookup index from persisted registry rows."""
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        template_name = str(row.get("template_name", "") or "")
        if not template_name:
            continue
        indexed[template_name] = dict(row)
    return indexed


def resolve_registry_override(
    overrides: Mapping[str, Any],
    *,
    template_name: str = "",
    template_family: str = "",
) -> dict[str, Any]:
    """Resolve manual override with template-level precedence over family-level."""
    template_key = str(template_name or "").strip()
    family_key = str(template_family or "").strip().lower()
    resolved: dict[str, Any] = {}
    family_overrides = overrides.get("family_overrides", {})
    if isinstance(family_overrides, Mapping) and family_key and family_key in family_overrides:
        family_value = family_overrides[family_key]
        if isinstance(family_value, Mapping):
            resolved.update(dict(family_value))
    template_overrides = overrides.get("template_overrides", {})
    if isinstance(template_overrides, Mapping) and template_key and template_key in template_overrides:
        template_value = template_overrides[template_key]
        if isinstance(template_value, Mapping):
            resolved.update(dict(template_value))
    return resolved


__all__ = [
    "DEFAULT_OVERRIDE_PAYLOAD",
    "build_template_registry_index",
    "load_persisted_template_registry",
    "load_registry_overrides",
    "resolve_registry_override",
]
