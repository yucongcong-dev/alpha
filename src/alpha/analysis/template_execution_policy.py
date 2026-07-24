"""Template execution-policy helpers for queue planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..config.constants import FEEDBACK_STAGE_GENERATE
from ..models.domain import NearPassCandidate
from ..models.domain_parsers import parse_failed_check
from .template_registry_budget import (
    choose_family_settings_budget,
    choose_field_cluster_settings_budget,
    choose_registry_settings_budget,
)
from .template_registry_rules import (
    normalize_activation_scope,
    normalize_template_role,
    recommend_template_role_transition,
)
from .template_registry_store import resolve_registry_override
from .template_stats import historical_template_priority_bonus


@dataclass(frozen=True)
class TemplateExecutionDecision:
    """Execution-facing registry decision for a single template candidate."""

    template_role: str
    template_activation_scope: str
    effective_priority: int
    effective_variant_budget: int
    refine_candidate: NearPassCandidate | None = None


def _merge_manual_override(
    role_recommendation: dict[str, Any],
    manual_override: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply a manual registry override on top of an inferred role recommendation."""
    merged = dict(role_recommendation)
    if not manual_override:
        return merged
    merged.update(
        recommended_role=normalize_template_role(
            manual_override.get("recommended_role") or merged["recommended_role"]
        ),
        recommended_scope=normalize_activation_scope(
            manual_override.get("recommended_scope") or merged["recommended_scope"]
        ),
        priority_adjustment=int(
            manual_override.get("priority_adjustment", merged["priority_adjustment"]) or 0
        ),
        should_suppress=bool(
            manual_override.get("should_suppress", merged["should_suppress"])
        ),
        reason=str(manual_override.get("reason", merged["reason"]) or ""),
    )
    return merged


def _annotate_template_metadata(
    template_metadata: dict[str, Any],
    *,
    recommended_role: str,
    recommended_scope: str,
    reason: str,
) -> None:
    """Persist resolved registry recommendation metadata onto the template candidate."""
    template_metadata["registry_recommended_role"] = recommended_role
    template_metadata["registry_recommended_scope"] = recommended_scope
    template_metadata["registry_reason"] = reason


def _resolve_effective_variant_budget(
    *,
    base_variant_budget: int,
    role_recommendation: Mapping[str, Any],
    template_family: str,
    template_family_registry: Mapping[str, Mapping[str, Any]],
    field_tags: object,
    template_registry_overrides: Mapping[str, Any],
    feedback_stage: str,
) -> int:
    """Apply registry, family, and field-cluster budget adjustments in one place."""
    effective_variant_budget = choose_registry_settings_budget(
        base_variant_budget,
        role_recommendation,
        feedback_stage=feedback_stage,
    )
    effective_variant_budget = choose_family_settings_budget(
        effective_variant_budget,
        template_family,
        template_family_registry,
        feedback_stage=feedback_stage,
    )
    return choose_field_cluster_settings_budget(
        effective_variant_budget,
        field_tags,
        template_registry_overrides,
        feedback_stage=feedback_stage,
    )


def _build_refine_candidate(
    *,
    field_id: str,
    field_name: str,
    template_name: str,
    expression: str,
    template_family: str,
    template_stage: str,
    template_metadata: dict[str, Any],
) -> NearPassCandidate | None:
    """Rebuild a refine candidate from template metadata when available."""
    refine_failed_checks = template_metadata.get("refine_failed_checks")
    if not isinstance(refine_failed_checks, list):
        return None
    return NearPassCandidate(
        field_id=field_id,
        field_name=field_name,
        template_name=template_name,
        expression=expression,
        template_family=template_family,
        template_stage=template_stage,
        score=float(template_metadata.get("refine_score", 0.0) or 0.0),
        failed_checks=[parse_failed_check(check) for check in refine_failed_checks],
    )


def build_template_execution_decision(
    *,
    template_name: str,
    expression: str,
    priority: int,
    template_family: str,
    template_stage: str,
    template_metadata: dict[str, Any],
    template_stats: Mapping[str, Mapping[str, int]],
    template_registry: Mapping[str, Mapping[str, Any]],
    template_family_registry: Mapping[str, Mapping[str, Any]],
    template_registry_overrides: Mapping[str, Any],
    field_id: str,
    field_name: str,
    field_tags: object,
    base_variant_budget: int,
    feedback_stage: str = FEEDBACK_STAGE_GENERATE,
) -> TemplateExecutionDecision | None:
    """Resolve registry role/scope/budget policy for one template candidate."""
    manual_override = resolve_registry_override(
        template_registry_overrides,
        template_name=template_name,
        template_family=template_family,
    )
    persisted_registry_entry = template_registry.get(template_name, {})
    template_role = normalize_template_role(
        manual_override.get("recommended_role")
        or persisted_registry_entry.get("recommended_role")
        or template_metadata.get("role")
    )
    template_activation_scope = normalize_activation_scope(
        manual_override.get("recommended_scope")
        or persisted_registry_entry.get("recommended_scope")
        or template_metadata.get("activation_scope")
    )
    role_recommendation = recommend_template_role_transition(
        template_name,
        template_stats,
        current_role=template_role,
        current_scope=template_activation_scope,
        feedback_stage=feedback_stage,
    )
    role_recommendation = _merge_manual_override(role_recommendation, manual_override)
    if role_recommendation["should_suppress"]:
        return None

    recommended_role = normalize_template_role(role_recommendation["recommended_role"])
    recommended_scope = normalize_activation_scope(role_recommendation["recommended_scope"])
    _annotate_template_metadata(
        template_metadata,
        recommended_role=recommended_role,
        recommended_scope=recommended_scope,
        reason=role_recommendation["reason"],
    )

    effective_priority = priority + historical_template_priority_bonus(
        template_name, template_stats
    ) + int(role_recommendation["priority_adjustment"])
    effective_variant_budget = _resolve_effective_variant_budget(
        base_variant_budget=base_variant_budget,
        role_recommendation=role_recommendation,
        template_family=template_family,
        template_family_registry=template_family_registry,
        field_tags=field_tags,
        template_registry_overrides=template_registry_overrides,
        feedback_stage=feedback_stage,
    )
    if effective_variant_budget <= 0:
        return None

    refine_candidate = _build_refine_candidate(
        field_id=field_id,
        field_name=field_name,
        template_name=template_name,
        expression=expression,
        template_family=template_family,
        template_stage=template_stage,
        template_metadata=template_metadata,
    )

    return TemplateExecutionDecision(
        template_role=recommended_role,
        template_activation_scope=recommended_scope,
        effective_priority=effective_priority,
        effective_variant_budget=effective_variant_budget,
        refine_candidate=refine_candidate,
    )


__all__ = ["TemplateExecutionDecision", "build_template_execution_decision"]
