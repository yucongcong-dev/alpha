"""Full-run seed-phase scheduling tests."""

from __future__ import annotations

from concurrent.futures import Future
from unittest.mock import patch

from alpha.app.run_loop_feedback import RuntimeFeedbackRefresh
from alpha.app.run_loop_rounds import execute_schedule_round
from alpha.models.domain import FieldTestResult, SettingsVariant
from alpha.runtime.contexts import PendingFutureContext, PendingTemplateEntry
from tests.unit.run_loop_rounds_support import build_round_context as _build_context


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
        patch("alpha.app.run_loop_rounds.persist_replanning_checkpoint"),
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
        patch("alpha.app.run_loop_rounds.persist_replanning_checkpoint"),
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
        patch("alpha.app.run_loop_rounds.persist_replanning_checkpoint"),
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
        patch("alpha.app.run_loop_rounds.persist_replanning_checkpoint"),
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
        patch("alpha.app.run_loop_rounds.persist_replanning_checkpoint"),
    ):
        seed_round = execute_schedule_round(context, round_index=1)
        assert seed_round.progressed is True
        assert context.seed_phase.active is False

        refine_round = execute_schedule_round(context, round_index=2)

    assert refine_round.progressed is True
    assert planned_field_ids == ["f2", "f1"]
    assert dispatched_field_ids == ["f1"]
