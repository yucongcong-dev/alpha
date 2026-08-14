"""Historical pending-check reconciliation tests."""

from __future__ import annotations

from dataclasses import replace

from alpha.app.bootstrap_pending_checks import reconcile_pending_check_results
from alpha.config._constants_strings import STATUS_ERROR
from alpha.core.pending_check_refresh import (
    refresh_pending_check_results,
)
from alpha.exceptions import BrainHTTPError, BrainStopRequested
from alpha.models.domain import FailedCheck, FieldTestResult
from alpha.runtime.contexts import HistoricalRunState


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


def test_reconcile_pending_check_results_returns_original_state_when_unchanged(
    monkeypatch,
) -> None:
    state = HistoricalRunState(feedback_results=[_pending_result()])
    monkeypatch.setattr(
        "alpha.app.bootstrap_pending_checks.refresh_pending_check_results",
        lambda *_args, **_kwargs: (list(state.feedback_results), 0),
    )

    reconciled = reconcile_pending_check_results(
        object(),
        state,
        retries=2,
        output_file="run.json",
        feedback_output="feedback.json",
        dataset_id="fundamental6",
        settings_fingerprint="settings",
        template_library_fingerprint="library",
        run_config={},
    )

    assert reconciled is state


def test_reconcile_pending_check_results_persists_run_and_feedback_views(monkeypatch) -> None:
    original = _pending_result()
    refreshed = replace(
        original,
        submittable=True,
        message="checks passed",
        failed_checks=[],
        updated_at="2026-08-06T00:00:00Z",
    )
    state = HistoricalRunState(
        existing_results=[original],
        feedback_results=[original],
    )
    persisted: list[dict[str, object]] = []
    indexed: list[str] = []
    monkeypatch.setattr(
        "alpha.app.bootstrap_pending_checks.refresh_pending_check_results",
        lambda *_args, **_kwargs: ([refreshed], 1),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_pending_checks.persist_reconciled_historical_results",
        lambda **kwargs: persisted.append(kwargs),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_pending_checks.persist_feedback_run_index",
        indexed.append,
    )

    reconciled = reconcile_pending_check_results(
        object(),
        state,
        retries=2,
        output_file="run.json",
        feedback_output="feedback.json",
        dataset_id="fundamental6",
        settings_fingerprint="settings",
        template_library_fingerprint="library",
        run_config={"run": {"name": "test"}},
    )

    assert reconciled.existing_results == [refreshed]
    assert reconciled.feedback_results == [refreshed]
    assert [entry["output_file"] for entry in persisted] == ["run.json", "feedback.json"]
    assert all(entry["settings_fingerprint"] == "settings" for entry in persisted)
    assert indexed == ["feedback.json"]


def test_reconcile_pending_check_results_forwards_check_only_refresh_budget(monkeypatch) -> None:
    state = HistoricalRunState(feedback_results=[_pending_result()])
    received: dict[str, object] = {}

    def _refresh(*_args, **kwargs):
        received.update(kwargs)
        return list(state.feedback_results), 0

    monkeypatch.setattr(
        "alpha.app.bootstrap_pending_checks.refresh_pending_check_results",
        _refresh,
    )

    reconcile_pending_check_results(
        object(),
        state,
        retries=2,
        output_file="run.json",
        feedback_output="feedback.json",
        dataset_id="fundamental6",
        settings_fingerprint="settings",
        template_library_fingerprint="library",
        run_config={},
        refresh_limit=0,
        max_refresh_seconds=900,
        max_workers=1,
        repeat_until_terminal=True,
    )

    assert received == {
        "retries": 2,
        "refresh_limit": 0,
        "max_refresh_seconds": 900,
        "max_workers": 1,
        "repeat_until_terminal": True,
    }


def test_refresh_pending_check_results_replaces_terminal_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.check_submission_with_retry",
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
        "alpha.core.pending_check_refresh.check_submission_with_retry",
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


def test_refresh_pending_check_results_retries_pending_rows_with_backoff(monkeypatch) -> None:
    calls = 0
    waits: list[float] = []

    def _check(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None, "checks pending", [FailedCheck(name="SELF_CORRELATION", result="PENDING")]
        return True, "checks passed", []

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.check_submission_with_retry",
        _check,
    )
    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.wait_seconds",
        lambda seconds, *_args, **_kwargs: waits.append(seconds),
    )

    refreshed, count = refresh_pending_check_results(
        object(),
        [_pending_result()],
        retries=1,
        max_refresh_seconds=30,
        repeat_until_terminal=True,
    )

    assert calls == 2
    assert waits == [3.0]
    assert count == 1
    assert refreshed[0].submittable is True


