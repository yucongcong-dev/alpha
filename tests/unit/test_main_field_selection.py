"""Field selection and ranking tests."""

from __future__ import annotations

from argparse import Namespace

from alpha.config import get_dataset_expression_policy
from alpha.main import (
    build_field_resume_positions,
    normalize_resume_index,
    prepare_fields_for_execution,
    refresh_runtime_feedback,
)
from alpha.models.base import FieldTestResult, HistoricalRunState, RunFilters, TemplateBuildContext


def test_prepare_fields_for_execution_filters_before_limit() -> None:
    """include/exclude filters must run before limit truncation."""
    fields = [
        {
            "id": "assets",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 10,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
        {
            "id": "cash_st",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 10,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
    ]
    args = Namespace(limit=1, offset=0, top_fields_by_feedback=0)
    filters = RunFilters(include_fields={"cash_st"})
    historical_state = HistoricalRunState(field_feedback={})

    selected, stats = prepare_fields_for_execution(
        fields,
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=historical_state,
        args=args,
    )

    assert [row["id"] for row in selected] == ["cash_st"]
    assert stats["prefiltered_count"] == 1
    assert stats["filtered_field_count"] == 1
    assert stats["ranked_field_count"] == 1


def test_prepare_fields_for_execution_applies_metadata_filters() -> None:
    """Fields below metadata thresholds should be dropped before ranking."""
    fields = [
        {
            "id": "cash_st",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 10,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
        {
            "id": "weak_field",
            "coverage": 0.01,
            "dateCoverage": 0.50,
            "alphaCount": 1,
            "userCount": 0,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
    ]
    args = Namespace(limit=0, offset=0, top_fields_by_feedback=0)
    filters = RunFilters()
    historical_state = HistoricalRunState(field_feedback={})

    selected, stats = prepare_fields_for_execution(
        fields,
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=historical_state,
        args=args,
    )

    assert [row["id"] for row in selected] == ["cash_st"]
    assert stats["low_coverage_count"] == 1
    assert stats["filtered_field_count"] == 1


def test_refresh_runtime_feedback_rebuilds_feedback_from_current_results() -> None:
    """Same-process results should be converted into fresh field/global feedback."""
    build_ctx = TemplateBuildContext()
    results = [
        FieldTestResult(
            field_id="cash_st",
            field_type="MATRIX",
            field_name="cash_st",
            template_name="group_zscore_subindustry_60",
            template_family="group_zscore",
            template_stage="group_second_order",
            status="simulated",
            submittable=False,
            expression="group_rank(ts_zscore(cash_st, 60), subindustry)",
            failed_checks=[{"name": "LOW_SHARPE", "value": 0.9, "limit": 1.25}],
        )
    ]

    refresh_runtime_feedback(build_ctx, results, force=True)

    assert build_ctx.field_feedback["cash_st"]["attempted_templates"] == 1
    assert build_ctx.field_feedback["cash_st"]["best_template_stage"] == "group_second_order"
    assert build_ctx.global_failed_check_counts["LOW_SHARPE"] == 1


def test_refresh_runtime_feedback_preserves_seed_feedback_and_only_adds_new_results() -> None:
    """Seeded feedback from a dedicated feedback file should not be overwritten at runtime."""
    build_ctx = TemplateBuildContext(
        field_feedback={
            "seed_field": {
                "field_name": "seed_field",
                "best_score": 0.8,
                "best_expression": "rank(seed_field)",
                "best_template_name": "seed_tpl",
                "best_template_family": "seed_family",
                "best_template_stage": "seed_stage",
                "attempted_templates": 3,
                "failed_check_counts": {"LOW_FITNESS": 2},
            }
        },
        global_failed_check_counts={"LOW_FITNESS": 2},
    )
    setattr(build_ctx, "_feedback_result_count", 1)
    results = [
        FieldTestResult(
            field_id="existing_output_field",
            field_type="MATRIX",
            field_name="existing_output_field",
            template_name="existing_tpl",
            status="simulated",
            submittable=False,
            expression="rank(existing_output_field)",
            failed_checks=[{"name": "LOW_SHARPE", "value": 0.6, "limit": 1.25}],
        ),
        FieldTestResult(
            field_id="new_field",
            field_type="MATRIX",
            field_name="new_field",
            template_name="new_tpl",
            template_stage="group_second_order",
            status="simulated",
            submittable=False,
            expression="rank(new_field)",
            failed_checks=[{"name": "LOW_SHARPE", "value": 0.9, "limit": 1.25}],
        ),
    ]

    refresh_runtime_feedback(build_ctx, results)

    assert build_ctx.field_feedback["seed_field"]["attempted_templates"] == 3
    assert build_ctx.field_feedback["new_field"]["attempted_templates"] == 1
    assert build_ctx.global_failed_check_counts["LOW_FITNESS"] == 2
    assert build_ctx.global_failed_check_counts["LOW_SHARPE"] == 1


def test_build_field_resume_positions_tracks_original_order() -> None:
    """Resume positions should remain tied to the original field ordering."""
    positions = build_field_resume_positions(
        [
            {"id": "field_a"},
            {"id": "field_b"},
            {"id": "field_c"},
        ]
    )

    assert positions == {"field_a": 1, "field_b": 2, "field_c": 3}


def test_normalize_resume_index_wraps_large_saved_cursor() -> None:
    """Saved cursors from prior resumes should wrap into the current field range."""
    assert normalize_resume_index(6, 4) == 2
    assert normalize_resume_index(4, 4) == 0
    assert normalize_resume_index(0, 0) == 0
