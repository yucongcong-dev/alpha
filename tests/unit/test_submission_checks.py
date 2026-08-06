"""Submission-check parsing and retry tests."""

from __future__ import annotations

import pytest

from alpha.core.simulation_parsing import (
    extract_checks,
    extract_failed_checks,
    extract_pending_checks,
    is_submittable_from_checks,
)
from alpha.core.submission_checks import check_submission_with_retry
from alpha.exceptions import BrainHTTPError, BrainStopRequested, BrainTransientError
from alpha.models.domain import FailedCheck


class TestExtractChecks:
    """extract_checks function tests."""

    def test_is_checks_path(self) -> None:
        payload = {"is": {"checks": [{"name": "LOW_SHARPE", "result": "FAIL"}]}}
        assert extract_checks(payload) == [{"name": "LOW_SHARPE", "result": "FAIL"}]

    def test_top_level_checks(self) -> None:
        payload = {"checks": [{"name": "LOW_FITNESS", "result": "PASS"}]}
        assert extract_checks(payload) == [{"name": "LOW_FITNESS", "result": "PASS"}]

    def test_is_checks_over_top_level(self) -> None:
        payload = {
            "is": {"checks": [{"name": "NESTED", "result": "FAIL"}]},
            "checks": [{"name": "TOP", "result": "PASS"}],
        }
        assert extract_checks(payload) == [{"name": "NESTED", "result": "FAIL"}]

    def test_empty_payload(self) -> None:
        assert extract_checks({}) == []

    def test_is_section_not_dict(self) -> None:
        payload = {"is": "not_a_dict", "checks": [{"name": "FALLBACK"}]}
        assert extract_checks(payload) == [{"name": "FALLBACK"}]

    def test_checks_not_list(self) -> None:
        assert extract_checks({"checks": "not_a_list"}) == []

    def test_is_checks_not_list(self) -> None:
        payload = {"is": {"checks": "not_list"}, "checks": [{"name": "FALLBACK2"}]}
        assert extract_checks(payload) == [{"name": "FALLBACK2"}]


class TestExtractFailedChecks:
    """extract_failed_checks function tests."""

    def test_only_failed_checks(self) -> None:
        payload = {
            "checks": [
                {"name": "LOW_SHARPE", "result": "FAIL", "value": 0.8, "limit": 1.0},
                {"name": "LOW_FITNESS", "result": "PASS", "value": 1.2, "limit": 1.0},
            ]
        }
        result = extract_failed_checks(payload)
        assert len(result) == 1
        assert result[0].name == "LOW_SHARPE"

    def test_all_pass(self) -> None:
        payload = {"checks": [{"name": "LOW_SHARPE", "result": "PASS", "value": 1.5}]}
        assert extract_failed_checks(payload) == []

    def test_case_insensitive_fail(self) -> None:
        payload = {"checks": [{"name": "TEST", "result": "fail", "value": 0.5}]}
        assert len(extract_failed_checks(payload)) == 1

    def test_uses_threshold_when_no_limit(self) -> None:
        payload = {"checks": [{"name": "TEST", "result": "FAIL", "value": 0.5, "threshold": 1.0}]}
        assert extract_failed_checks(payload)[0].limit == 1.0

    def test_limit_over_threshold(self) -> None:
        payload = {
            "checks": [
                {
                    "name": "TEST",
                    "result": "FAIL",
                    "value": 0.5,
                    "limit": 2.0,
                    "threshold": 1.0,
                }
            ]
        }
        assert extract_failed_checks(payload)[0].limit == 2.0

    def test_no_result_field(self) -> None:
        assert extract_failed_checks({"checks": [{"name": "TEST"}]}) == []

    def test_empty_checks_payload(self) -> None:
        assert extract_failed_checks({"status": "OK"}) == []


class TestExtractPendingChecks:
    """extract_pending_checks function tests."""

    def test_only_pending_checks(self) -> None:
        payload = {
            "checks": [
                {"name": "SELF_CORRELATION", "result": "PENDING"},
                {"name": "LOW_SHARPE", "result": "PASS", "value": 1.3, "limit": 1.25},
            ]
        }
        result = extract_pending_checks(payload)
        assert len(result) == 1
        assert result[0].name == "SELF_CORRELATION"
        assert result[0].result == "PENDING"


