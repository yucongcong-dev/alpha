"""Direct unit tests for feedback and field statistics."""

from __future__ import annotations

from alpha.analysis.feedback_stats import (
    compile_field_feedback,
    compile_global_failed_check_counts,
    dominant_failed_check_names,
    merge_failed_check_counts,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from alpha.analysis.field_stats import decay_field_feedback, field_priority
from alpha.config.constants import STATS_DEFAULT_SCORE
from alpha.models.domain import FieldTestResult


def _make_result(
    *,
    field_id: str = "cash_st",
    template_name: str = "ts_rank_60",
    template_family: str = "ts_rank",
    expression: str = "rank(ts_rank(cash_st, 60))",
    status: str = "simulated",
    submittable: bool = False,
    failed_checks: list[dict[str, object]] | None = None,
) -> FieldTestResult:
    return FieldTestResult(
        field_id=field_id,
        field_type="MATRIX",
        field_name=field_id,
        template_name=template_name,
        template_family=template_family,
        expression=expression,
        status=status,
        submittable=submittable,
        failed_checks=failed_checks or [],
    )


def test_compile_field_feedback_tracks_best_template() -> None:
    feedback = compile_field_feedback(
        [
            _make_result(failed_checks=[{"name": "LOW_SHARPE", "value": 0.9}]),
            _make_result(
                template_name="group_zscore_60",
                template_family="group_zscore",
                expression="group_rank(ts_zscore(cash_st, 60), subindustry)",
                failed_checks=[{"name": "LOW_SHARPE", "value": 1.1}],
            ),
        ]
    )["cash_st"]

    assert feedback["attempted_templates"] == 2
    assert feedback["best_template_name"] == "group_zscore_60"


def test_compile_field_feedback_promotes_submittable_result() -> None:
    feedback = compile_field_feedback([_make_result(submittable=True)])["cash_st"]

    assert feedback["submittable_templates"] == 1
    assert feedback["best_score"] == 1.0


def test_decay_field_feedback_does_not_mutate_history() -> None:
    summary = {"best_score": 0.8, "latest_result_at": "2024-01-01T00:00:00Z"}

    decayed = decay_field_feedback(summary, half_life_days=365)

    assert decayed is not None
    assert decayed["effective_best_score"] < summary["best_score"]
    assert summary["best_score"] == 0.8


def test_pending_self_correlation_is_not_feedback() -> None:
    feedback: dict = {}
    update_field_feedback_with_result(
        feedback,
        _make_result(
            submittable=True,
            failed_checks=[{"name": "SELF_CORRELATION", "result": "PENDING"}],
        ),
    )

    assert feedback == {}


def test_global_failed_check_counts_and_helpers() -> None:
    results = [
        _make_result(failed_checks=[{"name": "LOW_SHARPE", "value": 0.9}]),
        _make_result(
            field_id="revenue",
            failed_checks=[
                {"name": "LOW_SHARPE", "value": 0.8},
                {"name": "CONCENTRATED_WEIGHT", "value": 0.5},
            ],
        ),
    ]
    counts = compile_global_failed_check_counts(results)

    assert counts["LOW_SHARPE"] == 2
    assert dominant_failed_check_names(counts, limit=1) == {"LOW_SHARPE"}
    assert merge_failed_check_counts(counts, {"LOW_SHARPE": 1})["LOW_SHARPE"] == 3


def test_queue_timeout_does_not_update_global_failures() -> None:
    counts: dict[str, int] = {}
    result = _make_result(status="error", failed_checks=[{"name": "QUEUE_TIMEOUT"}])
    result.failed_stage = "simulation"
    result.message = "Simulation stayed queued too long"

    update_global_failed_check_counts_with_result(counts, result)

    assert counts == {}


def test_field_priority_uses_history_and_penalizes_exhausted_fields() -> None:
    assert field_priority("unknown", {}) == STATS_DEFAULT_SCORE
    assert (
        field_priority("cash_st", {"cash_st": {"best_score": 0.5, "attempted_templates": 2}}) == 0.5
    )
    assert (
        field_priority("cash_st", {"cash_st": {"best_score": 0.3, "attempted_templates": 10}}) < 0.3
    )
