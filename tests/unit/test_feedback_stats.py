"""Direct unit tests for feedback_stats, field_stats, historical_reuse, and adaptive priority."""

from __future__ import annotations

from alpha.analysis.feedback_stats import (
    compile_field_feedback,
    compile_global_failed_check_counts,
    dominant_failed_check_names,
    merge_failed_check_counts,
    update_field_feedback_with_result,
    update_global_failed_check_counts_with_result,
)
from alpha.analysis.field_stats import field_priority
from alpha.config.constants import (
    FEEDBACK_STAGE_RESIMULATE,
    STATS_DEFAULT_SCORE,
)
from alpha.generators.templates.feedback_mutations import build_feedback_mutations
from alpha.generators.templates.historical_reuse import build_historical_reuse_templates
from alpha.generators.templates.priority import adaptive_template_priority_adjustment
from alpha.models.domain import FieldTestResult
from alpha.policy.expression import get_dataset_expression_policy


def _make_result(
    *,
    field_id: str = "cash_st",
    field_name: str = "cash_st",
    template_name: str = "ts_rank_63",
    template_family: str = "ts_rank",
    template_stage: str = "first_order",
    expression: str = "rank(ts_rank(cash_st, 63))",
    status: str = "simulated",
    submittable: bool = False,
    failed_checks: list[dict[str, object]] | None = None,
) -> FieldTestResult:
    return FieldTestResult(
        field_id=field_id,
        field_type="MATRIX",
        field_name=field_name,
        template_name=template_name,
        template_family=template_family,
        template_stage=template_stage,
        expression=expression,
        status=status,
        submittable=submittable,
        failed_checks=failed_checks or [],
    )


# ---- compile_field_feedback / update_field_feedback_with_result ----


def test_compile_field_feedback_tracks_best_score_and_template_info() -> None:
    results = [
        _make_result(
            failed_checks=[{"name": "LOW_SHARPE", "value": 0.9, "limit": 1.25}],
        ),
        _make_result(
            template_name="group_zscore_63",
            template_family="group_zscore",
            template_stage="group_second_order",
            expression="group_rank(ts_zscore(cash_st, 63), subindustry)",
            failed_checks=[{"name": "LOW_SHARPE", "value": 1.1, "limit": 1.25}],
        ),
    ]
    feedback = compile_field_feedback(results)
    summary = feedback["cash_st"]
    assert summary["attempted_templates"] == 2
    assert summary["best_template_name"] == "group_zscore_63"
    assert summary["best_template_family"] == "group_zscore"
    assert summary["best_expression"] == "group_rank(ts_zscore(cash_st, 63), subindustry)"
    assert summary["failed_check_counts"]["LOW_SHARPE"] == 2


def test_update_field_feedback_includes_self_correlation_pending() -> None:
    feedback: dict = {}
    result = _make_result(
        status="simulated",
        submittable=True,
        failed_checks=[{"name": "SELF_CORRELATION", "result": "PENDING", "value": None, "limit": None}],
    )
    update_field_feedback_with_result(feedback, result)
    assert "cash_st" in feedback
    assert feedback["cash_st"]["attempted_templates"] == 1


def test_update_field_feedback_non_simulated_increments_attempted_only() -> None:
    feedback: dict = {}
    result = _make_result(
        status="error",
        failed_checks=[{"name": "LOW_SHARPE", "value": 0.5}],
    )
    update_field_feedback_with_result(feedback, result)
    summary = feedback["cash_st"]
    assert summary["attempted_templates"] == 1
    assert summary["best_score"] == STATS_DEFAULT_SCORE
    assert summary["best_expression"] == ""


# ---- compile_global_failed_check_counts ----


def test_compile_global_failed_check_counts_aggregates_across_results() -> None:
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
    assert counts["CONCENTRATED_WEIGHT"] == 1


def test_update_global_failed_check_counts_skips_queue_timeout() -> None:
    counts: dict[str, int] = {}
    result = _make_result(
        status="error",
        failed_checks=[{"name": "QUEUE_TIMEOUT", "value": None}],
    )
    result.failed_stage = "simulation"
    result.message = "Simulation stayed queued too long"
    update_global_failed_check_counts_with_result(counts, result)
    assert counts == {}


# ---- dominant_failed_check_names ----


def test_dominant_failed_check_names_returns_top_n() -> None:
    counts = {"LOW_SHARPE": 5, "LOW_FITNESS": 3, "CONCENTRATED_WEIGHT": 1, "LOW_TURNOVER": 0}
    dominant = dominant_failed_check_names(counts, limit=2)
    assert dominant == {"LOW_SHARPE", "LOW_FITNESS"}


