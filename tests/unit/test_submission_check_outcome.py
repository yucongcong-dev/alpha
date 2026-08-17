"""Normalized Submission Check outcome and refresh-service tests."""

from dataclasses import replace

from alpha.core.pending_check_refresh import (
    PendingCheckRefreshOptions,
    PendingCheckService,
)
from alpha.models.domain import FailedCheck, FieldTestResult
from alpha.models.result_predicates import (
    has_pending_checks,
    needs_submission_check_refresh,
)
from alpha.models.submission_check import SubmissionCheckOutcome, SubmissionCheckState


def _result(*, checks: list[FailedCheck], message: str = "checks pending") -> FieldTestResult:
    return FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="template_1",
        alpha_id="alpha_1",
        status="simulated",
        submittable=None,
        message=message,
        expression="rank(field_1)",
        failed_checks=checks,
    )


def test_mixed_failed_and_pending_observation_is_terminal_but_keeps_pending_diagnostic() -> None:
    result = _result(
        checks=[
            FailedCheck(name="LOW_SHARPE", result="FAIL"),
            FailedCheck(name="SELF_CORRELATION", result="PENDING"),
        ]
    )

    outcome = SubmissionCheckOutcome.from_result(result)

    assert outcome.state is SubmissionCheckState.FAILED
    assert outcome.needs_refresh is False
    assert has_pending_checks(result) is True
    assert needs_submission_check_refresh(result) is False


def test_unavailable_is_refreshable_but_unclassified_empty_result_is_not() -> None:
    unavailable = SubmissionCheckOutcome.from_observation(None, "checks unavailable")
    unknown = SubmissionCheckOutcome.from_observation(None, "")

    assert unavailable.state is SubmissionCheckState.UNAVAILABLE
    assert unavailable.needs_refresh is True
    assert unknown.state is SubmissionCheckState.ERROR
    assert unknown.needs_refresh is False


def test_service_terminalizes_legacy_mixed_rows_without_a_platform_request() -> None:
    service = PendingCheckService(
        object(),
        PendingCheckRefreshOptions(retries=1, max_refresh_seconds=1.0),
    )
    refreshed = service.refresh(
        [
            _result(
                checks=[
                    FailedCheck(name="LOW_SHARPE", result="FAIL"),
                    FailedCheck(name="SELF_CORRELATION", result="PENDING"),
                ]
            )
        ]
    )

    assert refreshed.resolved_count == 1
    assert refreshed.attempted_alpha_ids == frozenset()
    assert refreshed.results[0].submittable is False
    assert refreshed.results[0].message == "checks failed"
    assert [check.name for check in refreshed.results[0].failed_checks or []] == ["LOW_SHARPE"]


def test_service_refreshes_each_alpha_once_and_projects_the_observation(monkeypatch) -> None:
    calls: list[str] = []

    def _read(_client, alpha_id, _retries, **_kwargs):
        calls.append(alpha_id)
        return True, "checks passed", []

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.read_submission_status_with_retry",
        _read,
    )
    older = _result(checks=[FailedCheck(name="SELF_CORRELATION", result="PENDING")])
    newer = replace(
        older,
        field_id="field_2",
        field_name="field_2",
        updated_at="2026-08-17T00:00:00Z",
    )

    refreshed = PendingCheckService(
        object(),
        PendingCheckRefreshOptions(retries=1, max_refresh_seconds=1.0),
    ).refresh([older, newer])

    assert calls == ["alpha_1"]
    assert len(refreshed.results) == 2
    assert all(result.submittable is True for result in refreshed.results)
