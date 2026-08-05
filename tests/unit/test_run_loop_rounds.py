"""Breadth-first run-loop scheduling tests."""

from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Semaphore
from unittest.mock import MagicMock, patch

from alpha.app.run_loop_dispatch import dispatch_templates_for_field
from alpha.app.run_loop_feedback import RuntimeFeedbackRefresh
from alpha.app.run_loop_rounds import (
    ScheduleRoundContext,
    ScheduleRoundResult,
    execute_schedule_round,
    schedule_field_round,
)
from alpha.app.run_loop_seed_phase import SeedPhaseState
from alpha.models.domain import FieldTestResult, SettingsVariant, TemplateField
from alpha.models.io_types import RunFilters
from alpha.models.runtime import (
    ExecutionState,
    FutureCompletionContext,
    HistoricalRunState,
    InitializedRunContext,
    PendingFutureContext,
    PendingTemplateEntry,
    RuntimeConcurrencyState,
    TemplateBuildContext,
)
from alpha.models.runtime_options import SchedulerControlOptions
from alpha.runtime.field_template_queue import FieldTemplateQueue


def _build_context(
    *,
    field_template_batch_size: int,
    state_file: str = "state.json",
    field_ids: tuple[str, ...] = ("f1",),
    seed_phase_enabled: bool = False,
    seed_resolved_field_ids: set[str] | None = None,
) -> ScheduleRoundContext:
    fields = [TemplateField(field_id, field_id, "MATRIX") for field_id in field_ids]
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
        fields=fields,
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
        fields=fields,
        original_fields=fields,
        field_resume_positions={field.field_id: index for index, field in enumerate(fields, 1)},
        completion_ctx=FutureCompletionContext(),
        state_file=state_file,
        field_template_batch_size=field_template_batch_size,
        seed_phase=SeedPhaseState.create(
            fields,
            enabled=seed_phase_enabled,
            resolved_field_ids=seed_resolved_field_ids,
        ),
    )


def test_breadth_first_field_progress_keeps_resume_cursor_at_start(tmp_path) -> None:
    """A partial template batch must keep every field eligible after restart."""
    context = _build_context(
        field_template_batch_size=1,
        state_file=str(tmp_path / "state.json"),
    )

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            return_value=([], 0, 0),
        ),
        patch("alpha.app.run_loop_rounds.dispatch_templates_for_field", return_value=False),
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


def test_zero_batch_size_is_normalized_to_breadth_first() -> None:
    context = _build_context(field_template_batch_size=0)

    assert context.field_template_batch_size == 1

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            return_value=([], 0, 0),
        ),
        patch("alpha.app.run_loop_rounds.dispatch_templates_for_field", return_value=False),
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


def test_full_run_seed_phase_covers_fields_before_refine() -> None:
    context = _build_context(
        field_template_batch_size=2,
        field_ids=("f1", "f2"),
        seed_phase_enabled=True,
    )
    dispatched_batches: list[tuple[str, int]] = []

    def _pending_for_field(_ctx, field, **_kwargs):
        entries = [
            PendingTemplateEntry(
                template_name=f"template-{index}",
                template_family="rank",
                template_stage="first_order",
                template_role="signal",
                template_activation_scope="broad",
                expression=f"rank({field.field_id}) + {index}",
                priority=100 - index,
                settings_variant=SettingsVariant(),
                variant_fingerprint=f"settings-{index}",
            )
            for index in range(3)
        ]
        return entries, 0, len(entries)

    def _consume_dispatch(*, field_id, scheduled_templates, template_queue, **_kwargs):
        dispatched_batches.append((field_id, len(scheduled_templates)))
        for _entry in scheduled_templates:
            template_queue.consume_one()
        return False

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            side_effect=_pending_for_field,
        ),
        patch(
            "alpha.app.run_loop_rounds.dispatch_templates_for_field",
            side_effect=_consume_dispatch,
        ),
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        first_round = execute_schedule_round(context, round_index=1)
        assert first_round.progressed is True
        assert dispatched_batches == [("f1", 1), ("f2", 1)]
        assert context.seed_phase.active is True
        assert context.seed_phase.inflight_field_ids == {"f1", "f2"}

        context.run_ctx.execution_state.attempted_keys.update(
            {
                ("f1", "seed", "rank(f1)", "settings-0"),
                ("f2", "seed", "rank(f2)", "settings-0"),
            }
        )

        dispatched_batches.clear()
        second_round = execute_schedule_round(context, round_index=2)

    assert second_round.progressed is True
    assert dispatched_batches == [("f1", 2), ("f2", 2)]


