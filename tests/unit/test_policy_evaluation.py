"""Adaptive-policy isolation and holdout evaluation tests."""

from __future__ import annotations

from alpha.analysis.feedback_stats import compile_failed_check_counts_by_field_type
from alpha.models.domain import FailedCheck, FieldTestResult
from alpha.policy.evaluation import (
    POLICY_ARM_ADAPTIVE,
    POLICY_ARM_HOLDOUT,
    assign_policy_arm,
    summarize_policy_evaluation,
)


def test_policy_arm_assignment_is_stable_and_supports_boundary_percentages() -> None:
    kwargs = {
        "dataset_id": "fundamental6",
        "field_id": "assets",
        "policy_version": "v1",
    }

    assert assign_policy_arm(**kwargs, holdout_percent=0) == POLICY_ARM_ADAPTIVE
    assert assign_policy_arm(**kwargs, holdout_percent=100) == POLICY_ARM_HOLDOUT
    assert assign_policy_arm(**kwargs, holdout_percent=10) == assign_policy_arm(
        **kwargs,
        holdout_percent=10,
    )


def test_failed_check_feedback_is_isolated_by_field_type() -> None:
    results = [
        FieldTestResult(
            field_id="matrix_field",
            field_type="MATRIX",
            field_name="matrix_field",
            template_name="tpl",
            failed_checks=[FailedCheck(name="LOW_SHARPE")],
        ),
        FieldTestResult(
            field_id="vector_field",
            field_type="VECTOR",
            field_name="vector_field",
            template_name="tpl",
            failed_checks=[FailedCheck(name="HIGH_TURNOVER")],
        ),
    ]

    scoped = compile_failed_check_counts_by_field_type(results)

    assert scoped["MATRIX"] == {"LOW_SHARPE": 1}
    assert scoped["VECTOR"] == {"HIGH_TURNOVER": 1}


def test_policy_evaluation_reports_rates_by_version_and_arm() -> None:
    results = [
        FieldTestResult(
            field_id="f1",
            field_type="MATRIX",
            field_name="f1",
            template_name="tpl",
            policy_version="v1",
            policy_arm=POLICY_ARM_ADAPTIVE,
            submittable=True,
        ),
        FieldTestResult(
            field_id="f2",
            field_type="MATRIX",
            field_name="f2",
            template_name="tpl",
            policy_version="v1",
            policy_arm=POLICY_ARM_ADAPTIVE,
            submittable=False,
        ),
    ]

    summary = summarize_policy_evaluation(results)

    assert summary["groups"][0]["tested"] == 2
    assert summary["groups"][0]["submittable_rate"] == 0.5
