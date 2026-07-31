"""run_loop resume and persistence boundary tests."""

from __future__ import annotations

import argparse
from concurrent.futures import Future
import json
from threading import Semaphore
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from alpha.app.run_loop import (
    ScheduleRoundResult,
    drain_remaining_futures,
    persist_field_progress,
    resolve_result_write_options,
    restore_fields_from_state,
    run_field_test_loop,
)
from alpha.app.run_loop_resume import save_runtime_checkpoint
from alpha.models.io_types import RunFilters, RunPaths
from alpha.models.runtime import (
    ExecutionState,
    FutureCompletionContext,
    HistoricalRunState,
    InitializedRunContext,
    ResultWriteOptions,
    RuntimeConcurrencyState,
)


def _build_execution_state() -> ExecutionState:
    return ExecutionState(
        results=[],
        attempted_keys=set(),
        template_stats={},
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )


def _build_run_ctx(fields: list[dict[str, str]]) -> InitializedRunContext:
    runtime_state = RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1)
    return InitializedRunContext(
        client_factory=None,
        template_library={},
        filters=RunFilters(),
        expression_policy=None,
        use_dataset_heuristics=False,
        template_library_fingerprint="tpl-fp",
        settings_fingerprint="settings-fp",
        historical_state=HistoricalRunState(),
        fields=fields,
        execution_state=_build_execution_state(),
        runtime_state=runtime_state,
        create_semaphore=Semaphore(1),
        run_config={},
    )


def test_restore_fields_from_state_returns_empty_when_all_fields_completed(tmp_path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({"version": 1, "completed_field_index": 2}),
        encoding="utf-8",
    )
    fields = [{"id": "f1"}, {"id": "f2"}]

    restored_fields, resumed_index = restore_fields_from_state(
        fields=fields,
        state_file=str(state_file),
        runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        execution_state=_build_execution_state(),
    )

    assert restored_fields == []
    assert resumed_index == 2


def test_persist_field_progress_keeps_terminal_index() -> None:
    with patch("alpha.app.run_loop_resume.save_pipeline_state") as mock_save:
        persist_field_progress(
            state_file="/tmp/state.json",
            field_id="f3",
            field_index=3,
            original_fields=[{"id": "f1"}, {"id": "f2"}, {"id": "f3"}],
            field_resume_positions={"f1": 1, "f2": 2, "f3": 3},
            execution_state=_build_execution_state(),
            runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        )

    assert mock_save.call_args.kwargs["completed_field_index"] == 3


def test_persist_field_progress_allows_resuming_from_first_field() -> None:
    """Breadth-first rounds must not mark partially processed fields complete."""
    with patch("alpha.app.run_loop_resume.save_pipeline_state") as mock_save:
        persist_field_progress(
            state_file="/tmp/state.json",
            field_id="f3",
            field_index=3,
            original_fields=[{"id": "f1"}, {"id": "f2"}, {"id": "f3"}],
            field_resume_positions={"f1": 1, "f2": 2, "f3": 3},
            execution_state=_build_execution_state(),
            runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
            completed_field_index_override=0,
        )

    assert mock_save.call_args.kwargs["completed_field_index"] == 0


def test_drain_remaining_futures_persists_total_field_count() -> None:
    future = object()
    execution_state = _build_execution_state()
    execution_state.pending_futures = {future: {"field_id": "f1"}}

    def _drain(*, execution_state, **_kwargs):
        execution_state.pending_futures.clear()

    with (
        patch("alpha.app.loop_future_support.wait", return_value=({future}, set())),
        patch(
            "alpha.app.loop_future_support.drain_completed_futures_with_context", side_effect=_drain
        ),
        patch("alpha.app.run_loop_resume.save_pipeline_state") as mock_save,
    ):
        drain_remaining_futures(
            state_file="/tmp/state.json",
            total_fields=5,
            last_field_id="f5",
            execution_state=execution_state,
            runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
            args=argparse.Namespace(),
            completion_ctx=FutureCompletionContext(
                result_write_options=ResultWriteOptions(),
            ),
        )

    assert mock_save.call_args.kwargs["completed_field_index"] == 5


