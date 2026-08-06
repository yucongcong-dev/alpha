"""Breadth-first run-loop scheduling tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from alpha.app.run_loop_dispatch import dispatch_templates_for_field
from alpha.app.run_loop_feedback import RuntimeFeedbackRefresh
from alpha.app.run_loop_rounds import (
    ScheduleRoundResult,
    execute_schedule_round,
    schedule_field_round,
)
from alpha.models.domain import FieldTestResult, SettingsVariant
from alpha.models.runtime import (
    PendingTemplateEntry,
    TemplateBuildContext,
)
from alpha.models.runtime_options import SchedulerControlOptions
from alpha.runtime.field_template_queue import FieldTemplateQueue
from tests.unit.run_loop_rounds_support import build_round_context as _build_context


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


def test_submittable_result_does_not_stop_new_round() -> None:
    context = _build_context(field_template_batch_size=1)
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
        patch("alpha.app.run_loop_dispatch.drain_until_capacity"),
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
        patch("alpha.app.run_loop_dispatch.drain_until_capacity"),
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


def test_dispatch_honors_success_path() -> None:
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

    with (
        patch("alpha.app.run_loop_dispatch.maybe_restore_runtime_concurrency"),
        patch("alpha.app.run_loop_dispatch.drain_until_capacity"),
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

    def _drain_with_result(**_kwargs) -> None:
        context.run_ctx.execution_state.result_ledger.append(
            FieldTestResult(
                field_id="f1",
                field_type="MATRIX",
                field_name="f1",
                template_name="prior",
                status="simulated",
            )
        )

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
        patch("alpha.app.run_loop_dispatch.drain_until_capacity"),
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
    assert context.run_ctx.execution_state.future_queue.stop_signal.is_set() is False
    mock_submit.assert_called_once()
