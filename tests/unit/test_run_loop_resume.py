"""run_loop resume and persistence boundary tests."""

from __future__ import annotations

import argparse
from concurrent.futures import Future
from functools import partial
import json
from threading import Semaphore
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from alpha.app.loop_future_support import (
    drain_next_completion,
    drain_remaining_futures,
)
from alpha.app.run_loop import run_field_test_loop
from alpha.app.run_loop_resume import (
    persist_replanning_checkpoint as _persist_replanning_checkpoint,
)
from alpha.app.run_loop_resume import (
    restore_fields_from_state as _restore_fields_from_state,
)
from alpha.app.run_loop_resume import (
    save_runtime_checkpoint as _save_runtime_checkpoint,
)
from alpha.app.run_loop_resume import (
    save_terminal_pipeline_state as _save_terminal_pipeline_state,
)
from alpha.app.run_loop_rounds import ScheduleRoundResult
from alpha.config.application import ApplicationConfig
from alpha.models.domain import TemplateField
from alpha.models.io_types import RunFilters, RunPaths
from alpha.models.runtime_options import ResultWriteOptions, SchedulerControlOptions
from alpha.runtime.concurrency import RuntimeConcurrencyState
from alpha.runtime.contexts import (
    CheckpointIdentity,
    FutureCompletionContext,
    HistoricalRunState,
)
from alpha.runtime.state import ExecutionState, InitializedRunContext

IDENTITY = CheckpointIdentity("run-fp")
persist_replanning_checkpoint = partial(_persist_replanning_checkpoint, identity=IDENTITY)
restore_fields_from_state = partial(_restore_fields_from_state, identity=IDENTITY)
save_runtime_checkpoint = partial(_save_runtime_checkpoint, identity=IDENTITY)
save_terminal_pipeline_state = partial(_save_terminal_pipeline_state, identity=IDENTITY)


def _checkpoint_json(completed_field_index: int) -> str:
    return json.dumps(
        {
            "version": 3,
            "run_fingerprint": IDENTITY.run_fingerprint,
            "completed_field_index": completed_field_index,
        }
    )


def _completion_context() -> FutureCompletionContext:
    return FutureCompletionContext(
        result_write_options=ResultWriteOptions(),
        settings_fingerprint="settings-fp",
        template_library_fingerprint="tpl-fp",
        run_fingerprint=IDENTITY.run_fingerprint,
    )


def _build_execution_state() -> ExecutionState:
    return ExecutionState.create()


def _field(field_id: str) -> TemplateField:
    return TemplateField(
        field_id=field_id,
        field_name=field_id,
        field_type="MATRIX",
        metadata={"id": field_id, "name": field_id, "type": "MATRIX"},
    )


def _build_run_ctx(fields: list[TemplateField]) -> InitializedRunContext:
    runtime_state = RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1)
    return InitializedRunContext(
        client_factory=None,
        template_library={},
        filters=RunFilters(),
        expression_policy=None,
        template_library_fingerprint="tpl-fp",
        settings_fingerprint="settings-fp",
        run_fingerprint=IDENTITY.run_fingerprint,
        historical_state=HistoricalRunState(),
        fields=fields,
        execution_state=_build_execution_state(),
        runtime_state=runtime_state,
        create_semaphore=Semaphore(1),
        run_config={},
    )


