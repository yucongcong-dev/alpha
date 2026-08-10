"""Stable identity construction for one resolved research run."""

from __future__ import annotations

from dataclasses import asdict
import json
import logging
import os
from typing import Any

from ..config.models import DatasetExpressionPolicy
from ..generators.fingerprint import stable_fingerprint
from ..models.domain import TemplateLibrary
from ..models.io_types import RunFilters
from ..models.runtime_protocols import RunConfig
from ..policy.types import BlacklistPayload

GENERATOR_BEHAVIOR_VERSION = 1
logger = logging.getLogger(__name__)


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
            "input_fingerprints",
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


def build_research_input_fingerprints(
    *,
    filters: RunFilters,
    expression_policy: DatasetExpressionPolicy,
    blacklist_payload: BlacklistPayload,
) -> dict[str, str]:
    """Build auditable fingerprints for mutable local research inputs."""
    return {
        "include_fields": stable_fingerprint(sorted(filters.include_fields)),
        "exclude_fields": stable_fingerprint(sorted(filters.exclude_fields)),
        "include_templates": stable_fingerprint(sorted(filters.include_templates)),
        "exclude_templates": stable_fingerprint(sorted(filters.exclude_templates)),
        "expression_policy": stable_fingerprint(asdict(expression_policy)),
        "blacklist": stable_fingerprint(_research_blacklist(blacklist_payload)),
    }


def build_research_run_fingerprint(
    *,
    run_config: RunConfig,
    template_library: TemplateLibrary,
    filters: RunFilters,
    expression_policy: DatasetExpressionPolicy,
    blacklist_payload: BlacklistPayload,
) -> str:
    """Fingerprint all resolved inputs that affect candidate generation and ordering."""
    payload = {
        "generator_behavior_version": GENERATOR_BEHAVIOR_VERSION,
        "config": _research_config(run_config),
        "template_library": template_library,
        "filters": _resolved_filters(filters),
        "expression_policy": asdict(expression_policy),
        "blacklist": _research_blacklist(blacklist_payload),
    }
    return stable_fingerprint(payload)


def validate_existing_run_identity(
    output_path: str,
    *,
    run_fingerprint: str,
    run_config: RunConfig,
    settings_fingerprint: str,
    template_library_fingerprint: str,
) -> None:
    """Reject reuse of a run output whose persisted research identity differs."""
    if not output_path or not os.path.exists(output_path):
        return
    with open(output_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return

    saved_fingerprint = str(payload.get("run_fingerprint", "") or "")
    if saved_fingerprint:
        if saved_fingerprint == run_fingerprint:
            return
        raise ValueError(
            f"run configuration changed for {output_path}; use a new --run-name "
            "instead of mixing results"
        )

    tested = int(payload.get("tested", 0) or 0)
    if tested <= 0:
        return
    saved_config = payload.get("run_config")
    legacy_identity_matches = (
        isinstance(saved_config, dict)
        and _research_config(saved_config) == _research_config(run_config)
        and str(payload.get("settings_fingerprint", "") or "") == settings_fingerprint
        and str(payload.get("template_library_fingerprint", "") or "")
        == template_library_fingerprint
    )
    if legacy_identity_matches:
        logger.warning(
            "[run] migrating legacy summary without run_fingerprint: %s",
            output_path,
        )
        return
    raise ValueError(
        f"existing results in {output_path} predate complete run identity metadata; "
        "use a new --run-name instead of mixing results"
    )