class TestIsSubmittableFromChecks:
    """is_submittable_from_checks function tests."""

    def test_all_pass(self) -> None:
        assert is_submittable_from_checks([FailedCheck(name="LOW_SHARPE", result="PASS")]) is True

    def test_any_fail(self) -> None:
        assert (
            is_submittable_from_checks(
                [
                    FailedCheck(name="LOW_SHARPE", result="PASS"),
                    FailedCheck(name="LOW_FITNESS", result="FAIL"),
                ]
            )
            is False
        )

    def test_pending_is_unresolved(self) -> None:
        assert (
            is_submittable_from_checks([FailedCheck(name="SELF_CORRELATION", result="PENDING")])
            is None
        )

    def test_pending_takes_precedence_over_failure(self) -> None:
        assert (
            is_submittable_from_checks(
                [
                    FailedCheck(name="LOW_FITNESS", result="FAIL"),
                    FailedCheck(name="SELF_CORRELATION", result="PENDING"),
                ]
            )
            is None
        )

    def test_empty_list(self) -> None:
        assert is_submittable_from_checks([]) is None

    def test_case_insensitive(self) -> None:
        assert is_submittable_from_checks([FailedCheck(name="LOW_SHARPE", result="fail")]) is False

    def test_multiple_fail_first_wins(self) -> None:
        assert (
            is_submittable_from_checks(
                [FailedCheck(name="A", result="FAIL"), FailedCheck(name="B", result="PASS")]
            )
            is False
        )

    def test_missing_result_field_is_unresolved(self) -> None:
        assert (
            is_submittable_from_checks(
                [FailedCheck(name="A", result="PASS"), FailedCheck(name="B", result=None)]
            )
            is None
        )

    def test_unknown_result_is_unresolved(self) -> None:
        assert is_submittable_from_checks([FailedCheck(name="A", result="UNKNOWN")]) is None