def _build_run_loop_args(tmp_path, **overrides) -> ApplicationConfig:
    values = {
        "field_template_batch_size": 1,
        "dataset_id": "fundamental6",
        "output": str(tmp_path / "results.json"),
        "region": "USA",
        "universe": "TOP3000",
        "instrument_type": "EQUITY",
        "delay": 1,
        "decay": 4,
        "neutralization": "SUBINDUSTRY",
        "truncation": 0.08,
        "pasteurization": "ON",
        "unit_handling": "VERIFY",
        "nan_handling": "OFF",
        "max_trade": "OFF",
        "language": "FASTEXPR",
        "start_date": None,
        "end_date": None,
        "simulation_create_retries": 1,
        "simulation_poll_retries": 1,
        "simulation_max_polls": 1,
        "simulation_max_wait_seconds": 1,
        "simulation_max_pending_cycles": 1,
        "simulation_max_queue_seconds": 1,
        "check_submission_retries": 1,
        "min_sharpe": 0.0,
        "min_fitness": 0.0,
        "min_turnover": 0.0,
        "max_turnover": 1.0,
        "max_weight": 1.0,
        "max_templates_per_field": 0,
        "max_templates_per_family": 0,
        "similarity_penalty": 0,
        "template_library_file": "",
        "include_fields_file": "",
        "include_templates_file": "",
        "queue_busy_cooldown_seconds": 0.0,
        "queue_busy_retry_limit": 0,
        "sleep_between_fields": 0.0,
    }
    values.update(overrides)
    args = argparse.Namespace(**values)
    paths = RunPaths(
        results_dir=str(tmp_path),
        log_file=str(tmp_path / "run.log"),
        state_file=str(tmp_path / "state.json"),
        checkpoint_file=str(tmp_path / "checkpoint.json"),
        output=str(tmp_path / "results.json"),
    )
    return ApplicationConfig.from_args(args, paths)


def test_restore_fields_from_state_returns_empty_when_all_fields_completed(tmp_path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        _checkpoint_json(2),
        encoding="utf-8",
    )
    fields = [_field("f1"), _field("f2")]

    restored_fields = restore_fields_from_state(
        fields=fields,
        state_file=str(state_file),
        runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        execution_state=_build_execution_state(),
    )

    assert restored_fields == []


def test_restore_fields_from_state_ignores_legacy_partial_cursor(tmp_path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        _checkpoint_json(1),
        encoding="utf-8",
    )
    fields = [_field("f1"), _field("f2")]

    restored_fields = restore_fields_from_state(
        fields=fields,
        state_file=str(state_file),
        runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        execution_state=_build_execution_state(),
    )

    assert restored_fields == fields


def test_persist_replanning_checkpoint_keeps_cursor_at_zero(tmp_path) -> None:
    """Breadth-first rounds must not mark partially processed fields complete."""
    with patch("alpha.app.run_loop_resume.save_pipeline_state") as mock_save:
        persist_replanning_checkpoint(
            state_file=str(tmp_path / "state.json"),
            field_id="f3",
            execution_state=_build_execution_state(),
            runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        )

    assert mock_save.call_args.kwargs["completed_field_index"] == 0


def test_persist_replanning_checkpoint_raises_when_write_fails(tmp_path) -> None:
    with (
        patch("alpha.app.run_loop_resume.save_pipeline_state", return_value=False),
        pytest.raises(RuntimeError, match="failed to save pipeline state"),
    ):
        persist_replanning_checkpoint(
            state_file=str(tmp_path / "state.json"),
            field_id="f1",
            execution_state=_build_execution_state(),
            runtime_state=RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1),
        )


def test_drain_remaining_futures_persists_total_field_count(tmp_path) -> None:
    future = object()
    execution_state = _build_execution_state()
    execution_state.future_queue.pending_futures = {future: {"field_id": "f1"}}

    def _drain(*, execution_state, **_kwargs):
        execution_state.future_queue.pending_futures.clear()

    with (
        patch("alpha.app.loop_future_support.wait", return_value=({future}, set())),
        patch(
            "alpha.app.loop_future_support.drain_completed_futures_with_context", side_effect=_drain
        ),
        patch("alpha.app.run_loop_resume.save_pipeline_state") as mock_save,
    ):
        drain_remaining_futures(
            state_file=str(tmp_path / "state.json"),
            total_fields=5,
            last_field_id="f5",
            execution_state=execution_state,
            runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
            scheduler_options=SchedulerControlOptions(),
            completion_ctx=_completion_context(),
        )

    assert mock_save.call_args.kwargs["completed_field_index"] == 5


