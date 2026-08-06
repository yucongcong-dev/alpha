"""Read-only template statistics report builder."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..generators.templates.metadata import (
    normalize_activation_scope,
    normalize_template_role,
)


def _count_mapping(data: object) -> dict[str, int]:
    if not isinstance(data, Mapping):
        return {}
    return {str(key): int(value or 0) for key, value in data.items()}


def compile_template_registry_summary(
    template_stats: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build a sorted, JSON-ready report without execution recommendations."""
    rows = [
        {
            "template_name": template_name,
            "template_family": str(stat.get("template_family", "") or ""),
            "template_stage": str(stat.get("template_stage", "") or ""),
            "template_role": normalize_template_role(stat.get("template_role")),
            "activation_scope": normalize_activation_scope(stat.get("template_activation_scope")),
            "attempted": int(stat.get("attempted", 0) or 0),
            "simulated": int(stat.get("simulated", 0) or 0),
            "submittable": int(stat.get("submittable", 0) or 0),
            "errors": int(stat.get("errors", 0) or 0),
            "queue_timeouts": int(stat.get("queue_timeouts", 0) or 0),
            "low_sharpe": int(stat.get("low_sharpe", 0) or 0),
            "low_fitness": int(stat.get("low_fitness", 0) or 0),
            "concentrated_weight": int(stat.get("concentrated_weight", 0) or 0),
            "role_counts": _count_mapping(stat.get("role_counts")),
            "scope_counts": _count_mapping(stat.get("scope_counts")),
        }
        for template_name, stat in template_stats.items()
    ]
    return sorted(
        rows,
        key=lambda row: (
            -row["submittable"],
            -row["simulated"],
            -row["attempted"],
            row["template_name"],
        ),
    )


__all__ = ["compile_template_registry_summary"]