def test_full_run_seed_phase_prefers_default_seed_role() -> None:
    context = _build_context(
        field_template_batch_size=2,
        seed_phase_enabled=True,
    )
    refine_entry = PendingTemplateEntry(
        template_name="high-priority-refine",
        template_family="ratio",
        template_stage="group_second_order",
        template_role="refine_neighbor",
        template_activation_scope="broad",
        expression="group_rank(f1, industry)",
        priority=1200,
        settings_variant=SettingsVariant(),
        variant_fingerprint="refine-settings",
    )
    seed_entry = PendingTemplateEntry(
        template_name="generic-seed",
        template_family="rank",
        template_stage="first_order",
        template_role="default_seed",
        template_activation_scope="broad",
        expression="rank(f1)",
        priority=900,
        settings_variant=SettingsVariant(),
        variant_fingerprint="seed-settings",
    )
    dispatched: list[str] = []

    def _consume_dispatch(*, scheduled_templates, template_queue, **_kwargs):
        dispatched.extend(entry.template_name for entry in scheduled_templates)
        for entry in scheduled_templates:
            template_queue.consume(entry)
        return False

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            return_value=([refine_entry, seed_entry], 0, 2),
        ),
        patch(
            "alpha.app.run_loop_rounds.dispatch_templates_for_field",
            side_effect=_consume_dispatch,
        ),
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        execute_schedule_round(context, round_index=1)

    assert dispatched == ["generic-seed"]
    assert list(context.field_template_queues["f1"].entries) == [refine_entry]


def test_full_run_seed_phase_skips_historically_seeded_fields() -> None:
    context = _build_context(
        field_template_batch_size=2,
        field_ids=("f1", "f2"),
        seed_phase_enabled=True,
        seed_resolved_field_ids={"f1"},
    )
    planned_field_ids: list[str] = []

    def _pending_for_field(_ctx, field, **_kwargs):
        planned_field_ids.append(field.field_id)
        entry = PendingTemplateEntry(
            template_name="seed",
            template_family="rank",
            template_stage="first_order",
            template_role="signal",
            template_activation_scope="broad",
            expression=f"rank({field.field_id})",
            priority=100,
            settings_variant=SettingsVariant(),
            variant_fingerprint="settings",
        )
        return [entry], 0, 1

    def _consume_dispatch(*, scheduled_templates, template_queue, **_kwargs):
        assert len(scheduled_templates) == 1
        template_queue.consume_one()
        return False

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            side_effect=_pending_for_field,
        ),
        patch(
            "alpha.app.run_loop_rounds.dispatch_templates_for_field",
            side_effect=_consume_dispatch,
        ),
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        execute_schedule_round(context, round_index=1)

    assert planned_field_ids == ["f2"]
    assert context.seed_phase.active is True
    assert context.seed_phase.inflight_field_ids == {"f2"}


def test_full_run_seed_phase_skips_resumable_inflight_fields() -> None:
    context = _build_context(
        field_template_batch_size=1,
        field_ids=("f1", "f2"),
        seed_phase_enabled=True,
    )
    context.run_ctx.execution_state.future_queue.replace_resumable_batch(
        [PendingFutureContext(field_id="f1", simulation_location="/simulations/sim-1")]
    )
    context.seed_phase.sync(context.run_ctx.execution_state)
    planned_field_ids: list[str] = []

    def _pending_for_field(_ctx, field, **_kwargs):
        planned_field_ids.append(field.field_id)
        return [], 0, 0

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            side_effect=_pending_for_field,
        ),
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        result = execute_schedule_round(context, round_index=1)

    assert planned_field_ids == ["f2"]
    assert result.progressed is True
    assert context.seed_phase.active is True
    assert context.seed_phase.inflight_field_ids == {"f1"}


def test_full_run_seed_inflight_completion_becomes_resolved() -> None:
    context = _build_context(
        field_template_batch_size=1,
        seed_phase_enabled=True,
    )
    completed_future: Future[FieldTestResult] = Future()
    context.run_ctx.execution_state.future_queue.register(
        completed_future,
        PendingFutureContext(field_id="f1", simulation_location="/simulations/sim-1"),
    )
    context.seed_phase.sync(context.run_ctx.execution_state)
    assert context.seed_phase.inflight_field_ids == {"f1"}

    context.run_ctx.execution_state.future_queue.pop_completed(completed_future)
    context.run_ctx.execution_state.attempted_keys.add(("f1", "seed", "rank(f1)", "settings"))
    context.seed_phase.sync(context.run_ctx.execution_state)

    assert context.seed_phase.inflight_field_ids == set()
    assert context.seed_phase.resolved_field_ids == {"f1"}
    assert context.seed_phase.active is False