# ---- merge_failed_check_counts ----


def test_merge_failed_check_counts_sums_and_skips_non_int() -> None:
    merged = merge_failed_check_counts(
        {"LOW_SHARPE": 2, "LOW_FITNESS": 1},
        {"LOW_SHARPE": 3, "BAD": "not_int"},
    )
    assert merged == {"LOW_SHARPE": 5, "LOW_FITNESS": 1}


# ---- field_priority ----


def test_field_priority_returns_default_for_unknown_field() -> None:
    assert field_priority("unknown", {}) == STATS_DEFAULT_SCORE


def test_field_priority_returns_best_score_for_few_attempts() -> None:
    feedback = {"cash_st": {"best_score": 0.5, "attempted_templates": 2}}
    assert field_priority("cash_st", feedback) == 0.5


def test_field_priority_penalizes_high_attempts_low_score() -> None:
    feedback = {"cash_st": {"best_score": 0.3, "attempted_templates": 10}}
    priority = field_priority("cash_st", feedback)
    assert priority < 0.3


# ---- build_historical_reuse_templates ----


def test_build_historical_reuse_returns_empty_in_generate_stage() -> None:
    feedback = {"best_score": 0.5, "best_expression": "rank(cash_st)"}
    templates = build_historical_reuse_templates(
        "cash_st",
        feedback,
        feedback_stage="generate",
    )
    assert templates == []


def test_build_historical_reuse_returns_empty_for_low_score() -> None:
    feedback = {"best_score": -1.0, "best_expression": "rank(cash_st)"}
    templates = build_historical_reuse_templates(
        "cash_st",
        feedback,
        feedback_stage=FEEDBACK_STAGE_RESIMULATE,
    )
    assert templates == []


def test_build_historical_reuse_generates_wrappers_for_high_score() -> None:
    feedback = {"best_score": 0.5, "best_expression": "rank(cash_st)"}
    templates = build_historical_reuse_templates(
        "cash_st",
        feedback,
        feedback_stage=FEEDBACK_STAGE_RESIMULATE,
    )
    names = {t.name for t in templates}
    expressions = {t.expression for t in templates}
    assert any("iter_reuse_best" in name for name in names)
    assert any("group_neutralize(" in expr for expr in expressions)
    assert any("group_rank(" in expr for expr in expressions)


# ---- build_feedback_mutations ----


def test_build_feedback_mutations_returns_base_in_generate_stage() -> None:
    """In generate stage, base mutations are returned even without field feedback."""
    templates = build_feedback_mutations(
        "cash_st",
        None,
        feedback_stage="generate",
    )
    assert len(templates) > 0


def test_build_feedback_mutations_returns_empty_for_non_generate_without_feedback() -> None:
    """Outside generate stage with no feedback, no mutations are produced."""
    templates = build_feedback_mutations(
        "cash_st",
        None,
        feedback_stage=FEEDBACK_STAGE_RESIMULATE,
    )
    assert templates == []


def test_build_feedback_mutations_generates_mutations_in_resimulate() -> None:
    policy = get_dataset_expression_policy("fundamental6")
    feedback = {
        "best_score": 0.5,
        "best_expression": "rank(cash_st)",
        "failed_check_counts": {"LOW_SHARPE": 2},
    }
    templates = build_feedback_mutations(
        "cash_st",
        feedback,
        expression_policy=policy,
        feedback_stage=FEEDBACK_STAGE_RESIMULATE,
    )
    assert len(templates) > 0


# ---- adaptive_template_priority_adjustment ----


def test_adaptive_priority_returns_zero_for_no_feedback_and_no_failures() -> None:
    adj = adaptive_template_priority_adjustment(
        "ts_rank_63",
        "rank(ts_rank(cash_st, 63))",
        field_feedback=None,
        global_failed_check_counts={},
    )
    assert adj == 0


def test_adaptive_priority_boosts_vol_scaled_delta_family() -> None:
    adj = adaptive_template_priority_adjustment(
        "vol_scaled_delta_20",
        "ts_delta(cash_st, 20) / ts_std_dev(cash_st, 60)",
        field_feedback={"best_score": 0.5, "failed_check_counts": {}},
        global_failed_check_counts={},
    )
    assert adj < 0


def test_adaptive_priority_penalizes_legacy_ratio_with_high_score() -> None:
    adj = adaptive_template_priority_adjustment(
        "ratio_template",
        "ratio(cash_st, revenue)",
        field_feedback={"best_score": 0.8, "failed_check_counts": {}},
        global_failed_check_counts={},
    )
    assert adj <= 0
