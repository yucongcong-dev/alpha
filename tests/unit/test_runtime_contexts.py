"""Focused construction tests for the split template build contexts."""

from __future__ import annotations

import pytest

from alpha.models.domain import TemplateField
from alpha.runtime.contexts import (
    TemplateBuildContext,
    TemplateFeedbackContext,
    TemplateSourceContext,
)

from .template_build_options_support import template_build_options


def test_legacy_template_build_context_arguments_are_projected_to_nested_contexts() -> None:
    options = template_build_options(dataset_id="model16")
    fields = [
        TemplateField(
            field_id="f1",
            field_name="f1",
            field_type="MATRIX",
        )
    ]
    field_feedback = {"f1": {"best_score": 0.5}}
    failed_counts = {"LOW_SHARPE": 2}

    context = TemplateBuildContext(
        options=options,
        template_library_file="datasets/model16/template.json",
        all_fields=fields,
        template_library={"default": []},
        include_templates={"rank"},
        exclude_templates={"raw"},
        field_feedback=field_feedback,
        global_failed_check_counts=failed_counts,
        feedback_template_min_priority=175,
        feedback_result_count=4,
    )

    assert context.source.options is options
    assert context.source.all_fields == fields
    assert context.source.include_templates == {"rank"}
    assert context.source.exclude_templates == {"raw"}
    assert context.feedback.field_feedback is field_feedback
    assert context.feedback.global_failed_check_counts is failed_counts
    assert context.feedback.feedback_template_min_priority == 175
    assert context.feedback.feedback_result_count == 4


def test_nested_template_build_context_takes_precedence_over_legacy_arguments() -> None:
    options = template_build_options(dataset_id="nested")
    source = TemplateSourceContext(options=options, include_templates={"nested"})
    feedback = TemplateFeedbackContext(field_feedback={"nested": {"best_score": 1.0}})

    context = TemplateBuildContext(
        source=source,
        feedback=feedback,
        options=template_build_options(dataset_id="ignored"),
        include_templates={"ignored"},
        field_feedback={"ignored": {"best_score": 0.0}},
    )

    assert context.source is source
    assert context.feedback is feedback


def test_template_build_context_requires_options_for_legacy_source() -> None:
    with pytest.raises(TypeError, match="requires source or options"):
        TemplateBuildContext()


def test_legacy_default_collections_are_independent_between_contexts() -> None:
    options = template_build_options()
    first = TemplateBuildContext(options=options)
    second = TemplateBuildContext(options=options)

    first.source.include_templates.add("rank")
    first.feedback.field_feedback["f1"] = {"best_score": 0.1}

    assert second.source.include_templates == set()
    assert second.feedback.field_feedback == {}
