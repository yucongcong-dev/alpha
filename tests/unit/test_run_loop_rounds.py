"""Breadth-first run-loop scheduling tests."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import Semaphore
from unittest.mock import MagicMock, patch

from alpha.app.run_loop_rounds import (
    ScheduleRoundContext,
    ScheduleRoundResult,
    _dispatch_templates_for_field,
    execute_schedule_round,
    schedule_field_round,
)
from alpha.models.domain import FieldTestResult, SettingsVariant, TemplateField
from alpha.models.io_types import RunFilters
from alpha.models.runtime import (
    ExecutionState,
    FutureCompletionContext,
    HistoricalRunState,
    InitializedRunContext,
    PendingTemplateEntry,
    RuntimeConcurrencyState,
    TemplateBuildContext,
)
from alpha.models.runtime_options import SchedulerControlOptions


def _build_context(*, field_template_batch_size: int) -> ScheduleRoundContext:
    field = TemplateField("f1", "f1", "MATRIX")
    execution_state = ExecutionState.create()
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


def test_queue_exhausted_candidate_is_excluded_from_next_round() -> None:
    context = _build_context(field_template_batch_size=1)
    exhausted_key = ("f1", "t1", "rank(f1)", "settings")
    context.run_ctx.execution_state.queue_exhausted_keys.add(exhausted_key)
    captured_attempted: list[set[tuple[str, str, str, str]]] = []

    def _capture_pending(*_args, attempted_keys, **_kwargs):
        captured_attempted.append(attempted_keys)
        return [], 0, 0

    with (
        context.executor,
        patch("alpha.app.run_loop_rounds.refresh_runtime_feedback"),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            side_effect=_capture_pending,
        ),
        patch("alpha.app.run_loop_rounds._dispatch_templates_for_field", return_value=False),
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        schedule_field_round(
            context=context,
            field=context.fields[0],
            field_index=1,
            total_fields=1,
            round_index=2,
        )

    assert exhausted_key in captured_attempted[0]


def test_historical_submittable_result_does_not_stop_new_round() -> None:
    context = _build_context(field_template_batch_size=1)
    context.scheduler_options = SchedulerControlOptions(stop_after_submittable=1)
    ledger = context.run_ctx.execution_state.result_ledger
    ledger.append(
        FieldTestResult(
            field_id="historical",
            field_type="MATRIX",
            field_name="historical",
            template_name="tpl",
            status="simulated",
            submittable=True,
            expression="rank(historical)",
        )
    )
    ledger.submittable_baseline_count = 1
    context.run_ctx.execution_state.sync_result_ledger()

    with patch(
        "alpha.app.run_loop_rounds.schedule_field_round",
        return_value=ScheduleRoundResult(
            progressed=False,
            stop_requested=False,
            last_field_id="f1",
        ),
    ) as mock_schedule:
        result = execute_schedule_round(context, round_index=1)

    assert result.stop_requested is False
    mock_schedule.assert_called_once()


def test_preexisting_stop_signal_skips_round_without_building_fields() -> None:
    context = _build_context(field_template_batch_size=1)
    context.run_ctx.execution_state.stop_signal.set()

    with patch("alpha.app.run_loop_rounds.schedule_field_round") as mock_schedule:
        result = execute_schedule_round(context, round_index=1)

    assert result == ScheduleRoundResult(False, True, "")
    mock_schedule.assert_not_called()


def test_stop_after_submittable_stops_before_next_field() -> None:
    context = _build_context(field_template_batch_size=1)
    context.scheduler_options = SchedulerControlOptions(stop_after_submittable=1)
    context.run_ctx.execution_state.result_ledger.append(
        FieldTestResult(
            field_id="new",
            field_type="MATRIX",
            field_name="new",
            template_name="template",
            status="simulated",
            submittable=True,
        )
    )

    with patch("alpha.app.run_loop_rounds.schedule_field_round") as mock_schedule:
        result = execute_schedule_round(context, round_index=1)

    assert result.stop_requested is True
    assert context.run_ctx.execution_state.stop_signal.is_set()
    mock_schedule.assert_not_called()


def test_skipped_field_persists_progress_without_building_templates() -> None:
    context = _build_context(field_template_batch_size=1)

    with (
        context.executor,
        patch("alpha.app.run_loop_rounds.refresh_runtime_feedback"),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=True),
        patch("alpha.app.run_loop_rounds.build_pending_templates_for_field") as mock_build,
        patch("alpha.app.run_loop_rounds.persist_field_progress") as mock_persist,
    ):
        result = schedule_field_round(
            context=context,
            field=context.fields[0],
            field_index=1,
            total_fields=1,
            round_index=1,
        )

    assert result == ScheduleRoundResult(False, False, "f1")
    mock_build.assert_not_called()
    assert mock_persist.call_args.kwargs["completed_field_index_override"] == 0


def test_breadth_first_round_dispatches_only_configured_batch() -> None:
    context = _build_context(field_template_batch_size=1)
    entries = [
        PendingTemplateEntry(
            template_name=f"template-{index}",
            template_family="rank",
            template_stage="first_order",
            template_role="signal",
            template_activation_scope="broad",
            expression=f"rank(f1) + {index}",
            priority=100 - index,
            settings_variant=SettingsVariant(),
            variant_fingerprint=f"settings-{index}",
        )
        for index in range(2)
    ]

    with (
        context.executor,
        patch("alpha.app.run_loop_rounds.refresh_runtime_feedback"),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            return_value=(entries, 0, 2),
        ),
        patch(
            "alpha.app.run_loop_rounds._dispatch_templates_for_field", return_value=False
        ) as dispatch,
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        result = schedule_field_round(
            context=context,
            field=context.fields[0],
            field_index=1,
            total_fields=1,
            round_index=1,
        )

    assert result == ScheduleRoundResult(True, False, "f1")
    assert dispatch.call_args.kwargs["scheduled_templates"] == entries[:1]


def test_dispatch_honors_stop_capacity_and_success_paths() -> None:
    context = _build_context(field_template_batch_size=1)
    entry = PendingTemplateEntry(
        template_name="template",
        template_family="rank",
        template_stage="first_order",
        template_role="signal",
        template_activation_scope="broad",
        expression="rank(f1)",
        priority=100,
        settings_variant=SettingsVariant(),
        variant_fingerprint="settings",
    )
    kwargs = {
        "context": context,
        "field": context.fields[0],
        "field_id": "f1",
        "field_name": "f1",
        "field_type": "MATRIX",
        "scheduled_templates": [entry],
    }

    context.scheduler_options = SchedulerControlOptions(stop_after_submittable=1)
    context.run_ctx.execution_state.result_ledger.append(
        FieldTestResult(
            field_id="new",
            field_type="MATRIX",
            field_name="new",
            template_name="template",
            status="simulated",
            submittable=True,
        )
    )

    assert _dispatch_templates_for_field(**kwargs) is True
    assert context.run_ctx.execution_state.stop_signal.is_set()

    context.scheduler_options = SchedulerControlOptions(stop_after_submittable=0)
    context.run_ctx.execution_state.stop_signal.clear()
    with (
        patch("alpha.app.run_loop_rounds.maybe_restore_runtime_concurrency"),
        patch("alpha.app.run_loop_rounds.drain_until_capacity", return_value=False),
        patch("alpha.app.run_loop_rounds.submit_template_future") as mock_submit,
    ):
        assert _dispatch_templates_for_field(**kwargs) is False
    mock_submit.assert_not_called()

    with (
        patch("alpha.app.run_loop_rounds.maybe_restore_runtime_concurrency"),
        patch("alpha.app.run_loop_rounds.drain_until_capacity", return_value=True),
        patch("alpha.app.run_loop_rounds.throttle_before_submission"),
        patch("alpha.app.run_loop_rounds.submit_template_future") as mock_submit,
    ):
        assert _dispatch_templates_for_field(**kwargs) is False
    mock_submit.assert_called_once()
