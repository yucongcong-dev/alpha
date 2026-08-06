"""Runtime feedback refresh tests."""

from __future__ import annotations

from alpha.app.run_loop_feedback import refresh_runtime_feedback
from alpha.models.domain import FieldTestResult
from alpha.models.runtime import TemplateBuildContext, TemplateBuildOptions

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

    refresh = refresh_runtime_feedback(build_ctx, results, force=True)

    assert refresh.feedback_changed is True
    assert refresh.invalidate_all is True
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

    refresh = refresh_runtime_feedback(build_ctx, results)
    assert refresh.feedback_changed is True
    assert refresh.changed_field_ids == frozenset({"new_field"})
    assert refresh_runtime_feedback(build_ctx, results).feedback_changed is False

    assert build_ctx.field_feedback["seed_field"]["attempted_templates"] == 3
    assert build_ctx.field_feedback["new_field"]["attempted_templates"] == 1
    assert build_ctx.global_failed_check_counts["LOW_FITNESS"] == 2
    assert build_ctx.global_failed_check_counts["LOW_SHARPE"] == 1


def test_refresh_runtime_feedback_invalidates_retry_field_for_queue_timeout() -> None:
    build_ctx = TemplateBuildContext(options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS))
    build_ctx.feedback_result_count = 0
    results = [
        FieldTestResult(
            field_id="queued_field",
            field_type="MATRIX",
            field_name="queued_field",
            template_name="queued_template",
            status="error",
            failed_stage="simulation",
            message="simulation queued too long",
            expression="rank(queued_field)",
        )
    ]

    refresh = refresh_runtime_feedback(build_ctx, results)

    assert refresh.feedback_changed is False
    assert refresh.changed_field_ids == frozenset()
    assert refresh.retry_field_ids == frozenset({"queued_field"})
    assert build_ctx.feedback_result_count == 1
    assert build_ctx.field_feedback == {}


def test_refresh_runtime_feedback_invalidates_retry_field_for_worker_failure() -> None:
    build_ctx = TemplateBuildContext(options=TemplateBuildOptions(**_DEFAULT_SIM_SETTINGS))
    build_ctx.feedback_result_count = 0
    results = [
        FieldTestResult(
            field_id="failed_field",
            field_type="MATRIX",
            field_name="failed_field",
            template_name="seed",
            status="error",
            failed_stage="worker",
            message="connection reset",
            expression="rank(failed_field)",
        )
    ]

    refresh = refresh_runtime_feedback(build_ctx, results)

    assert refresh.feedback_changed is False
    assert refresh.changed_field_ids == frozenset()
    assert refresh.retry_field_ids == frozenset({"failed_field"})
    assert build_ctx.field_feedback == {}
