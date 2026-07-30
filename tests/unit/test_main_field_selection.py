"""Field selection and ranking tests."""

from __future__ import annotations

from argparse import Namespace

from alpha.app.bootstrap_fields import infer_field_family, prepare_fields_for_execution
from alpha.app.run_loop_feedback import refresh_runtime_feedback
from alpha.app.run_loop_resume import build_field_resume_positions, normalize_resume_index
from alpha.models.domain import FieldTestResult
from alpha.models.io_types import RunFilters
from alpha.models.runtime import HistoricalRunState, TemplateBuildContext, TemplateBuildOptions
from alpha.policy.expression import get_dataset_expression_policy

_DEFAULT_SIM_SETTINGS = {
    "region": "USA",
    "universe": "TOP3000",
    "instrument_type": "EQUITY",
    "delay": 1,
    "decay": 4,
    "neutralization": "SUBINDUSTRY",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unit_handling": "VERIFY",
    "nan_handling": "OFF",
    "language": "FASTEXPR",
}


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


def test_prepare_fields_for_execution_applies_stricter_event_field_filters() -> None:
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
    args = Namespace(limit=0, offset=0, top_fields_by_feedback=0)
    filters = RunFilters()
    historical_state = HistoricalRunState(field_feedback={})

    selected, _ = prepare_fields_for_execution(
        fields,
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("model16"),
        historical_state=historical_state,
        args=args,
    )

    tags_by_id = {row["id"]: tuple(row.get("runtime_field_tags", [])) for row in selected}
    assert "model16_sparse_fscore" in tags_by_id["fscore_quality"]
    assert "model16_dense_derivative" in tags_by_id["analyst_revision_rank_derivative"]
    assert [row["id"] for row in selected] == [
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
    args = Namespace(limit=0, offset=0, top_fields_by_feedback=0)
    filters = RunFilters()
    historical_state = HistoricalRunState(field_feedback={})

    selected, stats = prepare_fields_for_execution(
        fields,
        filters_dict=filters,
        expression_policy=get_dataset_expression_policy("model51"),
        historical_state=historical_state,
        args=args,
    )

    assert [row["id"] for row in selected] == ["unsystematic_risk_last_60_days"]
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
    args = Namespace(limit=0, offset=0, top_fields_by_feedback=0)

    selected, stats = prepare_fields_for_execution(
        fields,
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        args=args,
    )

    assert [row["id"] for row in selected] == ["valid_signal"]
    assert stats["low_coverage_count"] == 1
    assert stats["high_alpha_count"] == 1


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
    args = Namespace(limit=3, offset=0, top_fields_by_feedback=0)

    selected, stats = prepare_fields_for_execution(
        fields,
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        args=args,
    )

    assert [row["id"] for row in selected] == [
        "call_breakeven_10",
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
    args = Namespace(limit=2, offset=0, top_fields_by_feedback=0)

    selected, stats = prepare_fields_for_execution(
        fields,
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=history,
        args=args,
    )

    assert [row["id"] for row in selected] == ["known_signal_a", "new_signal"]
    assert stats["selected_unexplored_count"] == 1


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
        fields,
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(
            field_feedback={"failed_signal": {"best_score": 0.1, "attempted_templates": 4}}
        ),
        args=Namespace(limit=2, offset=0, top_fields_by_feedback=0),
    )

    assert [row["id"] for row in selected] == ["new_signal_a", "new_signal_b"]
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
        fields,
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
        args=Namespace(limit=0, offset=0, top_fields_by_feedback=0),
    )

    assert selected[0]["selection_reason"] == "historical_promising"


def test_unknown_field_metadata_is_retained_with_penalty() -> None:
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
        fields,
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        args=Namespace(limit=0, offset=0, top_fields_by_feedback=0),
    )

    assert {row["id"] for row in selected} == {"complete_signal", "metadata_missing"}
    assert stats["unknown_coverage_count"] == 1
    assert stats["unknown_date_coverage_count"] == 1
    assert stats["unknown_alpha_count"] == 1
    assert stats["unknown_user_count"] == 1
    scores = {row["id"]: row["selection_score"] for row in selected}
    assert scores["metadata_missing"] < scores["complete_signal"]


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
        fields,
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("fundamental6"),
        historical_state=HistoricalRunState(
            field_feedback={"one_attempt": {"best_score": 0.95, "attempted_templates": 1}}
        ),
        args=Namespace(limit=0, offset=0, top_fields_by_feedback=0),
    )

    reasons = {row["id"]: row["selection_reason"] for row in selected}
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
        fields,
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
        args=Namespace(limit=0, offset=0, top_fields_by_feedback=0),
    )

    assert selected[0]["selection_reason"] == "historical_feedback"


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
    args = Namespace(limit=1, offset=0, top_fields_by_feedback=0)

    selected, _ = prepare_fields_for_execution(
        fields,
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        args=args,
    )

    assert [row["id"] for row in selected] == ["matrix_signal"]


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
    args = Namespace(limit=2, offset=0, top_fields_by_feedback=0)

    selected, _ = prepare_fields_for_execution(
        fields,
        filters_dict=RunFilters(),
        expression_policy=get_dataset_expression_policy("new_dataset"),
        historical_state=HistoricalRunState(field_feedback={}),
        args=args,
    )

    assert [row["id"] for row in selected] == ["pcr_vol_30", "pcr_vol_60"]


def test_refresh_runtime_feedback_rebuilds_feedback_from_current_results() -> None:
    """Same-process results should be converted into fresh field/global feedback."""
    build_ctx = TemplateBuildContext(options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS))
    results = [
        FieldTestResult(
            field_id="cash_st",
            field_type="MATRIX",
            field_name="cash_st",
            template_name="group_zscore_subindustry_63",
            template_family="group_zscore",
            template_stage="group_second_order",
            status="simulated",
            submittable=False,
            expression="group_rank(ts_zscore(cash_st, 63), subindustry)",
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
        options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS),
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
    build_ctx.feedback_result_count = 1
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