class TestCheckSubmissionWithRetry:
    """check_submission_with_retry function tests."""

    def test_all_pass(self, monkeypatch) -> None:
        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                return {"is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}}

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", lambda *a, **k: a[2]())

        assert check_submission_with_retry(DummyClient(), "alpha_1", retries=3) == (
            True,
            "checks passed",
            [],
        )

    def test_stop_request_aborts_before_remote_check(self) -> None:
        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                raise AssertionError("remote check must not run after stop request")

        with pytest.raises(BrainStopRequested, match="stop was requested"):
            check_submission_with_retry(
                DummyClient(),
                "alpha_1",
                retries=3,
                should_abort=lambda: True,
            )

    def test_checks_failed(self, monkeypatch) -> None:
        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                return {
                    "is": {
                        "checks": [
                            {
                                "name": "SELF_CORRELATION",
                                "result": "FAIL",
                                "value": 0.91,
                                "limit": 0.7,
                            }
                        ]
                    }
                }

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", lambda *a, **k: a[2]())

        assert check_submission_with_retry(DummyClient(), "alpha_1", retries=3) == (
            False,
            "checks failed",
            [FailedCheck(name="SELF_CORRELATION", result="FAIL", value=0.91, limit=0.7)],
        )

    def test_failure_waits_for_unrelated_pending_checks(self, monkeypatch) -> None:
        calls = 0

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                nonlocal calls
                calls += 1
                return {
                    "is": {
                        "checks": [
                            {"name": "LOW_FITNESS", "result": "FAIL", "value": 0.9, "limit": 1.0},
                            {"name": "SELF_CORRELATION", "result": "PENDING"},
                        ]
                    }
                }

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", lambda *a, **k: a[2]())
        monkeypatch.setattr("alpha.core.submission_checks.wait_seconds", lambda *_a, **_k: None)

        result = check_submission_with_retry(DummyClient(), "alpha_1", retries=3)

        assert calls == 3
        assert result == (
            None,
            "checks pending",
            [
                FailedCheck(name="LOW_FITNESS", result="FAIL", value=0.9, limit=1.0),
                FailedCheck(name="SELF_CORRELATION", result="PENDING"),
            ],
        )

    def test_pending_checks_are_polled_until_terminal(self, monkeypatch) -> None:
        responses = iter(
            [
                {"is": {"checks": [{"name": "SELF_CORRELATION", "result": "PENDING"}]}},
                {"is": {"checks": [{"name": "SELF_CORRELATION", "result": "PASS"}]}},
            ]
        )
        waits: list[str] = []
        transport_attempts: list[int] = []

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                return next(responses)

        def _retry(_name, attempts, operation, **_kwargs):
            transport_attempts.append(attempts)
            return operation()

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", _retry)
        monkeypatch.setattr(
            "alpha.core.submission_checks.wait_seconds",
            lambda _seconds, reason, **_kwargs: waits.append(reason),
        )

        assert check_submission_with_retry(DummyClient(), "alpha_1", retries=3) == (
            True,
            "checks passed",
            [],
        )
        assert waits == ["waiting for submission checks for alpha alpha_1"]
        assert transport_attempts == [2, 2]

    def test_api_failure_remains_unresolved(self, monkeypatch) -> None:
        transport_attempts: list[int] = []
        waits: list[str] = []

        def _retry(_name, attempts, _operation, **_kwargs):
            transport_attempts.append(attempts)
            raise BrainTransientError("network unavailable")

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", _retry)
        monkeypatch.setattr(
            "alpha.core.submission_checks.wait_seconds",
            lambda _seconds, reason, **_kwargs: waits.append(reason),
        )

        assert check_submission_with_retry(object(), "alpha_1", retries=2) == (
            None,
            "checks unavailable",
            [],
        )
        assert transport_attempts == [2, 2]
        assert waits == ["waiting for submission checks for alpha alpha_1"]

    def test_permanent_http_failure_is_not_left_pending(self, monkeypatch) -> None:
        def _retry(*_args, **_kwargs):
            raise BrainHTTPError("GET /alphas/missing/check failed: 404", status=404)

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", _retry)

        with pytest.raises(BrainHTTPError) as exc_info:
            check_submission_with_retry(object(), "missing", retries=3)

        assert exc_info.value.status == 404

    def test_transient_http_failure_remains_unresolved(self, monkeypatch) -> None:
        def _retry(*_args, **_kwargs):
            raise BrainHTTPError("GET /alphas/a/check failed: 503", status=503)

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", _retry)
        monkeypatch.setattr("alpha.core.submission_checks.wait_seconds", lambda *_a, **_k: None)

        assert check_submission_with_retry(object(), "a", retries=1) == (
            None,
            "checks unavailable",
            [],
        )

    def test_unavailable_checks_are_polled_until_available(self, monkeypatch) -> None:
        responses = iter(
            [
                {},
                {"is": {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}},
            ]
        )
        waits: list[str] = []

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                return next(responses)

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", lambda *a, **k: a[2]())
        monkeypatch.setattr(
            "alpha.core.submission_checks.wait_seconds",
            lambda _seconds, reason, **_kwargs: waits.append(reason),
        )

        assert check_submission_with_retry(DummyClient(), "alpha_1", retries=3) == (
            True,
            "checks passed",
            [],
        )
        assert waits == ["waiting for submission checks for alpha alpha_1"]

    def test_unavailable_checks_stop_after_retry_budget(self, monkeypatch) -> None:
        calls = 0

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                nonlocal calls
                calls += 1
                return {}

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", lambda *a, **k: a[2]())
        monkeypatch.setattr("alpha.core.submission_checks.wait_seconds", lambda *_a, **_k: None)

        assert check_submission_with_retry(DummyClient(), "alpha_1", retries=2) == (
            None,
            "checks unavailable",
            [],
        )
        assert calls == 2

    def test_pending_checks_stop_after_retry_budget(self, monkeypatch) -> None:
        calls = 0

        class DummyClient:
            def check_alpha_submission(self, _alpha_id: str) -> dict[str, object]:
                nonlocal calls
                calls += 1
                return {"is": {"checks": [{"name": "SELF_CORRELATION", "result": "PENDING"}]}}

        monkeypatch.setattr("alpha.core.submission_checks.retry_operation", lambda *a, **k: a[2]())
        monkeypatch.setattr("alpha.core.submission_checks.wait_seconds", lambda *_a, **_k: None)

        assert check_submission_with_retry(DummyClient(), "alpha_1", retries=2) == (
            None,
            "checks pending",
            [FailedCheck(name="SELF_CORRELATION", result="PENDING")],
        )
        assert calls == 2