def test_full_run_all_remaining_seeds_inflight_does_not_enter_refine() -> None:
    context = _build_context(
        field_template_batch_size=1,
        field_ids=("f1",),
        seed_phase_enabled=True,
    )
    context.run_ctx.execution_state.future_queue.replace_resumable_batch(
        [PendingFutureContext(field_id="f1", simulation_location="/simulations/sim-1")]
    )

    with (
        context.executor,
        patch("alpha.app.run_loop_rounds.build_pending_templates_for_field") as mock_build,
    ):
        result = execute_schedule_round(context, round_index=1)

    assert result.progressed is False
    assert result.stop_requested is False
    assert context.seed_phase.active is True
    mock_build.assert_not_called()


def test_full_run_unactionable_seed_fields_advance_to_refine() -> None:
    context = _build_context(
        field_template_batch_size=2,
        field_ids=("f1", "f2"),
        seed_phase_enabled=True,
        seed_resolved_field_ids={"f1"},
    )
    planned_field_ids: list[str] = []
    dispatched_field_ids: list[str] = []

    def _pending_for_field(_ctx, field, **_kwargs):
        planned_field_ids.append(field.field_id)
        if field.field_id == "f2":
            return [], 0, 0
        entries = [
            PendingTemplateEntry(
                template_name=f"refine-{index}",
                template_family="rank",
                template_stage="first_order",
                template_role="signal",
                template_activation_scope="refine",
                expression=f"rank(f1) + {index}",
                priority=100 - index,
                settings_variant=SettingsVariant(),
                variant_fingerprint=f"settings-{index}",
            )
            for index in range(2)
        ]
        return entries, 0, len(entries)

    def _consume_dispatch(*, field_id, scheduled_templates, template_queue, **_kwargs):
        if scheduled_templates:
            dispatched_field_ids.append(field_id)
        for _entry in scheduled_templates:
            template_queue.consume_one()
        return False

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            side_effect=_pending_for_field,
        ),
        patch(
            "alpha.app.run_loop_rounds.dispatch_templates_for_field",
            side_effect=_consume_dispatch,
        ),
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        seed_round = execute_schedule_round(context, round_index=1)
        assert seed_round.progressed is True
        assert context.seed_phase.active is False

        refine_round = execute_schedule_round(context, round_index=2)

    assert refine_round.progressed is True
    assert planned_field_ids == ["f2", "f1"]
    assert dispatched_field_ids == ["f1"]


def test_queue_exhausted_candidate_is_excluded_from_next_round() -> None:
    context = _build_context(field_template_batch_size=1)
    exhausted_key = ("f1", "t1", "rank(f1)", "settings")
    context.run_ctx.execution_state.queue_retry_state.exhausted_keys.add(exhausted_key)
    captured_attempted: list[set[tuple[str, str, str, str]]] = []

    def _capture_pending(*_args, attempted_keys, **_kwargs):
        captured_attempted.append(attempted_keys)
        return [], 0, 0

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            side_effect=_capture_pending,
        ),
        patch("alpha.app.run_loop_rounds.dispatch_templates_for_field", return_value=False),
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


def test_queue_timeout_invalidates_only_retry_field_template_queue() -> None:
    context = _build_context(field_template_batch_size=1)
    context.template_build_ctx = TemplateBuildContext(options=MagicMock())
    context.template_build_ctx.feedback_result_count = 0
    stale_entry = PendingTemplateEntry(
        template_name="stale",
        template_family="rank",
        template_stage="first_order",
        template_role="signal",
        template_activation_scope="broad",
        expression="rank(f1)",
        priority=100,
        settings_variant=SettingsVariant(),
        variant_fingerprint="settings",
    )
    context.field_template_queues["f1"] = FieldTemplateQueue.create(
        [stale_entry],
        filtered_templates=0,
        template_count=1,
    )
    context.run_ctx.execution_state.result_ledger.append(
        FieldTestResult(
            field_id="f1",
            field_type="MATRIX",
            field_name="f1",
            template_name="stale",
            status="error",
            failed_stage="simulation",
            message="simulation queued too long",
            expression="rank(f1)",
        )
    )

    with (
        context.executor,
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            return_value=([], 0, 1),
        ) as mock_build,
        patch("alpha.app.run_loop_rounds.dispatch_templates_for_field", return_value=False),
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        schedule_field_round(
            context=context,
            field=context.fields[0],
            field_index=1,
            total_fields=1,
            round_index=2,
        )

    mock_build.assert_called_once()
    assert not context.field_template_queues["f1"].entries


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
    context.run_ctx.execution_state.future_queue.stop_signal.set()

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
    assert context.run_ctx.execution_state.future_queue.scheduling_stop_signal.is_set()
    assert context.run_ctx.execution_state.future_queue.stop_signal.is_set() is False
    mock_schedule.assert_not_called()