def test_drain_next_completion_keeps_replanning_cursor_at_zero(tmp_path) -> None:
    future = object()
    execution_state = _build_execution_state()
    execution_state.future_queue.pending_futures = {future: {"field_id": "f1"}}

    def _drain(*, execution_state, **_kwargs):
        execution_state.future_queue.pending_futures.clear()

    with (
        patch("alpha.app.loop_future_support.wait", return_value=({future}, set())),
        patch(
            "alpha.app.loop_future_support.drain_completed_futures_with_context", side_effect=_drain
        ),
        patch("alpha.app.loop_future_support.save_pipeline_state", return_value=True) as mock_save,
    ):
        assert (
            drain_next_completion(
                state_file=str(tmp_path / "state.json"),
                total_fields=5,
                last_field_id="f1",
                execution_state=execution_state,
                scheduler_options=SimpleNamespace(),
                completion_ctx=_completion_context(),
                runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
            )
            is True
        )

    assert mock_save.call_args.kwargs["completed_field_index"] == 0


def test_run_field_test_loop_persists_progress_for_skipped_fields(tmp_path) -> None:
    fields = [_field("f1"), _field("f2")]
    run_ctx = _build_run_ctx(fields)
    args = _build_run_loop_args(tmp_path)

    with (
        patch("alpha.app.run_loop_resume.restore_fields_from_state", return_value=fields),
        patch(
            "alpha.app.run_loop_contexts.create_template_build_context",
            return_value=SimpleNamespace(
                field_feedback={},
                global_failed_check_counts={},
                feedback_result_count=0,
            ),
        ),
        patch(
            "alpha.app.run_loop_rounds.execute_schedule_round",
            return_value=ScheduleRoundResult(
                progressed=False,
                stop_requested=False,
                last_field_id="f2",
            ),
        ) as mock_round,
        patch("alpha.app.loop_future_support.submit_resumable_futures") as mock_resume,
        patch("alpha.app.loop_future_support.drain_next_completion", return_value=False),
        patch("alpha.app.loop_future_support.drain_remaining_futures"),
    ):
        run_field_test_loop(args, run_ctx)

    assert mock_resume.call_count == 1
    assert mock_round.call_count == 1


def test_run_field_test_loop_replans_after_pending_seed_completion(tmp_path) -> None:
    fields = [_field("f1")]
    run_ctx = _build_run_ctx(fields)
    args = _build_run_loop_args(tmp_path)
    pending_future = Future()

    def _submit_resumable(**_kwargs) -> int:
        run_ctx.execution_state.future_queue.pending_futures[pending_future] = SimpleNamespace(
            field_id="f1"
        )
        return 1

    def _drain_next(**_kwargs) -> bool:
        if not run_ctx.execution_state.future_queue.pending_futures:
            return False
        run_ctx.execution_state.future_queue.pending_futures.clear()
        run_ctx.execution_state.attempted_keys.add(("f1", "seed", "rank(f1)", "settings"))
        return True

    with (
        patch("alpha.app.run_loop_resume.restore_fields_from_state", return_value=fields),
        patch(
            "alpha.app.run_loop_contexts.create_template_build_context",
            return_value=SimpleNamespace(
                field_feedback={},
                global_failed_check_counts={},
                feedback_result_count=0,
            ),
        ),
        patch(
            "alpha.app.run_loop_rounds.execute_schedule_round",
            side_effect=[
                ScheduleRoundResult(False, False, "f1"),
                ScheduleRoundResult(False, False, "f1"),
            ],
        ) as mock_round,
        patch(
            "alpha.app.loop_future_support.submit_resumable_futures", side_effect=_submit_resumable
        ),
        patch(
            "alpha.app.loop_future_support.drain_next_completion", side_effect=_drain_next
        ) as mock_drain,
        patch("alpha.app.loop_future_support.drain_remaining_futures"),
    ):
        run_field_test_loop(args, run_ctx)

    assert mock_drain.call_count == 2
    assert mock_round.call_count == 2


