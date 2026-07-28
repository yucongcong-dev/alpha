"""Breadth-first run-loop scheduling tests."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import Semaphore
from unittest.mock import MagicMock, patch

from alpha.app.run_loop_rounds import ScheduleRoundContext, schedule_field_round
from alpha.models.io_types import RunFilters
from alpha.models.runtime import (
    ExecutionState,
    FutureCompletionContext,
    HistoricalRunState,
    InitializedRunContext,
    RuntimeConcurrencyState,
    TemplateBuildContext,
)


def _build_context(*, field_template_batch_size: int) -> ScheduleRoundContext:
    field = {"id": "f1", "name": "f1", "type": "MATRIX"}
    execution_state = ExecutionState(
        results=[],
        attempted_keys=set(),
        template_stats={},
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )
    runtime_state = RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1)
    run_ctx = InitializedRunContext(
        client_factory=None,
        template_library={},
        filters=RunFilters(),
        expression_policy=None,
        use_dataset_heuristics=False,
        template_library_fingerprint="tpl-fp",
        settings_fingerprint="settings-fp",
        historical_state=HistoricalRunState(),
        fields=[field],
        execution_state=execution_state,
        runtime_state=runtime_state,
        create_semaphore=Semaphore(1),
        run_config={},
    )
    return ScheduleRoundContext(
        args=argparse.Namespace(stop_after_submittable=0),
        run_ctx=run_ctx,
        executor=ThreadPoolExecutor(max_workers=1),
        template_build_ctx=MagicMock(spec=TemplateBuildContext),
        fields=[field],
        original_fields=[field],
        field_resume_positions={"f1": 1},
        completion_ctx=FutureCompletionContext(),
        state_file="/tmp/state.json",
        field_template_batch_size=field_template_batch_size,
    )


def test_breadth_first_field_progress_keeps_resume_cursor_at_start() -> None:
    """A partial template batch must keep every field eligible after restart."""
    context = _build_context(field_template_batch_size=1)

    with (
        context.executor,
        patch("alpha.app.run_loop_rounds.refresh_runtime_feedback"),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            return_value=([], 0, 0),
        ),
        patch("alpha.app.run_loop_rounds._dispatch_templates_for_field", return_value=False),
        patch("alpha.app.run_loop_rounds.persist_field_progress") as mock_persist,
    ):
        schedule_field_round(
            context=context,
            field=context.fields[0],
            field_index=1,
            total_fields=1,
            round_index=1,
        )

    assert mock_persist.call_args.kwargs["completed_field_index_override"] == 0


def test_unbatched_field_progress_keeps_linear_resume_cursor() -> None:
    """The original field cursor remains active when a field is processed in full."""
    context = _build_context(field_template_batch_size=0)

    with (
        context.executor,
        patch("alpha.app.run_loop_rounds.refresh_runtime_feedback"),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            return_value=([], 0, 0),
        ),
        patch("alpha.app.run_loop_rounds._dispatch_templates_for_field", return_value=False),
        patch("alpha.app.run_loop_rounds.persist_field_progress") as mock_persist,
    ):
        schedule_field_round(
            context=context,
            field=context.fields[0],
            field_index=1,
            total_fields=1,
            round_index=1,
        )

    assert mock_persist.call_args.kwargs["completed_field_index_override"] is None
