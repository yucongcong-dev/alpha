"""Template registry recommendation and summary rules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..config.constants import FEEDBACK_STAGE_GENERATE, FEEDBACK_STAGE_RESIMULATE

_DEFAULT_ROLE = "default_seed"
_DEFAULT_SCOPE = "broad"

_PROMOTE_SUBMITTABLE_BONUS = 120
_PROMOTE_STABLE_SIM_BONUS = 45
_REFINE_FOCUS_BONUS = 20
_DIAGNOSTIC_DEMOTION_PENALTY = -120

_PROMOTE_MIN_SIMULATED = 3
_DEMOTE_MIN_ATTEMPTED = 6
_REFINE_MIN_ATTEMPTED = 4
_FAMILY_STRONG_SUBMITTABLE_BONUS = 1
_FAMILY_WEAK_MIN_ATTEMPTED = 8


def normalize_template_role(role: object) -> str:
    """Normalize template role into a stable lowercase string."""
    value = str(role or "").strip().lower()
    return value or _DEFAULT_ROLE


def normalize_activation_scope(scope: object) -> str:
    """Normalize activation scope and fall back to broad."""
    value = str(scope or "").strip().lower()
    if value in {"broad", "refine", "diagnostic"}:
        return value
    return _DEFAULT_SCOPE


def _count_mapping(data: object) -> dict[str, int]:
    """Coerce a role/scope counter payload into a string-int mapping."""
    if not isinstance(data, Mapping):
        return {}
    counts: dict[str, int] = {}
    for key, value in data.items():
        counts[str(key)] = int(value or 0)
    return counts


def _recommended_role_from_scope(scope: str) -> str:
    if scope == "diagnostic":
        return "diagnostic_probe"
    if scope == "refine":
        return "refine_neighbor"
    return "promoted_core"


def recommend_template_role_transition(
    template_name: str,
    template_stats: Mapping[str, Mapping[str, Any]],
    *,
    current_role: str = "",
    current_scope: str = "",
    feedback_stage: str = FEEDBACK_STAGE_GENERATE,
) -> dict[str, Any]:
    """Recommend whether a template should be promoted, refined, or demoted."""
    stat = template_stats.get(template_name)
    role = normalize_template_role(current_role)
    scope = normalize_activation_scope(current_scope)
    if not isinstance(stat, Mapping):
        return {
            "current_role": role,
            "current_scope": scope,
            "recommended_role": role,
            "recommended_scope": scope,
            "priority_adjustment": 0,
            "should_suppress": False,
            "reason": "insufficient_history",
        }

    attempted = int(stat.get("attempted", 0) or 0)
    submittable = int(stat.get("submittable", 0) or 0)
    simulated = int(stat.get("simulated", 0) or 0)
    errors = int(stat.get("errors", 0) or 0)
    low_sharpe = int(stat.get("low_sharpe", 0) or 0)
    low_fitness = int(stat.get("low_fitness", 0) or 0)
    concentrated = int(stat.get("concentrated_weight", 0) or 0)

    recommended_scope = scope
    recommended_role = role
    priority_adjustment = 0
    should_suppress = False
    reason = "preserve"

    if submittable > 0:
        recommended_scope = "broad"
        recommended_role = "promoted_core"
        priority_adjustment = _PROMOTE_SUBMITTABLE_BONUS
        reason = "submittable_history"
    elif (
        simulated >= _PROMOTE_MIN_SIMULATED
        and errors == 0
        and low_sharpe == 0
        and low_fitness == 0
        and concentrated == 0
    ):
        recommended_scope = "broad"
        recommended_role = "promoted_core"
        priority_adjustment = _PROMOTE_STABLE_SIM_BONUS
        reason = "stable_simulation_history"
    elif (
        attempted >= _DEMOTE_MIN_ATTEMPTED
        and submittable == 0
        and ((low_sharpe >= 3 and low_fitness >= 3) or concentrated >= 2)
    ):
        recommended_scope = "diagnostic"
        recommended_role = "diagnostic_probe"
        priority_adjustment = _DIAGNOSTIC_DEMOTION_PENALTY
        should_suppress = feedback_stage == FEEDBACK_STAGE_GENERATE
        reason = "persistent_failure_pattern"
    elif attempted >= _REFINE_MIN_ATTEMPTED and simulated >= 2 and submittable == 0 and errors <= 1:
        recommended_scope = "refine"
        recommended_role = "refine_neighbor"
        priority_adjustment = _REFINE_FOCUS_BONUS
        reason = "nearpass_refine_focus"

    role_counts = _count_mapping(stat.get("role_counts"))
    scope_counts = _count_mapping(stat.get("scope_counts"))
    return {
        "current_role": role,
        "current_scope": scope,
        "recommended_role": recommended_role or _recommended_role_from_scope(recommended_scope),
        "recommended_scope": recommended_scope,
        "priority_adjustment": priority_adjustment,
        "should_suppress": should_suppress,
        "reason": reason,
        "attempted": attempted,
        "submittable": submittable,
        "simulated": simulated,
        "errors": errors,
        "role_counts": role_counts,
        "scope_counts": scope_counts,
    }


def compile_template_registry_summary(
    template_stats: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build a sorted, JSON-ready registry summary from template stats."""
    rows: list[dict[str, Any]] = []
    for template_name, stat in template_stats.items():
        if not isinstance(stat, Mapping):
            continue
        current_role = normalize_template_role(stat.get("template_role"))
        current_scope = normalize_activation_scope(stat.get("template_activation_scope"))
        recommendation = recommend_template_role_transition(
            template_name,
            template_stats,
            current_role=current_role,
            current_scope=current_scope,
        )
        rows.append(
            {
                "template_name": template_name,
                "template_family": str(stat.get("template_family", "") or ""),
                "template_stage": str(stat.get("template_stage", "") or ""),
                "current_role": current_role,
                "current_scope": current_scope,
                "recommended_role": recommendation["recommended_role"],
                "recommended_scope": recommendation["recommended_scope"],
                "priority_adjustment": recommendation["priority_adjustment"],
                "should_suppress_in_generate": recommendation["should_suppress"],
                "reason": recommendation["reason"],
                "attempted": int(stat.get("attempted", 0) or 0),
                "simulated": int(stat.get("simulated", 0) or 0),
                "submittable": int(stat.get("submittable", 0) or 0),
                "errors": int(stat.get("errors", 0) or 0),
                "role_counts": recommendation["role_counts"],
                "scope_counts": recommendation["scope_counts"],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["should_suppress_in_generate"],
            -row["submittable"],
            -row["simulated"],
            -row["attempted"],
            row["template_name"],
        ),
    )


