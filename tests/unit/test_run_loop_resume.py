"""run_loop / loop_support 续跑边界测试。"""

from __future__ import annotations

import argparse
import json
from threading import Semaphore
from types import SimpleNamespace
from unittest.mock import patch

from alpha.loop_support import (
    drain_remaining_futures,
    persist_field_progress,
    restore_fields_from_state,
)
from alpha.models.base import (
    ExecutionState,
    HistoricalRunState,
    InitializedRunContext,
    RunFilters,
    RuntimeConcurrencyState,
)
from alpha.run_loop import clamp_resume_index, run_field_test_loop


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
        clamp_resume_index_fn=clamp_resume_index,
    )

    assert restored_fields == []
    assert resumed_index == 2


def test_persist_field_progress_keeps_terminal_index() -> None:
    with patch("alpha.loop_support.save_pipeline_state") as mock_save:
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


def test_drain_remaining_futures_persists_total_field_count() -> None:
    future = object()
    execution_state = _build_execution_state()
    execution_state.pending_futures = {future: {"field_id": "f1"}}

    def _drain(*, execution_state, **_kwargs):
        execution_state.pending_futures.clear()

    with (
        patch("alpha.loop_support.wait", return_value=({future}, set())),
        patch("alpha.loop_support.drain_completed_futures", side_effect=_drain),
        patch("alpha.loop_support.save_pipeline_state") as mock_save,
    ):
        drain_remaining_futures(
            state_file="/tmp/state.json",
            total_fields=5,
            last_field_id="f5",
            execution_state=execution_state,
            runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
            args=argparse.Namespace(),
            run_ctx=_build_run_ctx([]),
        )

    assert mock_save.call_args.kwargs["completed_field_index"] == 5


def test_run_field_test_loop_persists_progress_for_skipped_fields(tmp_path) -> None:
    fields = [{"id": "f1", "type": "MATRIX", "name": "f1"}, {"id": "f2", "type": "MATRIX", "name": "f2"}]
    run_ctx = _build_run_ctx(fields)
    args = argparse.Namespace(dry_run_plan=False, field_template_batch_size=0, stop_after_submittable=0)

    with (
        patch("alpha.run_loop.restore_fields_from_state", return_value=(fields, 0)),
        patch(
            "alpha.run_loop.create_template_build_context",
            return_value=SimpleNamespace(
                field_feedback={},
                global_failed_check_counts={},
                feedback_result_count=0,
            ),
        ),
        patch("alpha.run_loop.should_stop_after_submittable", return_value=False),
        patch("alpha.run_loop.should_skip_field", side_effect=[True, True]),
        patch("alpha.run_loop.persist_field_progress") as mock_persist,
        patch("alpha.run_loop.drain_remaining_futures"),
    ):
        run_field_test_loop(
            args,
            run_ctx,
            run_paths=argparse.Namespace(
                state_file=str(tmp_path / "state.json"),
                checkpoint_file="",
            ),
        )

    assert mock_persist.call_count == 2