def test_skipped_field_persists_progress_without_building_templates() -> None:
    context = _build_context(field_template_batch_size=1)

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
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
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            return_value=(entries, 0, 2),
        ),
        patch(
            "alpha.app.run_loop_rounds.dispatch_templates_for_field", return_value=False
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


def test_breadth_first_reuses_cached_field_template_queue() -> None:
    context = _build_context(field_template_batch_size=1)
    context.template_build_ctx.feedback_result_count = 0
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
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(feedback_changed=False),
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            return_value=(entries, 0, 2),
        ) as mock_build,
        patch("alpha.app.run_loop_dispatch.maybe_restore_runtime_concurrency"),
        patch("alpha.app.run_loop_dispatch.drain_until_capacity", return_value=True),
        patch("alpha.app.run_loop_dispatch.throttle_before_submission"),
        patch("alpha.app.run_loop_dispatch.submit_template_future") as mock_submit,
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        for round_index in (1, 2):
            schedule_field_round(
                context=context,
                field=context.fields[0],
                field_index=1,
                total_fields=1,
                round_index=round_index,
            )

    mock_build.assert_called_once()
    assert [call.kwargs["expression"] for call in mock_submit.call_args_list] == [
        "rank(f1) + 0",
        "rank(f1) + 1",
    ]
    assert not context.field_template_queues["f1"].entries


def test_feedback_change_invalidates_cached_field_template_queue() -> None:
    context = _build_context(field_template_batch_size=1)
    context.template_build_ctx.feedback_result_count = 0
    initial_entries = [
        PendingTemplateEntry(
            template_name=f"initial-{index}",
            template_family="rank",
            template_stage="first_order",
            template_role="signal",
            template_activation_scope="broad",
            expression=f"rank(f1) + {index}",
            priority=100 - index,
            settings_variant=SettingsVariant(),
            variant_fingerprint=f"initial-{index}",
        )
        for index in range(2)
    ]
    refreshed_entry = PendingTemplateEntry(
        template_name="refreshed",
        template_family="rank",
        template_stage="feedback",
        template_role="signal",
        template_activation_scope="feedback_only",
        expression="ts_rank(f1, 20)",
        priority=120,
        settings_variant=SettingsVariant(),
        variant_fingerprint="refreshed",
    )
    refresh_calls = 0

    def _refresh_feedback(template_build_ctx, _results) -> RuntimeFeedbackRefresh:
        nonlocal refresh_calls
        refresh_calls += 1
        if refresh_calls == 2:
            template_build_ctx.feedback_result_count = 1
            return RuntimeFeedbackRefresh(
                feedback_changed=True,
                changed_field_ids=frozenset({"f1"}),
            )
        return RuntimeFeedbackRefresh(feedback_changed=False)

    with (
        context.executor,
        patch(
            "alpha.app.run_loop_rounds.refresh_runtime_feedback",
            side_effect=_refresh_feedback,
        ),
        patch("alpha.app.run_loop_rounds.should_skip_field", return_value=False),
        patch(
            "alpha.app.run_loop_rounds.build_pending_templates_for_field",
            side_effect=[
                (initial_entries, 0, 2),
                ([refreshed_entry], 0, 1),
            ],
        ) as mock_build,
        patch("alpha.app.run_loop_dispatch.maybe_restore_runtime_concurrency"),
        patch("alpha.app.run_loop_dispatch.drain_until_capacity", return_value=True),
        patch("alpha.app.run_loop_dispatch.throttle_before_submission"),
        patch("alpha.app.run_loop_dispatch.submit_template_future") as mock_submit,
        patch("alpha.app.run_loop_rounds.persist_field_progress"),
    ):
        for round_index in (1, 2):
            schedule_field_round(
                context=context,
                field=context.fields[0],
                field_index=1,
                total_fields=1,
                round_index=round_index,
            )

    assert mock_build.call_count == 2
    assert [call.kwargs["expression"] for call in mock_submit.call_args_list] == [
        "rank(f1) + 0",
        "ts_rank(f1, 20)",
    ]


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

    assert dispatch_templates_for_field(**kwargs) is True
    assert context.run_ctx.execution_state.future_queue.scheduling_stop_signal.is_set()
    assert context.run_ctx.execution_state.future_queue.stop_signal.is_set() is False

    context.scheduler_options = SchedulerControlOptions(stop_after_submittable=0)
    context.run_ctx.execution_state.future_queue.scheduling_stop_signal.clear()
    with (
        patch("alpha.app.run_loop_dispatch.maybe_restore_runtime_concurrency"),
        patch("alpha.app.run_loop_dispatch.drain_until_capacity", return_value=False),
        patch("alpha.app.run_loop_dispatch.submit_template_future") as mock_submit,
    ):
        assert dispatch_templates_for_field(**kwargs) is False
    mock_submit.assert_not_called()

    with (
        patch("alpha.app.run_loop_dispatch.maybe_restore_runtime_concurrency"),
        patch("alpha.app.run_loop_dispatch.drain_until_capacity", return_value=True),
        patch("alpha.app.run_loop_dispatch.throttle_before_submission"),
        patch("alpha.app.run_loop_dispatch.submit_template_future") as mock_submit,
    ):
        assert dispatch_templates_for_field(**kwargs) is False
    mock_submit.assert_called_once()