def test_run_field_test_loop_interrupts_workers_without_waiting(tmp_path) -> None:
    fields = [_field("f1")]
    run_ctx = _build_run_ctx(fields)
    args = _build_run_loop_args(tmp_path)
    running: Future[object] = Future()
    queued: Future[object] = Future()
    assert running.set_running_or_notify_cancel() is True
    running_context = SimpleNamespace(simulation_location="/simulations/sim-1")
    queued_context = SimpleNamespace(simulation_location="")

    class FakeExecutor:
        def __init__(self) -> None:
            self.shutdown_calls: list[tuple[bool, bool]] = []

        def shutdown(self, *, wait: bool, cancel_futures: bool = False) -> None:
            self.shutdown_calls.append((wait, cancel_futures))

    executor = FakeExecutor()

    def _interrupt(*_args, **_kwargs):
        run_ctx.execution_state.future_queue.pending_futures = {
            running: running_context,
            queued: queued_context,
        }
        raise KeyboardInterrupt

    with (
        patch("alpha.app.run_loop.ThreadPoolExecutor", return_value=executor),
        patch("alpha.app.run_loop_resume.restore_fields_from_state", return_value=fields),
        patch(
            "alpha.app.run_loop_contexts.create_template_build_context",
            return_value=SimpleNamespace(
                field_feedback={},
                global_failed_check_counts={},
                feedback_result_count=0,
            ),
        ),
        patch("alpha.app.loop_future_support.submit_resumable_futures"),
        patch("alpha.app.run_loop_rounds.execute_schedule_round", side_effect=_interrupt),
        patch("alpha.app.run_loop_resume.save_runtime_checkpoint") as mock_checkpoint,
        pytest.raises(KeyboardInterrupt),
    ):
        run_field_test_loop(args, run_ctx)

    assert run_ctx.execution_state.future_queue.stop_signal.is_set() is True
    assert executor.shutdown_calls == [(False, True)]
    assert queued.cancelled() is True
    assert list(run_ctx.execution_state.future_queue.pending_futures.values()) == [running_context]
    saved_state = mock_checkpoint.call_args.kwargs["execution_state"]
    assert (
        next(iter(saved_state.future_queue.pending_futures.values())).simulation_location
        == "/simulations/sim-1"
    )


def test_run_field_test_loop_waits_for_worker_metadata_before_interrupt_checkpoint(
    tmp_path,
) -> None:
    fields = [_field("f1")]
    run_ctx = _build_run_ctx(fields)
    args = _build_run_loop_args(tmp_path)
    running: Future[object] = Future()
    assert running.set_running_or_notify_cancel() is True
    running_context = SimpleNamespace(simulation_location="")

    class FakeExecutor:
        def shutdown(self, *, wait: bool, cancel_futures: bool = False) -> None:
            assert (wait, cancel_futures) == (False, True)

    def _interrupt(*_args, **_kwargs):
        run_ctx.execution_state.future_queue.pending_futures = {
            running: running_context,
        }
        raise KeyboardInterrupt

    def _stabilize(execution_state, *, timeout_seconds: float) -> int:
        assert timeout_seconds == 15.0
        context = next(iter(execution_state.future_queue.pending_futures.values()))
        context.simulation_location = "/simulations/sim-after-interrupt"
        return 0

    with (
        patch("alpha.app.run_loop.ThreadPoolExecutor", return_value=FakeExecutor()),
        patch("alpha.app.run_loop_resume.restore_fields_from_state", return_value=fields),
        patch(
            "alpha.app.run_loop_contexts.create_template_build_context",
            return_value=SimpleNamespace(
                field_feedback={},
                global_failed_check_counts={},
                feedback_result_count=0,
            ),
        ),
        patch("alpha.app.loop_future_support.submit_resumable_futures"),
        patch("alpha.app.run_loop_rounds.execute_schedule_round", side_effect=_interrupt),
        patch(
            "alpha.app.loop_future_support.wait_for_inflight_simulation_metadata",
            side_effect=_stabilize,
        ) as mock_stabilize,
        patch("alpha.app.run_loop_resume.save_runtime_checkpoint") as mock_checkpoint,
        pytest.raises(KeyboardInterrupt),
    ):
        run_field_test_loop(args, run_ctx)

    mock_stabilize.assert_called_once_with(
        run_ctx.execution_state,
        timeout_seconds=15.0,
    )
    saved_state = mock_checkpoint.call_args.kwargs["execution_state"]
    assert (
        next(iter(saved_state.future_queue.pending_futures.values())).simulation_location
        == "/simulations/sim-after-interrupt"
    )


