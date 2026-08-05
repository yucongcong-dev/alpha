"""Result predicate tests."""

from alpha.models.domain import FailedCheck, FieldTestResult
from alpha.models.result_predicates import (
    has_pending_checks,
    is_attempted_result,
    is_feedback_eligible_result,
    is_informative_result,
    is_retryable_infrastructure_result,
)


def test_checks_unavailable_remain_resumable() -> None:
    result = FieldTestResult(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="cashflow_op",
        template_name="template",
        status="simulated",
        submittable=None,
        message="checks unavailable",
    )

    assert has_pending_checks(result) is True


def test_pending_check_remains_resumable_even_with_terminal_flag() -> None:
    result = FieldTestResult(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="cashflow_op",
        template_name="template",
        status="simulated",
        submittable=False,
        message="checks failed",
        failed_checks=[FailedCheck(name="SELF_CORRELATION", result="PENDING")],
    )

    assert has_pending_checks(result) is True


def test_worker_failure_is_retryable_and_not_research_feedback() -> None:
    result = FieldTestResult(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="cashflow_op",
        template_name="template",
        status="error",
        submittable=False,
        failed_stage="worker",
        message="connection reset",
    )

    assert is_retryable_infrastructure_result(result) is True
    assert is_attempted_result(result) is False
    assert is_informative_result(result) is False
    assert is_feedback_eligible_result(result) is False


def test_terminal_check_error_is_attempted_but_not_quality_feedback() -> None:
    result = FieldTestResult(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="cashflow_op",
        template_name="template",
        status="error",
        submittable=False,
        failed_stage="check_submission",
        message="permanent check submission error: 404",
    )

    assert is_retryable_infrastructure_result(result) is False
    assert is_attempted_result(result) is True
    assert is_informative_result(result) is False
    assert is_feedback_eligible_result(result) is False
