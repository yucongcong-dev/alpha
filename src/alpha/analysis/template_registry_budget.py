"""Template registry settings-budget helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..config.constants import FEEDBACK_STAGE_GENERATE, FEEDBACK_STAGE_RESIMULATE
from .template_registry_rules import normalize_activation_scope, normalize_template_role


def choose_registry_settings_budget(
    base_budget: int,
    recommendation: Mapping[str, Any],
    *,
    feedback_stage: str = FEEDBACK_STAGE_GENERATE,
) -> int:
    """Adjust settings-variant budget using registry recommendation."""
    budget = max(1, int(base_budget or 1))
    recommended_scope = normalize_activation_scope(recommendation.get("recommended_scope"))
    recommended_role = normalize_template_role(recommendation.get("recommended_role"))
    should_suppress = bool(recommendation.get("should_suppress", False))

    if should_suppress and feedback_stage == FEEDBACK_STAGE_GENERATE:
        return 0
    if recommended_role == "promoted_core" or recommended_scope == "broad":
        return budget + 1
    if recommended_scope == "refine":
        if feedback_stage == FEEDBACK_STAGE_RESIMULATE:
            return budget + 1
        return min(budget, 1)
    if recommended_scope == "diagnostic":
        if feedback_stage == FEEDBACK_STAGE_GENERATE:
            return 0
        return 1
    return budget


def choose_family_settings_budget(
    base_budget: int,
    template_family: str,
    family_registry: Mapping[str, Mapping[str, Any]],
    *,
    feedback_stage: str = FEEDBACK_STAGE_GENERATE,
) -> int:
    """Adjust settings budget using family-level historical strength."""
    budget = max(0, int(base_budget or 0))
    family_key = str(template_family or "").strip().lower()
    if not family_key or family_key not in family_registry:
        return budget
    family_row = family_registry[family_key]
    recommended_scope = normalize_activation_scope(family_row.get("recommended_scope"))
    adjustment = int(family_row.get("budget_adjustment", 0) or 0)
    if recommended_scope == "diagnostic" and feedback_stage == FEEDBACK_STAGE_GENERATE:
        return 0
    if recommended_scope == "broad":
        return max(1, budget + max(0, adjustment))
    if recommended_scope == "refine" and feedback_stage == FEEDBACK_STAGE_GENERATE:
        return max(1, budget)
    return max(1, budget + adjustment)


def choose_field_cluster_settings_budget(
    base_budget: int,
    field_tags: object,
    overrides: Mapping[str, Any],
    *,
    feedback_stage: str = FEEDBACK_STAGE_GENERATE,
) -> int:
    """Adjust budget using field-cluster tags and optional manual overrides."""
    budget = max(0, int(base_budget or 0))
    tags = [str(tag).strip().lower() for tag in field_tags or [] if str(tag).strip()]
    if not tags:
        return budget
    cluster_overrides = overrides.get("field_cluster_overrides", {})
    if not isinstance(cluster_overrides, Mapping):
        cluster_overrides = {}
    for tag in tags:
        if tag == "high_coverage":
            budget += 1
        elif tag == "sparse_coverage":
            budget = max(1, budget - 1)
        override = cluster_overrides.get(tag)
        if isinstance(override, Mapping):
            recommended_scope = normalize_activation_scope(override.get("recommended_scope"))
            adjustment = int(override.get("budget_adjustment", 0) or 0)
            if recommended_scope == "diagnostic" and feedback_stage == FEEDBACK_STAGE_GENERATE:
                return 0
            budget += adjustment
    return max(0, budget)


__all__ = [
    "choose_family_settings_budget",
    "choose_field_cluster_settings_budget",
    "choose_registry_settings_budget",
]