def test_refresh_pending_check_results_terminalizes_permanent_http_error(monkeypatch) -> None:
    def _missing(*_args, **_kwargs):
        raise BrainHTTPError("GET /alphas/missing/check failed: 404", status=404)

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.check_submission_with_retry",
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
        "alpha.core.pending_check_refresh.check_submission_with_retry",
        _unexpected,
    )

    refreshed, count = refresh_pending_check_results(
        object(),
        [_pending_result(alpha_id=None)],
        retries=2,
    )

    assert count == 0
    assert refreshed[0].alpha_id is None


def test_refresh_pending_check_results_recovers_stale_terminal_flag(monkeypatch) -> None:
    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.check_submission_with_retry",
        lambda *_args, **_kwargs: (True, "checks passed", []),
    )

    original = _pending_result(submittable=False)
    refreshed, count = refresh_pending_check_results(object(), [original], retries=2)

    assert count == 1
    assert refreshed[0].submittable is True
    assert refreshed[0].message == "checks passed"
    assert refreshed[0].failed_checks == []


def test_refresh_pending_check_results_respects_startup_budget(monkeypatch) -> None:
    calls = 0

    def _resolve(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return True, "checks passed", []

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.check_submission_with_retry",
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

    def _pending(_client, alpha_id, _retries, **_kwargs):
        checked_alpha_ids.append(alpha_id)
        return None, "checks pending", [FailedCheck(name="SELF_CORRELATION", result="PENDING")]

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.check_submission_with_retry",
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
    clock = {"now": 0.0}

    def _pending(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return None, "checks pending", []

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.check_submission_with_retry",
        _pending,
    )
    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.time.monotonic",
        lambda: clock["now"],
    )

    def _complete_first_batch(futures, timeout=None):
        del timeout
        clock["now"] = 31.0
        return {next(iter(futures))}, set()

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.wait",
        _complete_first_batch,
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


def test_refresh_pending_check_results_aborts_retry_at_deadline(monkeypatch) -> None:
    clock = {"now": 0.0}
    callbacks = []
    original = _pending_result()

    def _deadline_abort(_client, _alpha_id, _retries, *, should_abort=None):
        callbacks.append(should_abort)
        clock["now"] = 31.0
        assert should_abort is not None and should_abort()
        raise BrainStopRequested("startup refresh deadline reached")

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.check_submission_with_retry",
        _deadline_abort,
    )
    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.time.monotonic",
        lambda: clock["now"],
    )

    refreshed, count = refresh_pending_check_results(
        object(),
        [original],
        retries=3,
        max_refresh_seconds=30.0,
    )

    assert len(callbacks) == 1
    assert count == 0
    assert refreshed == [original]
    assert refreshed[0].updated_at == ""


def test_refresh_pending_check_results_joins_timed_out_batch_before_returning(monkeypatch) -> None:
    executors = []

    class _SlowFuture:
        def __init__(self, result):
            self._result = result
            self.cancelled = False

        def result(self):
            raise AssertionError("slow future must not be consumed after timeout")

        def cancel(self):
            self.cancelled = True
            return True

    class _Executor:
        future = None

        def __init__(self, **_kwargs):
            self.future = _SlowFuture(None)
            self.shutdown_calls: list[dict[str, bool]] = []
            executors.append(self)

        def submit(self, *_args, **_kwargs):
            return self.future

        def shutdown(self, **_kwargs):
            self.shutdown_calls.append(_kwargs)

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.ThreadPoolExecutor",
        _Executor,
    )
    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.wait",
        lambda futures, timeout=None: (set(), set(futures)),
    )

    original = _pending_result()
    refreshed, count = refresh_pending_check_results(
        object(),
        [original],
        retries=1,
        max_refresh_seconds=30.0,
    )

    assert refreshed == [original]
    assert count == 0
    assert executors[0].shutdown_calls == [{"wait": True, "cancel_futures": True}]


def test_refresh_pending_check_results_uses_worker_factory_for_parallel_checks(monkeypatch) -> None:
    clients: list[object] = []
    deadlines: list[float | None] = []

    class _Factory:
        def get_client(self, *, request_deadline=None):
            client = object()
            clients.append(client)
            deadlines.append(request_deadline)
            return client

    checked_clients: list[object] = []

    def _resolve(client, _alpha_id, _retries, **_kwargs):
        checked_clients.append(client)
        return True, "checks passed", []

    monkeypatch.setattr(
        "alpha.core.pending_check_refresh.check_submission_with_retry",
        _resolve,
    )

    refreshed, count = refresh_pending_check_results(
        _Factory(),
        [_pending_result(alpha_id="alpha_0"), _pending_result(alpha_id="alpha_1")],
        retries=1,
        refresh_limit=0,
        max_refresh_seconds=30,
        max_workers=2,
    )

    assert count == 2
    assert all(result.submittable is True for result in refreshed)
    assert len(clients) == 2
    assert set(checked_clients) == set(clients)
    assert len(set(deadlines)) == 1
    assert deadlines[0] is not None
