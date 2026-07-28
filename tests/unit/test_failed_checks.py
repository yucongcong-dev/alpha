"""Failed-check scoring and research hint tests."""

from __future__ import annotations

import pytest

from alpha.analysis.failed_checks import (
    compile_failed_check_leaderboard,
    compile_near_pass_summary,
    compile_optimization_hints,
    failed_check_closeness,
    failed_check_gap,
    score_failed_checks,
    summarize_failed_check,
)
from alpha.models.domain import FailedCheck, FieldTestResult


def _result(
    field_id: str,
    template_name: str,
    checks: list[FailedCheck],
    *,
    alpha_id: str | None = None,
    status: str = "simulated",
    submittable: bool = False,
) -> FieldTestResult:
    return FieldTestResult(
        field_id=field_id,
        field_type="MATRIX",
        field_name=field_id,
        template_name=template_name,
        alpha_id=alpha_id,
        status=status,
        submittable=submittable,
        expression=f"rank({field_id})",
        failed_checks=checks,
    )


def test_failed_check_gap_and_closeness_handle_both_threshold_directions() -> None:
    low = FailedCheck(name="LOW_SHARPE", value=1.0, limit=1.25)
    high = FailedCheck(name="HIGH_TURNOVER", value=0.8, limit=0.7)

    assert failed_check_gap(low) == 0.25
    assert failed_check_closeness(low) == 0.8
    assert failed_check_gap(high) == pytest.approx(0.1)
    assert failed_check_closeness(high) == pytest.approx(1.0 - (0.1 / 0.7))


def test_failed_check_closeness_is_clamped_and_missing_values_are_ignored() -> None:
    assert failed_check_closeness(FailedCheck(name="LOW_SHARPE", value=2.0, limit=1.0)) == 1.0
    assert failed_check_closeness(FailedCheck(name="LOW_SHARPE", value=-2.0, limit=1.0)) == 0.0
    assert failed_check_closeness(FailedCheck(name="LOW_SHARPE", value=None, limit=1.0)) is None
    assert failed_check_gap(FailedCheck(name="LOW_SHARPE", value=1.0, limit=None)) is None
    assert score_failed_checks([]) == -10.0
    assert score_failed_checks([FailedCheck(name="UNKNOWN")]) == -10.0


def test_summarize_failed_check_exposes_gap_and_closeness() -> None:
    summary = summarize_failed_check(FailedCheck(name="LOW_FITNESS", value=0.8, limit=1.0))

    assert summary["name"] == "LOW_FITNESS"
    assert summary["value"] == 0.8
    assert summary["limit"] == 1.0
    assert summary["gap"] == pytest.approx(0.2)
    assert summary["closeness"] == pytest.approx(0.8)


def test_leaderboard_sorts_zero_closeness_ahead_of_missing_score() -> None:
    results = [
        _result("unknown", "template", [FailedCheck(name="A_UNKNOWN")], alpha_id="same"),
        _result(
            "zero",
            "template",
            [FailedCheck(name="Z_ZERO", value=2.0, limit=1.0)],
            alpha_id="same",
        ),
    ]

    leaderboard = compile_failed_check_leaderboard(results)

    assert [row["name"] for row in leaderboard] == ["Z_ZERO", "A_UNKNOWN"]
    assert leaderboard[0]["avg_closeness"] == 0.0
    assert leaderboard[1]["avg_closeness"] is None


def test_leaderboard_aggregates_values_and_deduplicates_example_ids() -> None:
    results = [
        _result(
            f"field-{index}",
            "template",
            [FailedCheck(name="LOW_SHARPE", value=0.5 + index / 10, limit=1.0)],
            alpha_id="duplicate" if index < 2 else f"alpha-{index}",
        )
        for index in range(8)
    ]

    row = compile_failed_check_leaderboard(results)[0]

    assert row["count"] == 8
    assert row["avg_limit"] == 1.0
    assert row["avg_gap"] is not None
    assert len(row["example_alpha_ids"]) == 5
    assert row["example_alpha_ids"].count("duplicate") == 1


def test_near_pass_summary_sorts_candidates_and_rejects_nonpositive_limit() -> None:
    results = [
        _result(
            "far",
            "z-template",
            [FailedCheck(name="LOW_SHARPE", value=0.2, limit=1.0)],
            alpha_id="far-alpha",
        ),
        _result(
            "near",
            "a-template",
            [FailedCheck(name="LOW_SHARPE", value=0.9, limit=1.0)],
            alpha_id="near-alpha",
        ),
        _result(
            "passed",
            "passed-template",
            [FailedCheck(name="LOW_SHARPE", value=0.9, limit=1.0)],
            submittable=True,
        ),
    ]

    assert compile_near_pass_summary(results, limit=0) == []
    assert compile_near_pass_summary(results, limit=-1) == []
    rows = compile_near_pass_summary(results, limit=1)
    assert len(rows) == 1
    assert rows[0]["field_id"] == "near"
    assert rows[0]["failed_checks"][0]["name"] == "LOW_SHARPE"


def test_optimization_hints_cover_known_failures_nearpass_and_fallback() -> None:
    leaderboard = [
        {"name": "LOW_SHARPE"},
        {"name": "LOW_FITNESS"},
        {"name": "LOW_TURNOVER"},
    ]
    nearpass = [{"field_id": "cash", "template_name": "rank", "score": 0.75}]

    hints = compile_optimization_hints(leaderboard, nearpass)

    assert any("夏普比率" in hint for hint in hints)
    assert any("适应性" in hint for hint in hints)
    assert any("换手率过低" in hint for hint in hints)
    assert any("最佳接近通过候选" in hint for hint in hints)
    assert compile_optimization_hints([], []) == ["还没有失败检查记录；先运行更广泛的探索样本。"]
    assert "扩大样本" in compile_optimization_hints([{"name": "UNKNOWN"}], [])[0]


def test_optimization_hints_cover_turnover_and_concentration() -> None:
    hints = compile_optimization_hints(
        [
            {"name": "HIGH_TURNOVER"},
            {"name": "CONCENTRATED_WEIGHT"},
            {"name": "LOW_SUB_UNIVERSE_SHARPE"},
        ],
        [],
    )

    assert any("换手率过高" in hint for hint in hints)
    assert any("权重集中度" in hint for hint in hints)
    assert any("夏普比率" in hint for hint in hints)
