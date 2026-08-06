"""Seed-first scheduling state tests."""

from concurrent.futures import Future

from alpha.app.run_loop_seed_phase import SeedPhaseState
from alpha.models.domain import FieldTestResult, TemplateField
from alpha.runtime.contexts import PendingFutureContext
from alpha.runtime.state import ExecutionState


def test_seed_phase_tracks_resolved_and_inflight_fields() -> None:
    fields = [TemplateField("f1", "f1", "MATRIX"), TemplateField("f2", "f2", "MATRIX")]
    state = SeedPhaseState.create(fields, enabled=True, resolved_field_ids={"f1", "outside"})
    execution_state = ExecutionState.create()
    pending: Future[FieldTestResult] = Future()
    execution_state.future_queue.register(pending, PendingFutureContext(field_id="f2"))

    state.sync(execution_state)

    assert state.total_count == 2
    assert state.resolved_field_ids == {"f1"}
    assert state.inflight_field_ids == {"f2"}
    assert state.remaining_count == 1
    assert state.active is True
    assert state.should_wait_or_skip("f2") is True


def test_seed_phase_completion_transitions_to_refine() -> None:
    fields = [TemplateField("f1", "f1", "MATRIX")]
    state = SeedPhaseState.create(fields, enabled=True)
    execution_state = ExecutionState.create()
    execution_state.attempted_keys.add(("f1", "seed", "rank(f1)", "settings"))

    state.sync(execution_state)

    assert state.resolved_count == 1
    assert state.remaining_count == 0
    assert state.active is False
    assert state.phase_name == "refine"


def test_seed_phase_dispatch_remains_inflight_until_attempt_is_persisted() -> None:
    fields = [TemplateField("f1", "f1", "MATRIX")]
    state = SeedPhaseState.create(fields, enabled=True)
    execution_state = ExecutionState.create()

    assert state.mark_inflight("f1") is True
    assert state.resolved_field_ids == set()
    assert state.inflight_field_ids == {"f1"}
    assert state.active is True

    execution_state.attempted_keys.add(("f1", "seed", "rank(f1)", "settings"))
    state.sync(execution_state)

    assert state.resolved_field_ids == {"f1"}
    assert state.inflight_field_ids == set()
    assert state.active is False


def test_seed_phase_failed_inflight_returns_to_remaining_pool() -> None:
    fields = [TemplateField("f1", "f1", "MATRIX")]
    state = SeedPhaseState.create(fields, enabled=True)
    execution_state = ExecutionState.create()

    state.mark_inflight("f1")
    state.sync(execution_state)

    assert state.resolved_field_ids == set()
    assert state.inflight_field_ids == set()
    assert state.remaining_count == 1
    assert state.should_wait_or_skip("f1") is False