def test_dispatch_replans_when_capacity_drain_changes_feedback() -> None:
    context = _build_context(field_template_batch_size=2, field_ids=("f1", "f2"))
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
    context.field_template_queues["f1"] = FieldTemplateQueue.create(
        entries,
        filtered_templates=0,
        template_count=2,
    )
    context.field_template_queues["f2"] = FieldTemplateQueue.create(
        entries,
        filtered_templates=0,
        template_count=2,
    )

    def _drain_with_result(**_kwargs) -> bool:
        context.run_ctx.execution_state.result_ledger.append(
            FieldTestResult(
                field_id="f1",
                field_type="MATRIX",
                field_name="f1",
                template_name="prior",
                status="simulated",
            )
        )
        return True

    with (
        patch("alpha.app.run_loop_dispatch.maybe_restore_runtime_concurrency"),
        patch(
            "alpha.app.run_loop_dispatch.drain_until_capacity",
            side_effect=_drain_with_result,
        ),
        patch(
            "alpha.app.run_loop_dispatch.refresh_runtime_feedback",
            return_value=RuntimeFeedbackRefresh(
                feedback_changed=True,
                changed_field_ids=frozenset({"f1"}),
            ),
        ),
        patch("alpha.app.run_loop_dispatch.submit_template_future") as mock_submit,
    ):
        stopped = dispatch_templates_for_field(
            context=context,
            field=context.fields[0],
            field_id="f1",
            field_name="f1",
            field_type="MATRIX",
            scheduled_templates=entries,
            template_queue=context.field_template_queues["f1"],
        )

    assert stopped is False
    assert set(context.field_template_queues) == {"f2"}
    mock_submit.assert_not_called()


def test_dispatch_stops_at_total_simulation_budget_without_aborting_pending() -> None:
    context = _build_context(field_template_batch_size=2)
    context.scheduler_options = SchedulerControlOptions(max_total_simulations=1)
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
        patch("alpha.app.run_loop_dispatch.maybe_restore_runtime_concurrency"),
        patch("alpha.app.run_loop_dispatch.drain_until_capacity", return_value=True),
        patch("alpha.app.run_loop_dispatch.throttle_before_submission"),
        patch("alpha.app.run_loop_dispatch.submit_template_future") as mock_submit,
    ):
        stopped = dispatch_templates_for_field(
            context=context,
            field=context.fields[0],
            field_id="f1",
            field_name="f1",
            field_type="MATRIX",
            scheduled_templates=entries,
        )

    assert stopped is True
    assert context.scheduled_simulations == 1
    assert context.run_ctx.execution_state.future_queue.scheduling_stop_signal.is_set() is False
    assert context.run_ctx.execution_state.future_queue.stop_signal.is_set() is False
    mock_submit.assert_called_once()