def test_run_field_test_loop_persists_progress_for_skipped_fields(tmp_path) -> None:
    fields = [
        {"id": "f1", "type": "MATRIX", "name": "f1"},
        {"id": "f2", "type": "MATRIX", "name": "f2"},
    ]
    run_ctx = _build_run_ctx(fields)
    args = argparse.Namespace(
        field_template_batch_size=0,
        stop_after_submittable=0,
        dataset_id="fundamental6",
        output=str(tmp_path / "results.json"),
        auto_update_blacklist=False,
    )

    with (
        patch("alpha.app.run_loop.restore_fields_from_state", return_value=(fields, 0)),
        patch(
            "alpha.app.run_loop.create_template_build_context",
            return_value=SimpleNamespace(
                field_feedback={},
                global_failed_check_counts={},
                feedback_result_count=0,
            ),
        ),
        patch(
            "alpha.app.run_loop.execute_schedule_round",
            return_value=ScheduleRoundResult(
                progressed=False,
                stop_requested=False,
                last_field_id="f2",
            ),
        ) as mock_round,
        patch("alpha.app.run_loop.submit_resumable_futures") as mock_resume,
        patch("alpha.app.run_loop.drain_remaining_futures"),
    ):
        run_field_test_loop(
            args,
            run_ctx,
            run_paths=argparse.Namespace(
                state_file=str(tmp_path / "state.json"),
                checkpoint_file="",
            ),
        )

    assert mock_resume.call_count == 1
    assert mock_round.call_count == 1


def test_run_field_test_loop_interrupts_workers_without_waiting(tmp_path) -> None:
    fields = [{"id": "f1", "type": "MATRIX", "name": "f1"}]
    run_ctx = _build_run_ctx(fields)
    args = argparse.Namespace(
        field_template_batch_size=0,
        stop_after_submittable=0,
        dataset_id="fundamental6",
        output=str(tmp_path / "results.json"),
        auto_update_blacklist=False,
    )
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
        run_ctx.execution_state.pending_futures = {
            running: running_context,
            queued: queued_context,
        }
        raise KeyboardInterrupt

    with (
        patch("alpha.app.run_loop.ThreadPoolExecutor", return_value=executor),
        patch("alpha.app.run_loop.restore_fields_from_state", return_value=(fields, 0)),
        patch(
            "alpha.app.run_loop.create_template_build_context",
            return_value=SimpleNamespace(
                field_feedback={},
                global_failed_check_counts={},
                feedback_result_count=0,
            ),
        ),
        patch("alpha.app.run_loop.submit_resumable_futures"),
        patch("alpha.app.run_loop.execute_schedule_round", side_effect=_interrupt),
        patch("alpha.app.run_loop.save_runtime_checkpoint") as mock_checkpoint,
        pytest.raises(KeyboardInterrupt),
    ):
        run_field_test_loop(
            args,
            run_ctx,
            run_paths=argparse.Namespace(
                state_file=str(tmp_path / "state.json"),
                checkpoint_file=str(tmp_path / "checkpoint.json"),
            ),
        )

    assert run_ctx.execution_state.stop_signal.is_set() is True
    assert executor.shutdown_calls == [(False, True)]
    assert queued.cancelled() is True
    assert list(run_ctx.execution_state.pending_futures.values()) == [running_context]
    saved_state = mock_checkpoint.call_args.kwargs["execution_state"]
    assert next(iter(saved_state.pending_futures.values())).simulation_location == (
        "/simulations/sim-1"
    )


def test_resolve_result_write_options_prefers_run_paths_output() -> None:
    args = argparse.Namespace(
        dataset_id="fundamental6",
        output="raw-results.json",
        auto_update_blacklist=False,
    )
    run_paths = RunPaths(
        results_dir="/tmp/results",
        log_file="/tmp/run.log",
        state_file="/tmp/state.json",
        checkpoint_file="/tmp/checkpoint.json",
        output="/tmp/normalized-results.json",
    )

    options = resolve_result_write_options(args, run_paths)

    assert options == ResultWriteOptions(
        dataset_id="fundamental6",
        output_path="/tmp/normalized-results.json",
        auto_update_blacklist=False,
    )


def test_save_runtime_checkpoint_updates_resumable_pipeline_state() -> None:
    """Interrupt handling must persist live simulation locations to the resume file."""
    execution_state = _build_execution_state()
    runtime_state = RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2)

    with (
        patch("alpha.app.run_loop_resume.save_pipeline_state") as mock_state,
        patch("alpha.app.run_loop_resume.save_interrupt_report") as mock_interrupt_report,
    ):
        save_runtime_checkpoint(
            state_file="/tmp/state.json",
            interrupt_report_file="/tmp/checkpoint.json",
            completed_field_index=1,
            execution_state=execution_state,
            runtime_state=runtime_state,
            last_field_id="f1",
            fields=[{"id": "f1"}, {"id": "f2"}],
            reason="KeyboardInterrupt",
        )

    assert mock_state.call_args.kwargs["completed_field_index"] == 1
    assert mock_state.call_args.kwargs["field_id"] == "f1"
    assert mock_interrupt_report.call_args.kwargs["reason"] == "KeyboardInterrupt"
