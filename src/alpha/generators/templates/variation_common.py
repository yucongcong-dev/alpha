"""Shared helpers for template variation strategies."""

from __future__ import annotations

from typing import Any

from ...config import DatasetExpressionPolicy
from ...policy.template_blacklist import is_blacklisted_template as _policy_is_blacklisted_template
from .classification import classify_expression_family, classify_template_stage


def is_blacklisted_template(
    template_name: str,
    expression: str = "",
    *,
    template_metadata: dict[str, Any] | None = None,
    dataset_id: str = "",
    policy: DatasetExpressionPolicy | None = None,
) -> bool:
    """Check whether a generated variation is blocked by policy or dataset blacklist rules."""
    return _policy_is_blacklisted_template(
        template_name,
        expression,
        template_metadata=template_metadata,
        dataset_id=dataset_id,
        policy=policy,
        current_family=classify_expression_family(template_name, expression, template_metadata),
        current_stage=classify_template_stage(template_name, expression, template_metadata),
    )
