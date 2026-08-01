"""Historical pending-check reconciliation tests."""

from __future__ import annotations

from alpha.app.bootstrap_state import refresh_pending_check_results
from alpha.models.domain import FailedCheck, FieldTestResult


def _pending_result(*, alpha_id: str | None = "alpha_1") -> FieldTestResult:
    return FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="template_1",
        alpha_id=alpha_id,
        status="simulated",
        submittable=None,
        message="checks pending",
        expression="rank(field_1)",
        settings_fingerprint="settings",
        template_library_fingerprint="library",
        failed_checks=[FailedCheck(name="SELF_CORRELATION", result="PENDING")],
    )


def test_refresh_pending_check_results_replaces_terminal_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.app.bootstrap_state.checksubmit_with_retry",
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
        "alpha.app.bootstrap_state.checksubmit_with_retry",
        lambda *_args, **_kwargs: (
            None,
            "checks pending",
            [FailedCheck(name="SELF_CORRELATION", result="PENDING")],
        ),
    )

    refreshed, count = refresh_pending_check_results(object(), [original], retries=2)

    assert count == 0
    assert refreshed[0] is original


def test_refresh_pending_check_results_skips_rows_without_alpha_id(monkeypatch) -> None:
    def _unexpected(*_args, **_kwargs):
        raise AssertionError("checksubmit should not be called")

    monkeypatch.setattr(
        "alpha.app.bootstrap_state.checksubmit_with_retry",
        _unexpected,
    )

    refreshed, count = refresh_pending_check_results(
        object(),
        [_pending_result(alpha_id=None)],
        retries=2,
    )

    assert count == 0
    assert refreshed[0].alpha_id is None
