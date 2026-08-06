"""Field ranking, diversity, and exploitation-budget tests."""

from __future__ import annotations

from alpha.app.bootstrap_fields import prepare_fields_for_execution
from alpha.models import HistoricalRunState
from alpha.models.domain import TemplateField
from alpha.models.domain_parsers import parse_template_field
from alpha.models.io_types import RunFilters
from alpha.models.runtime_options import FieldSelectionOptions
from alpha.policy.expression import get_dataset_expression_policy


def _domain_fields(rows: list[dict[str, object]]) -> list[TemplateField]:
    return [parse_template_field(row) for row in rows]


def test_limit_diversifies_numeric_tenor_families() -> None:
    fields = [
        {
            "id": field_id,
            "coverage": coverage,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        }
        for field_id, coverage in [
            ("call_breakeven_10", 1.00),
            ("call_breakeven_20", 0.99),
            ("call_breakeven_30", 0.98),
            ("forward_price_10", 0.97),
        ]
    ]
    args = FieldSelectionOptions(limit=3, offset=0, top_fields_by_feedback=0)

    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        selection_options=args,
    )

    assert [row.field_id for row in selected] == [
        "call_breakeven_30",
        "call_breakeven_20",
        "forward_price_10",
    ]
    assert stats["selected_family_count"] == 2


def test_limit_reserves_capacity_for_unexplored_fields() -> None:
    fields = [
        {
            "id": field_id,
            "coverage": coverage,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        }
        for field_id, coverage in [
            ("known_signal_a", 1.00),
            ("known_signal_b", 0.99),
            ("new_signal", 0.98),
        ]
    ]
    history = HistoricalRunState(
        field_feedback={
            "known_signal_a": {"best_score": 0.90, "attempted_templates": 2},
            "known_signal_b": {"best_score": 0.80, "attempted_templates": 2},
        }
    )
    args = FieldSelectionOptions(limit=2, offset=0, top_fields_by_feedback=0)

    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=history,
        selection_options=args,
    )

    assert [row.field_id for row in selected] == ["known_signal_a", "new_signal"]
    assert stats["selected_unexplored_count"] == 1


def test_feedback_focus_keeps_field_family_diversity() -> None:
    fields = [
        {
            "id": field_id,
            "coverage": 1.0,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        }
        for field_id in (
            "call_breakeven_10",
            "call_breakeven_20",
            "call_breakeven_30",
            "forward_price_10",
        )
    ]
    history = HistoricalRunState(
        field_feedback={
            field_id: {"best_score": score, "attempted_templates": 4}
            for field_id, score in (
                ("call_breakeven_10", 0.90),
                ("call_breakeven_20", 0.80),
                ("call_breakeven_30", 0.70),
                ("forward_price_10", 0.60),
            )
        }
    )

    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=history,
        selection_options=FieldSelectionOptions(
            limit=0,
            offset=0,
            top_fields_by_feedback=3,
        ),
    )

    assert [row.field_id for row in selected] == [
        "call_breakeven_10",
        "call_breakeven_20",
        "forward_price_10",
    ]
    assert stats["selected_family_count"] == 2


def test_failed_feedback_does_not_consume_exploitation_budget() -> None:
    fields = [
        {
            "id": field_id,
            "coverage": 1.0,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        }
        for field_id in ("failed_signal", "new_signal_a", "new_signal_b")
    ]
    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(
            field_feedback={"failed_signal": {"best_score": 0.1, "attempted_templates": 4}}
        ),
        selection_options=FieldSelectionOptions(limit=2, offset=0, top_fields_by_feedback=0),
    )

    assert [row.field_id for row in selected] == ["new_signal_a", "new_signal_b"]
    assert stats["selected_unexplored_count"] == 2


def test_submittable_feedback_is_promising_even_after_single_attempt() -> None:
    fields = [
        {
            "id": "passed_signal",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        }
    ]
    selected, _ = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=HistoricalRunState(
            field_feedback={
                "passed_signal": {
                    "best_score": 1.0,
                    "attempted_templates": 1,
                    "submittable_templates": 1,
                }
            }
        ),
        selection_options=FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0),
    )

    assert selected[0].get("selection_reason") == "historical_promising"


def test_unknown_field_metadata_is_retained_without_affecting_rank_score() -> None:
    fields = [
        {
            "id": "complete_signal",
            "coverage": 1.0,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
        {"id": "metadata_missing"},
    ]
    selected, stats = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        selection_options=FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0),
    )

    assert {row.field_id for row in selected} == {"complete_signal", "metadata_missing"}
    assert stats["unknown_coverage_count"] == 1
    assert stats["unknown_date_coverage_count"] == 1
    assert stats["unknown_alpha_count"] == 1
    assert stats["unknown_user_count"] == 1
    scores = {row.field_id: row.get("selection_score") for row in selected}
    assert scores["metadata_missing"] == scores["complete_signal"] == 0.0


def test_single_attempt_feedback_is_not_pinned_as_promising() -> None:
    fields = [
        {
            "id": "one_attempt",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
        {
            "id": "unexplored",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
    ]
    selected, _ = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=HistoricalRunState(
            field_feedback={"one_attempt": {"best_score": 0.95, "attempted_templates": 1}}
        ),
        selection_options=FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0),
    )

    reasons = {row.field_id: row.get("selection_reason") for row in selected}
    assert reasons["one_attempt"] == "historical_feedback"


def test_stale_feedback_is_decayed_before_promising_classification() -> None:
    fields = [
        {
            "id": "stale_signal",
            "coverage": 0.5,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        }
    ]
    selected, _ = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=HistoricalRunState(
            field_feedback={
                "stale_signal": {
                    "best_score": 0.95,
                    "attempted_templates": 2,
                    "latest_result_at": "2020-01-01T00:00:00Z",
                }
            }
        ),
        selection_options=FieldSelectionOptions(limit=0, offset=0, top_fields_by_feedback=0),
    )

    assert selected[0].get("selection_reason") == "historical_feedback"


def test_unknown_dataset_prefers_matrix_over_equivalent_vector() -> None:
    fields = [
        {
            "id": "vector_signal",
            "type": "VECTOR",
            "coverage": 1.0,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
        {
            "id": "matrix_signal",
            "type": "MATRIX",
            "coverage": 1.0,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        },
    ]
    args = FieldSelectionOptions(limit=1, offset=0, top_fields_by_feedback=0)

    selected, _ = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        selection_options=args,
    )

    assert [row.field_id for row in selected] == ["matrix_signal"]


def test_family_selection_prefers_representative_windows_on_ties() -> None:
    fields = [
        {
            "id": f"pcr_vol_{window}",
            "type": "MATRIX",
            "coverage": 1.0,
            "dateCoverage": 1.0,
            "alphaCount": 100,
            "userCount": 20,
            "themes": [],
            "dateCreated": "2025-01-01",
        }
        for window in (10, 30, 60, 1080)
    ]
    args = FieldSelectionOptions(limit=2, offset=0, top_fields_by_feedback=0)

    selected, _ = prepare_fields_for_execution(
        _domain_fields(fields),
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        selection_options=args,
    )

    assert [row.field_id for row in selected] == ["pcr_vol_30", "pcr_vol_60"]
