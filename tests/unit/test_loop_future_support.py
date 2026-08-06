"""Future submission and remote simulation resume tests."""

from __future__ import annotations

from concurrent.futures import Future
from threading import Semaphore
from types import SimpleNamespace
from unittest.mock import patch

from alpha.app.loop_future_support import (
    cancel_unstarted_futures,
    submit_resumable_futures,
    submit_template_future,
    wait_for_inflight_simulation_metadata,
)
from alpha.models import ExecutionState, PendingFutureContext
from alpha.models.domain import FieldTestResult, SettingsVariant, TemplateField
from tests.unit.simulation_config_support import build_simulation_stage_config


def _execution_state() -> ExecutionState:
    return ExecutionState.create()


class _ImmediateExecutor:
    def submit(self, function, *args):
        future: Future[FieldTestResult] = Future()
        future.set_result(function(*args))
        return future


class _RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[object, ...]]] = []

    def submit(self, function, *args):
        self.calls.append((function, args))
        return Future()


class _FailingExecutor(_RecordingExecutor):
    def submit(self, function, *args):
        if self.calls:
            raise RuntimeError("executor unavailable")
        return super().submit(function, *args)


def test_cancel_unstarted_futures_preserves_running_simulations() -> None:
    execution_state = _execution_state()
    queued: Future[FieldTestResult] = Future()
    running: Future[FieldTestResult] = Future()
    assert running.set_running_or_notify_cancel() is True
    queued_context = PendingFutureContext(field_id="queued")
    running_context = PendingFutureContext(
        field_id="running",
        simulation_location="/simulations/sim-1",
    )
    execution_state.future_queue.pending_futures = {
        queued: queued_context,
        running: running_context,
    }

    cancelled = cancel_unstarted_futures(execution_state)

    assert cancelled == 1
    assert queued.cancelled() is True
    assert execution_state.future_queue.pending_futures == {running: running_context}


def test_wait_for_inflight_simulation_metadata_observes_created_location(monkeypatch) -> None:
    execution_state = _execution_state()
    running: Future[FieldTestResult] = Future()
    assert running.set_running_or_notify_cancel() is True
    context = PendingFutureContext(field_id="running")
    execution_state.future_queue.pending_futures = {running: context}
    monotonic_values = iter([0.0, 0.0, 0.1])

    monkeypatch.setattr(
        "alpha.app.loop_future_support.time.monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(
        "alpha.app.loop_future_support.time.sleep",
        lambda _seconds: setattr(context, "simulation_location", "/simulations/sim-1"),
    )

    assert wait_for_inflight_simulation_metadata(execution_state, timeout_seconds=1.0) == 0


def test_wait_for_inflight_simulation_metadata_waits_without_default_timeout(monkeypatch) -> None:
    execution_state = _execution_state()
    running: Future[FieldTestResult] = Future()
    assert running.set_running_or_notify_cancel() is True
    context = PendingFutureContext(field_id="running")
    execution_state.future_queue.pending_futures = {running: context}

    monkeypatch.setattr(
        "alpha.app.loop_future_support.time.monotonic",
        lambda: (_ for _ in ()).throw(AssertionError("default wait must not create a deadline")),
    )
    monkeypatch.setattr(
        "alpha.app.loop_future_support.time.sleep",
        lambda _seconds: setattr(context, "simulation_location", "/simulations/sim-1"),
    )

    assert wait_for_inflight_simulation_metadata(execution_state) == 0


