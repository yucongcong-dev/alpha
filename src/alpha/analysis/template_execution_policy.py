"""Compatibility wrapper for template execution selection policy."""

from ..selection.template_execution_policy import (
    TemplateExecutionDecision,
    build_template_execution_decision,
)

__all__ = ["TemplateExecutionDecision", "build_template_execution_decision"]
