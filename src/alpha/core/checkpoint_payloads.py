"""Checkpoint payload serialization and restoration helpers."""

from __future__ import annotations

from typing import Any

from ..config.constants import SENTINEL_UNKNOWN
from ..runtime.contexts import PendingFutureContext
from ..runtime.state import ExecutionState

TEMPLATE_STAT_COUNT_FIELDS = (
    "attempted",
    "submittable",
    "submitted",
    "errors",
    "simulated",
    "queue_timeouts",
    "low_sharpe",
    "low_fitness",
    "concentrated_weight",
    "low_sub_universe_sharpe",
)


def non_negative_int(value: object) -> int | None:
    """Return a safe non-negative integer or None for unusable persisted values."""
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = int(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def restore_template_stats(payload: object) -> dict[str, dict[str, Any]]:
    """Restore template statistics with safe numeric counters."""
    if not isinstance(payload, dict):
        return {}
    restored: dict[str, dict[str, Any]] = {}
    for template_name, raw_stat in payload.items():
        normalized_name = str(template_name or "").strip()
        if not normalized_name or not isinstance(raw_stat, dict):
            continue
        stat = dict(raw_stat)
        for field_name in TEMPLATE_STAT_COUNT_FIELDS:
            stat[field_name] = non_negative_int(stat.get(field_name)) or 0
        restored[normalized_name] = stat
    return restored


def all_pending_contexts(execution_state: ExecutionState) -> list[PendingFutureContext]:
    """Return submitted and not-yet-resubmitted simulation contexts."""
    future_queue = execution_state.future_queue
    return [
        *future_queue.pending_futures.values(),
        *future_queue.resumable_simulations,
    ]


def serialize_pending_simulations(
    execution_state: ExecutionState,
) -> list[dict[str, Any]]:
    """Serialize inflight metadata required to resume remote simulation polling."""
    return [
        {
            "field_id": str(getattr(meta, "field_id", "") or ""),
            "field_name": str(getattr(meta, "field_name", "") or ""),
            "field_type": str(getattr(meta, "field_type", "") or ""),
            "template_name": str(getattr(meta, "template_name", "") or ""),
            "template_family": str(getattr(meta, "template_family", "") or ""),
            "template_stage": str(getattr(meta, "template_stage", "") or ""),
            "template_role": str(getattr(meta, "template_role", "") or ""),
            "template_activation_scope": str(getattr(meta, "template_activation_scope", "") or ""),
            "policy_version": str(getattr(meta, "policy_version", "") or ""),
            "expression": str(getattr(meta, "expression", "") or ""),
            "settings_fingerprint": str(getattr(meta, "settings_fingerprint", "") or ""),
            "settings": dict(getattr(meta, "settings", {}) or {}),
            "simulation_location": str(getattr(meta, "simulation_location", "") or ""),
            "simulation_id": str(getattr(meta, "simulation_id", "") or ""),
        }
        for meta in all_pending_contexts(execution_state)
    ]


def restore_pending_simulations(
    payload: object,
) -> tuple[list[PendingFutureContext], int]:
    """Restore resumable simulations and count entries that require recreation."""
    restored: list[PendingFutureContext] = []
    retry_from_start = 0
    if not isinstance(payload, list):
        return restored, retry_from_start
    for item in payload:
        if not isinstance(item, dict):
            continue
        field_id = str(item.get("field_id", "") or "").strip()
        template_name = str(item.get("template_name", "") or "").strip()
        expression = str(item.get("expression", "") or "").strip()
        settings_fingerprint = str(item.get("settings_fingerprint", "") or "").strip()
        if not field_id or not template_name or not expression or not settings_fingerprint:
            continue
        simulation_location = str(item.get("simulation_location", "") or "").strip()
        if not simulation_location:
            retry_from_start += 1
            continue
        simulation_id = str(item.get("simulation_id", "") or "").strip()
        if not simulation_id:
            simulation_id = simulation_location.rstrip("/").rsplit("/", 1)[-1]
        restored.append(
            PendingFutureContext(
                field_id=field_id,
                field_name=str(item.get("field_name", "") or field_id),
                field_type=str(item.get("field_type", "") or SENTINEL_UNKNOWN),
                template_name=template_name,
                template_family=str(item.get("template_family", "") or ""),
                template_stage=str(item.get("template_stage", "") or ""),
                template_role=str(item.get("template_role", "") or ""),
                template_activation_scope=str(item.get("template_activation_scope", "") or ""),
                policy_version=str(item.get("policy_version", "") or ""),
                expression=expression,
                settings_fingerprint=settings_fingerprint,
                settings=dict(item.get("settings", {}))
                if isinstance(item.get("settings"), dict)
                else {},
                simulation_location=simulation_location,
                simulation_id=simulation_id,
            )
        )
    return restored, retry_from_start