def test_wait_for_inflight_simulation_metadata_reports_timeout(monkeypatch) -> None:
    execution_state = _execution_state()
    running: Future[FieldTestResult] = Future()
    assert running.set_running_or_notify_cancel() is True
    context = PendingFutureContext(field_id="running")
    execution_state.future_queue.pending_futures = {running: context}
    monotonic_values = iter([0.0, 0.0, 1.0])

    monkeypatch.setattr(
        "alpha.app.loop_future_support.time.monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr("alpha.app.loop_future_support.time.sleep", lambda _seconds: None)

    assert wait_for_inflight_simulation_metadata(execution_state, timeout_seconds=0.5) == 1


def test_submit_template_future_records_created_simulation_location() -> None:
    execution_state = _execution_state()
    run_ctx = SimpleNamespace(
        client_factory=object(),
        template_library_fingerprint="library-v1",
        create_semaphore=Semaphore(1),
    )
    field = TemplateField(
        field_id="f1",
        field_name="Field 1",
        field_type="MATRIX",
        metadata={"id": "f1", "name": "Field 1", "type": "MATRIX"},
    )

    def _worker(*args):
        on_created = args[-1]
        on_created("/simulations/sim-1", "sim-1")
        return FieldTestResult(
            field_id="f1",
            field_type="MATRIX",
            field_name="Field 1",
            template_name="base",
            expression="rank(f1)",
        )

    with patch("alpha.app.loop_future_support.run_field_test_in_worker", side_effect=_worker):
        submit_template_future(
            executor=_ImmediateExecutor(),  # type: ignore[arg-type]
            run_ctx=run_ctx,  # type: ignore[arg-type]
            execution_state=execution_state,
            simulation_config=build_simulation_stage_config(),
            field=field,
            field_id="f1",
            field_name="Field 1",
            field_type="MATRIX",
            template_name="base",
            template_family="base",
            template_stage="generate",
            template_role="signal",
            template_activation_scope="dataset",
            expression="rank(f1)",
            settings_variant=SettingsVariant(),
            variant_fingerprint="settings-v1",
        )

    pending = next(iter(execution_state.future_queue.pending_futures.values()))
    assert pending.simulation_location == "/simulations/sim-1"
    assert pending.simulation_id == "sim-1"


def test_submit_resumable_futures_registers_restored_contexts() -> None:
    execution_state = _execution_state()
    pending = PendingFutureContext(
        field_id="f1",
        field_name="Field 1",
        field_type="MATRIX",
        template_name="base",
        expression="rank(f1)",
        settings_fingerprint="settings-v1",
        simulation_location="/simulations/sim-1",
        simulation_id="sim-1",
    )
    execution_state.future_queue.replace_resumable_batch([pending])
    executor = _RecordingExecutor()
    run_ctx = SimpleNamespace(
        client_factory=object(),
        template_library_fingerprint="library-v1",
    )

    scheduled = submit_resumable_futures(
        executor=executor,  # type: ignore[arg-type]
        run_ctx=run_ctx,  # type: ignore[arg-type]
        execution_state=execution_state,
        simulation_config=build_simulation_stage_config(),
    )

    assert scheduled == 1
    assert execution_state.future_queue.resumable_simulations == []
    assert list(execution_state.future_queue.pending_futures.values()) == [pending]
    assert len(executor.calls) == 1
    assert executor.calls[0][1][-1]() is False


def test_submit_resumable_futures_restores_unsubmitted_contexts_on_failure() -> None:
    execution_state = _execution_state()
    first = PendingFutureContext(
        field_id="f1",
        template_name="base",
        expression="rank(f1)",
        settings_fingerprint="settings-v1",
        simulation_location="/simulations/sim-1",
    )
    second = PendingFutureContext(
        field_id="f2",
        template_name="base",
        expression="rank(f2)",
        settings_fingerprint="settings-v1",
        simulation_location="/simulations/sim-2",
    )
    execution_state.future_queue.replace_resumable_batch([first, second])
    executor = _FailingExecutor()
    run_ctx = SimpleNamespace(
        client_factory=object(),
        template_library_fingerprint="library-v1",
    )

    try:
        submit_resumable_futures(
            executor=executor,  # type: ignore[arg-type]
            run_ctx=run_ctx,  # type: ignore[arg-type]
            execution_state=execution_state,
            simulation_config=build_simulation_stage_config(),
        )
    except RuntimeError as exc:
        assert "executor unavailable" in str(exc)
    else:
        raise AssertionError("executor failure should propagate")

    assert list(execution_state.future_queue.pending_futures.values()) == [first]
    assert execution_state.future_queue.resumable_simulations == [second]
