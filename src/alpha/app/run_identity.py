"""Stable identity construction for one resolved research run."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..config.models import DatasetExpressionPolicy
from ..generators.fingerprint import stable_fingerprint
from ..models.domain import TemplateField, TemplateLibrary
from ..models.domain_serializers import serialize_template_field
from ..models.io_types import RunFilters
from ..models.runtime_protocols import RunConfig
from ..policy.types import BlacklistPayload

GENERATOR_BEHAVIOR_VERSION = 1


def _research_config(run_config: RunConfig) -> dict[str, Any]:
    """Discard filesystem and presentation settings that do not change research output."""
    identity_config = {
        key: run_config.get(key, {})
        for key in (
            "dataset",
            "settings",
            "limits",
            "concurrency",
            "retries",
            "quality",
            "runtime",
            "heuristic_policy",
        )
    }
    runtime_payload = identity_config.get("runtime")
    runtime = dict(runtime_payload) if isinstance(runtime_payload, dict) else {}
    for key in ("verbose", "quiet", "dry_run_plan"):
        runtime.pop(key, None)
    identity_config["runtime"] = runtime
    filters = run_config.get("filters", {})
    identity_config["filters"] = {
        "top_fields_by_feedback": filters.get("top_fields_by_feedback")
        if isinstance(filters, dict)
        else None
    }
    return identity_config


def _resolved_filters(filters: RunFilters) -> dict[str, object]:
    return {
        "region": sorted(filters.region_filter or []),
        "delay": sorted(filters.delay_filter or []),
        "include_fields": sorted(filters.include_fields),
        "exclude_fields": sorted(filters.exclude_fields),
        "include_templates": sorted(filters.include_templates),
        "exclude_templates": sorted(filters.exclude_templates),
    }


def _research_blacklist(payload: BlacklistPayload) -> dict[str, object]:
    """Ignore bookkeeping timestamps and comments while retaining active rules."""
    return {
        key: value
        for key, value in payload.items()
        if key not in {"_comment", "_created", "_updated"}
    }


def build_research_run_fingerprint(
    *,
    run_config: RunConfig,
    template_library: TemplateLibrary,
    filters: RunFilters,
    expression_policy: DatasetExpressionPolicy,
    blacklist_payload: BlacklistPayload,
    fields: list[TemplateField],
) -> str:
    """Fingerprint all resolved inputs that affect candidate generation and ordering."""
    payload = {
        "generator_behavior_version": GENERATOR_BEHAVIOR_VERSION,
        "config": _research_config(run_config),
        "template_library": template_library,
        "filters": _resolved_filters(filters),
        "expression_policy": asdict(expression_policy),
        "blacklist": _research_blacklist(blacklist_payload),
        "fields": [serialize_template_field(field) for field in fields],
    }
    return stable_fingerprint(payload)
