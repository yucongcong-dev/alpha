"""Template performance registry and role recommendation helpers."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from typing import Any

from ..config.constants import FEEDBACK_STAGE_GENERATE, FEEDBACK_STAGE_RESIMULATE
from ..io.output_paths import build_output_sidecar_paths

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
_DEFAULT_OVERRIDE_PAYLOAD = {
    "template_overrides": {},
    "family_overrides": {},
    "field_cluster_overrides": {},
}


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
        and (
            (low_sharpe >= 3 and low_fitness >= 3)
            or concentrated >= 2
        )
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
        return dict(_DEFAULT_OVERRIDE_PAYLOAD)
    override_path = build_output_sidecar_paths(output_path)["template_registry_overrides"]
    if not os.path.exists(override_path):
        return dict(_DEFAULT_OVERRIDE_PAYLOAD)
    try:
        with open(override_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return dict(_DEFAULT_OVERRIDE_PAYLOAD)
    if not isinstance(payload, dict):
        return dict(_DEFAULT_OVERRIDE_PAYLOAD)
    normalized = dict(_DEFAULT_OVERRIDE_PAYLOAD)
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
            and (
                (row["low_sharpe"] >= 4 and row["low_fitness"] >= 4)
                or row["concentrated_weight"] >= 3
            )
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
    "build_template_registry_index",
    "choose_field_cluster_settings_budget",
    "choose_family_settings_budget",
    "choose_registry_settings_budget",
    "compile_template_family_registry",
    "compile_template_registry_summary",
    "load_registry_overrides",
    "load_persisted_template_registry",
    "merge_registry_recommendations_into_template_stats",
    "normalize_activation_scope",
    "normalize_template_role",
    "resolve_registry_override",
    "recommend_template_role_transition",
]
