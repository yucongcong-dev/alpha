"""Template execution-policy helpers for queue planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..analysis.template_registry_rules import (
    normalize_activation_scope,
    normalize_template_role,
)
from ..models.domain import NearPassCandidate
from ..models.domain_parsers import parse_failed_check


@dataclass(frozen=True)
class TemplateExecutionDecision:
    """Execution-facing decision for a single template candidate."""

    template_role: str
    template_activation_scope: str
    effective_priority: int
    effective_variant_budget: int
    refine_candidate: NearPassCandidate | None = None


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
    field_id: str,
    field_name: str,
    base_variant_budget: int,
) -> TemplateExecutionDecision:
    """Use template metadata and the field-stage budget without registry adaptation."""
    template_role = normalize_template_role(template_metadata.get("role"))
    template_activation_scope = normalize_activation_scope(
        template_metadata.get("activation_scope")
    )

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
        template_role=template_role,
        template_activation_scope=template_activation_scope,
        effective_priority=priority,
        effective_variant_budget=max(1, int(base_variant_budget or 1)),
        refine_candidate=refine_candidate,
    )


__all__ = ["TemplateExecutionDecision", "build_template_execution_decision"]