def merge_registry_recommendations_into_template_stats(
    template_stats: dict[str, dict[str, Any]],
    registry_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Merge persisted registry recommendations back into template stats."""
    if not registry_rows:
        return template_stats
    merged = dict(template_stats)
    for row in registry_rows:
        template_name = str(row.get("template_name", "") or "")
        if not template_name:
            continue
        stat = dict(merged.get(template_name, {}))
        if "recommended_role" in row:
            stat["registry_recommended_role"] = str(row.get("recommended_role", "") or "")
        if "recommended_scope" in row:
            stat["registry_recommended_scope"] = str(row.get("recommended_scope", "") or "")
        if "priority_adjustment" in row:
            stat["registry_priority_adjustment"] = int(row.get("priority_adjustment", 0) or 0)
        if "reason" in row:
            stat["registry_reason"] = str(row.get("reason", "") or "")
        if "template_family" in row and row.get("template_family"):
            stat["template_family"] = str(row.get("template_family", "") or "")
        merged[template_name] = stat
    return merged


def compile_template_family_registry(
    template_stats: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Aggregate registry-like summary at template-family granularity."""
    grouped: dict[str, dict[str, Any]] = {}
    for stat in template_stats.values():
        if not isinstance(stat, Mapping):
            continue
        family = str(stat.get("template_family", "") or "").strip().lower()
        if not family:
            continue
        row = grouped.setdefault(
            family,
            {
                "template_family": family,
                "attempted": 0,
                "simulated": 0,
                "submittable": 0,
                "errors": 0,
                "low_sharpe": 0,
                "low_fitness": 0,
                "concentrated_weight": 0,
            },
        )
        for key in (
            "attempted",
            "simulated",
            "submittable",
            "errors",
            "low_sharpe",
            "low_fitness",
            "concentrated_weight",
        ):
            row[key] += int(stat.get(key, 0) or 0)
    for family, row in grouped.items():
        if row["submittable"] > 0:
            row["recommended_scope"] = "broad"
            row["budget_adjustment"] = _FAMILY_STRONG_SUBMITTABLE_BONUS
            row["reason"] = "family_has_submittable_history"
        elif (
            row["attempted"] >= _FAMILY_WEAK_MIN_ATTEMPTED
            and row["submittable"] == 0
            and ((row["low_sharpe"] >= 4 and row["low_fitness"] >= 4) or row["concentrated_weight"] >= 3)
        ):
            row["recommended_scope"] = "diagnostic"
            row["budget_adjustment"] = -1
            row["reason"] = "family_persistent_failure_pattern"
        else:
            row["recommended_scope"] = "refine" if row["simulated"] > 0 else "broad"
            row["budget_adjustment"] = 0
            row["reason"] = "family_neutral"
        grouped[family] = row
    return grouped


__all__ = [
    "compile_template_family_registry",
    "compile_template_registry_summary",
    "merge_registry_recommendations_into_template_stats",
    "normalize_activation_scope",
    "normalize_template_role",
    "recommend_template_role_transition",
]
