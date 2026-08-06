"""Field metadata filtering tests."""

from __future__ import annotations

from alpha.app.bootstrap_fields import infer_field_family, prepare_fields_for_execution
from alpha.models import HistoricalRunState
from alpha.models.domain import TemplateField
from alpha.models.domain_parsers import parse_template_field
from alpha.models.io_types import RunFilters
from alpha.models.runtime_options import FieldSelectionOptions
from alpha.policy.expression import get_dataset_expression_policy


def _domain_fields(rows: list[dict[str, object]]) -> list[TemplateField]:
    return [parse_template_field(row) for row in rows]


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
    args = FieldSelectionOptions(limit=1, offset=0, top_fields_by_feedback=0)
    filters = RunFilters(include_fields={"cash_st"})
    historical_state = HistoricalRunState(field_feedback={})

    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=historical_state,
        selection_options=args,
    )

    assert [row.field_id for row in selected] == ["cash_st"]
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
    args = FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0)
    filters = RunFilters()
    historical_state = HistoricalRunState(field_feedback={})

    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=historical_state,
        selection_options=args,
    )

    assert [row.field_id for row in selected] == ["cash_st"]
    assert stats["low_coverage_count"] == 1
    assert stats["filtered_field_count"] == 1


def test_explicit_include_fields_bypass_metadata_filters_and_feedback_ranking() -> None:
    """Preset field lists are closed sets and should not be rewritten by strategy ranking."""
    fields = [
        {
            "id": "strong_feedback",
            "coverage": 1.0,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
        {
            "id": "manual_field",
            "coverage": 0.01,
            "dateCoverage": 0.10,
            "alphaCount": 0,
            "userCount": 0,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
    ]
    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(include_fields={"manual_field"}),
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=HistoricalRunState(
            field_feedback={"strong_feedback": {"best_score": 1.0, "attempted_templates": 3}}
        ),
        selection_options=FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0),
    )

    assert [row.field_id for row in selected] == ["manual_field"]
    assert selected[0].get("selection_reason") == "explicit"
    assert stats["prefiltered_count"] == 1
    assert stats["low_coverage_count"] == 0
    assert stats["low_date_coverage_count"] == 0


def test_fundamental6_no_longer_applies_stricter_event_field_filters() -> None:
    fields = [
        {
            "id": "cash_st",
            "coverage": 0.21,
            "dateCoverage": 0.98,
            "alphaCount": 45,
            "userCount": 8,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
        {
            "id": "fnd6_cptnewqeventv110_apq",
            "coverage": 0.21,
            "dateCoverage": 0.98,
            "alphaCount": 45,
            "userCount": 8,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
    ]
    args = FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0)
    filters = RunFilters()
    historical_state = HistoricalRunState(field_feedback={})

    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=historical_state,
        selection_options=args,
    )

    assert {row.field_id for row in selected} == {"cash_st", "fnd6_cptnewqeventv110_apq"}
    assert stats["low_coverage_count"] == 0


def test_prepare_fields_for_execution_tags_model16_field_lanes() -> None:
    fields = [
        {
            "id": "fscore_quality",
            "coverage": 0.30,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 10,
            "themes": [],
            "dateCreated": "2022-05-01",
            "type": "MATRIX",
        },
        {
            "id": "analyst_revision_rank_derivative",
            "coverage": 1.0,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 10,
            "themes": [],
            "dateCreated": "2022-05-01",
            "type": "MATRIX",
        },
    ]
    args = FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0)
    filters = RunFilters()
    historical_state = HistoricalRunState(field_feedback={})

    selected, _ = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("model16"),
        historical_state=historical_state,
        selection_options=args,
    )

    tags_by_id = {row.field_id: tuple(row.get("runtime_field_tags", [])) for row in selected}
    assert "model16_sparse_fscore" in tags_by_id["fscore_quality"]
    assert "model16_dense_derivative" in tags_by_id["analyst_revision_rank_derivative"]
    assert [row.field_id for row in selected] == [
        "fscore_quality",
        "analyst_revision_rank_derivative",
    ]


def test_infer_field_family_removes_windows_before_instrument_suffix() -> None:
    assert infer_field_family("correlation_last_30_days_spy") == "correlation_spy"
    assert infer_field_family("correlation_last_360_days_spy") == "correlation_spy"
    assert infer_field_family("option_breakeven_30") == "option_breakeven"
    assert infer_field_family("pcr_vol_all") == "pcr_vol"


def test_prepare_fields_for_execution_hard_filters_crowded_model51_fields() -> None:
    fields = [
        {
            "id": "unsystematic_risk_last_360_days",
            "coverage": 0.94,
            "dateCoverage": 1.0,
            "alphaCount": 14503,
            "userCount": 4549,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
        {
            "id": "unsystematic_risk_last_60_days",
            "coverage": 0.96,
            "dateCoverage": 1.0,
            "alphaCount": 2535,
            "userCount": 1173,
            "themes": [],
            "dateCreated": "2022-05-01",
        },
    ]
    args = FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0)
    filters = RunFilters()
    historical_state = HistoricalRunState(field_feedback={})

    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("model51"),
        historical_state=historical_state,
        selection_options=args,
    )

    assert [row.field_id for row in selected] == ["unsystematic_risk_last_60_days"]
    assert stats["high_alpha_count"] == 1


def test_unknown_dataset_filters_unvalidated_and_overcrowded_fields() -> None:
    fields = [
        {
            "id": "valid_signal",
            "coverage": 0.80,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
        {
            "id": "too_sparse",
            "coverage": 0.10,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
        {
            "id": "too_crowded",
            "coverage": 1.0,
            "dateCoverage": 1.0,
            "alphaCount": 20000,
            "userCount": 100,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
    ]
    args = FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0)

    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        selection_options=args,
    )

    assert [row.field_id for row in selected] == ["valid_signal"]
    assert stats["low_coverage_count"] == 1
    assert stats["high_alpha_count"] == 1
