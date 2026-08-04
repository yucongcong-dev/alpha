"""Historical pending-check reconciliation tests."""

from __future__ import annotations

from alpha.app.bootstrap_state import refresh_pending_check_results
from alpha.config.constants import STATUS_ERROR
from alpha.exceptions import BrainHTTPError
from alpha.models.domain import FailedCheck, FieldTestResult


def _pending_result(
    *,
    alpha_id: str | None = "alpha_1",
    submittable: bool | None = None,
) -> FieldTestResult:
    return FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="template_1",
        alpha_id=alpha_id,
        status="simulated",
        submittable=submittable,
        message="checks pending",
        expression="rank(field_1)",
        settings_fingerprint="settings",
        template_library_fingerprint="library",
        failed_checks=[FailedCheck(name="SELF_CORRELATION", result="PENDING")],
    )


def test_refresh_pending_check_results_replaces_terminal_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.app.bootstrap_state.check_submission_with_retry",
        lambda *_args, **_kwargs: (True, "checks passed", []),
    )

    refreshed, count = refresh_pending_check_results(object(), [_pending_result()], retries=3)

    assert count == 1
    assert refreshed[0].submittable is True
    assert refreshed[0].message == "checks passed"
    assert refreshed[0].failed_checks == []


def test_refresh_pending_check_results_keeps_still_pending_result(monkeypatch) -> None:
    original = _pending_result()
    monkeypatch.setattr(
        "alpha.app.bootstrap_state.check_submission_with_retry",
        lambda *_args, **_kwargs: (
            None,
            "checks pending",
            [FailedCheck(name="SELF_CORRELATION", result="PENDING")],
        ),
    )

    refreshed, count = refresh_pending_check_results(object(), [original], retries=2)

    assert count == 0
    assert refreshed[0].submittable is None
    assert refreshed[0].updated_at


def test_refresh_pending_check_results_terminalizes_permanent_http_error(monkeypatch) -> None:
    def _missing(*_args, **_kwargs):
        raise BrainHTTPError("GET /alphas/missing/check failed: 404", status=404)

    monkeypatch.setattr(
        "alpha.app.bootstrap_state.check_submission_with_retry",
        _missing,
    )

    refreshed, count = refresh_pending_check_results(object(), [_pending_result()], retries=2)

    assert count == 1
    assert refreshed[0].status == STATUS_ERROR
    assert refreshed[0].submittable is False
    assert refreshed[0].failed_stage == "check_submission"
    assert refreshed[0].failed_checks == []
    assert "404" in refreshed[0].message


def test_refresh_pending_check_results_skips_rows_without_alpha_id(monkeypatch) -> None:
    def _unexpected(*_args, **_kwargs):
        raise AssertionError("check_submission should not be called")

    monkeypatch.setattr(
        "alpha.app.bootstrap_state.check_submission_with_retry",
        _unexpected,
    )

    refreshed, count = refresh_pending_check_results(
        object(),
        [_pending_result(alpha_id=None)],
        retries=2,
    )

    assert count == 0
    assert refreshed[0].alpha_id is None


def test_refresh_pending_check_results_skips_terminal_failure(monkeypatch) -> None:
    def _unexpected(*_args, **_kwargs):
        raise AssertionError("check_submission should not be called")

    monkeypatch.setattr(
        "alpha.app.bootstrap_state.check_submission_with_retry",
        _unexpected,
    )

    original = _pending_result(submittable=False)
    refreshed, count = refresh_pending_check_results(object(), [original], retries=2)

    assert count == 0
    assert refreshed[0] is original


def test_refresh_pending_check_results_respects_startup_budget(monkeypatch) -> None:
    calls = 0

    def _resolve(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return True, "checks passed", []

    monkeypatch.setattr(
        "alpha.app.bootstrap_state.check_submission_with_retry",
        _resolve,
    )
    originals = [_pending_result(alpha_id=f"alpha_{index}") for index in range(3)]

    refreshed, count = refresh_pending_check_results(
        object(),
        originals,
        retries=2,
        refresh_limit=1,
    )

    assert calls == 1
    assert count == 1
    assert refreshed[0].submittable is True
    assert refreshed[1:] == originals[1:]


def test_refresh_pending_check_results_rotates_oldest_attempts(monkeypatch) -> None:
    checked_alpha_ids: list[str] = []

    def _pending(_client, alpha_id, _retries):
        checked_alpha_ids.append(alpha_id)
        return None, "checks pending", [FailedCheck(name="SELF_CORRELATION", result="PENDING")]

    monkeypatch.setattr(
        "alpha.app.bootstrap_state.check_submission_with_retry",
        _pending,
    )
    originals = [_pending_result(alpha_id=f"alpha_{index}") for index in range(3)]

    first_results, _ = refresh_pending_check_results(
        object(),
        originals,
        retries=1,
        refresh_limit=1,
    )
    second_results, _ = refresh_pending_check_results(
        object(),
        first_results,
        retries=1,
        refresh_limit=1,
    )

    assert checked_alpha_ids == ["alpha_0", "alpha_1"]
    assert first_results[0].updated_at
    assert second_results[1].updated_at


def test_refresh_pending_check_results_respects_total_time_budget(monkeypatch) -> None:
    calls = 0
    monotonic_values = iter([0.0, 0.0, 31.0])

    def _pending(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return None, "checks pending", []

    monkeypatch.setattr(
        "alpha.app.bootstrap_state.check_submission_with_retry",
        _pending,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_state.time.monotonic",
        lambda: next(monotonic_values),
    )

    refreshed, count = refresh_pending_check_results(
        object(),
        [_pending_result(alpha_id="alpha_0"), _pending_result(alpha_id="alpha_1")],
        retries=1,
        refresh_limit=10,
        max_refresh_seconds=30.0,
    )

    assert calls == 1
    assert count == 0
    assert refreshed[0].updated_at
    assert refreshed[1].updated_at == ""
