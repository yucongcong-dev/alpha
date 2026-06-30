"""Field selection and ranking tests."""

from __future__ import annotations

from argparse import Namespace

from alpha.config import get_dataset_expression_policy
from alpha.main import prepare_fields_for_execution, refresh_runtime_feedback
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