def test_run_field_test_loop_waits_for_worker_metadata_before_exception_checkpoint(
    tmp_path,
) -> None:
    fields = [_field("f1")]
    run_ctx = _build_run_ctx(fields)
    args = _build_run_loop_args(tmp_path)
    running: Future[object] = Future()
    assert running.set_running_or_notify_cancel() is True
    running_context = SimpleNamespace(simulation_location="")

    class FakeExecutor:
        def __init__(self) -> None:
            self.shutdown_calls: list[tuple[bool, bool]] = []

        def shutdown(self, *, wait: bool, cancel_futures: bool = False) -> None:
            self.shutdown_calls.append((wait, cancel_futures))
            if wait:
                running_context.simulation_location = "/simulations/sim-after-error"

    executor = FakeExecutor()

    def _fail_round(*_args, **_kwargs):
        run_ctx.execution_state.future_queue.pending_futures = {
            running: running_context,
        }
        raise RuntimeError("scheduler failed")

    with (
        patch("alpha.app.run_loop.ThreadPoolExecutor", return_value=executor),
        patch("alpha.app.run_loop_resume.restore_fields_from_state", return_value=fields),
        patch(
            "alpha.app.run_loop_contexts.create_template_build_context",
            return_value=SimpleNamespace(
                field_feedback={},
                global_failed_check_counts={},
                feedback_result_count=0,
            ),
        ),
        patch("alpha.app.loop_future_support.submit_resumable_futures"),
        patch("alpha.app.run_loop_rounds.execute_schedule_round", side_effect=_fail_round),
        patch("alpha.app.run_loop_resume.save_runtime_checkpoint") as mock_checkpoint,
        pytest.raises(RuntimeError, match="scheduler failed"),
    ):
        run_field_test_loop(args, run_ctx)

    assert run_ctx.execution_state.future_queue.stop_signal.is_set() is True
    assert executor.shutdown_calls == [(True, True)]
    saved_state = mock_checkpoint.call_args.kwargs["execution_state"]
    assert (
        next(iter(saved_state.future_queue.pending_futures.values())).simulation_location
        == "/simulations/sim-after-error"
    )


def test_save_runtime_checkpoint_updates_resumable_pipeline_state(tmp_path) -> None:
    """Interrupt handling must persist live simulation locations to the resume file."""
    execution_state = _build_execution_state()
    runtime_state = RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2)

    with (
        patch("alpha.app.run_loop_resume.save_pipeline_state") as mock_state,
        patch("alpha.app.run_loop_resume.save_interrupt_report") as mock_interrupt_report,
    ):
        save_runtime_checkpoint(
            state_file=str(tmp_path / "state.json"),
            interrupt_report_file=str(tmp_path / "checkpoint.json"),
            completed_field_index=1,
            execution_state=execution_state,
            runtime_state=runtime_state,
            last_field_id="f1",
            fields=[_field("f1"), _field("f2")],
            reason="KeyboardInterrupt",
        )

    assert mock_state.call_args.kwargs["completed_field_index"] == 1
    assert mock_state.call_args.kwargs["field_id"] == "f1"
    assert mock_interrupt_report.call_args.kwargs["reason"] == "KeyboardInterrupt"


def test_save_runtime_checkpoint_logs_failed_writes_without_masking_abort(
    tmp_path,
    caplog,
) -> None:
    with (
        patch("alpha.app.run_loop_resume.save_pipeline_state", return_value=False),
        patch("alpha.app.run_loop_resume.save_interrupt_report", return_value=False),
    ):
        save_runtime_checkpoint(
            state_file=str(tmp_path / "state.json"),
            interrupt_report_file=str(tmp_path / "interrupt.json"),
            completed_field_index=0,
            execution_state=_build_execution_state(),
            runtime_state=RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1),
            last_field_id="f1",
            fields=[_field("f1")],
            reason="KeyboardInterrupt",
        )

    assert "runtime state was not saved" in caplog.text
    assert "interrupt report was not saved" in caplog.text


def test_save_terminal_pipeline_state_raises_when_write_fails(tmp_path) -> None:
    with (
        patch("alpha.app.run_loop_resume.save_pipeline_state", return_value=False),
        pytest.raises(RuntimeError, match="failed to save terminal pipeline state"),
    ):
        save_terminal_pipeline_state(
            state_file=str(tmp_path / "state.json"),
            total_fields=1,
            last_field_id="f1",
            execution_state=_build_execution_state(),
            runtime_state=RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1),
        )
