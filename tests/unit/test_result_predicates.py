"""Result predicate tests."""

from alpha.models.domain import FailedCheck, FieldTestResult
from alpha.models.result_predicates import has_pending_checks


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


def test_terminal_result_ignores_stale_pending_check() -> None:
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

    assert has_pending_checks(result) is False
