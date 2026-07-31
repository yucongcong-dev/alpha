"""Derived execution-state metric tests."""

from __future__ import annotations

from concurrent.futures import Future
from unittest.mock import patch

from alpha.app.bootstrap_state import create_execution_state
from alpha.config.application_sections import QualityConfig
from alpha.models.domain import FieldTestResult
from alpha.runtime.contexts import HistoricalRunState, PendingFutureContext
from alpha.runtime.state import ExecutionState


def _state() -> ExecutionState:
    return ExecutionState.create()


def test_execution_metrics_follow_results_without_manual_refresh() -> None:
    state = _state()
    state.result_ledger.append(
        FieldTestResult(
            field_id="field_1",
            field_type="MATRIX",
            field_name="field_1",
            template_name="tpl",
            status="simulated",
            submittable=True,
            submitted=True,
            expression="rank(field_1)",
        )
    )

    ledger = state.result_ledger
    assert ledger.unique_field_ids == {"field_1"}
    assert ledger.submittable_count == 1
    assert ledger.submitted_count == 1
    assert ledger.error_count == 0

    ledger.results.clear()
    assert ledger.unique_field_ids == set()
    assert ledger.submittable_count == 0


def test_queue_retry_state_updates_legacy_views() -> None:
    state = _state()
    key = ("field_1", "template_1", "rank(field_1)", "settings")

    update = state.queue_retry_state.register_busy(key, retry_limit=2)
    assert update.next_count == 1
    assert update.exhausted is False
    assert state.queue_retry_counts[key] == 1
    assert state.queue_exhausted_keys == set()

    update = state.queue_retry_state.register_busy(key, retry_limit=2)
    assert update.next_count == 2
    assert update.exhausted is True
    assert key in state.queue_exhausted_keys

    state.reset_transient_queue_state()
    assert state.queue_retry_counts == {}
    assert state.queue_exhausted_keys == set()


def test_result_ledger_owns_results_and_stop_threshold() -> None:
    state = _state()
    result = FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="tpl",
        status="simulated",
        submittable=True,
        expression="rank(field_1)",
    )

    ledger = state.result_ledger
    metrics = ledger.append(result)

    assert metrics.submittable_count == 1
    assert ledger.results == [result]

    ledger.append(
        FieldTestResult(
            field_id="field_2",
            field_type="MATRIX",
            field_name="field_2",
            template_name="tpl",
            status="simulated",
            submittable=True,
            expression="rank(field_2)",
        )
    )
    assert len(ledger.results) == 2
    assert ledger.reached_submittable_stop_threshold(1) is True


def test_execution_state_create_copies_runtime_inputs() -> None:
    result = FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="tpl",
        status="simulated",
        expression="rank(field_1)",
    )
    attempted_key = ("field_1", "tpl", "rank(field_1)", "settings")
    initial_results = [result]
    attempted_keys = {attempted_key}

    state = ExecutionState.create(
        initial_results=initial_results,
        attempted_keys=attempted_keys,
        template_stats={"tpl": {"attempted": 1}},
    )
    initial_results.clear()
    attempted_keys.clear()

    assert state.result_ledger.results == [result]
    assert state.attempted_keys == {attempted_key}
    assert state.template_stats == {"tpl": {"attempted": 1}}


def test_result_ledger_owns_runtime_counters() -> None:
    state = _state()
    ledger = state.result_ledger
    ledger.submittable_baseline_count = 2
    ledger.persisted_result_count = 3

    assert state.result_ledger.submittable_baseline_count == 2
    assert state.result_ledger.persisted_result_count == 3


def test_future_queue_containers_keep_legacy_views() -> None:
    state = _state()
    future: Future[FieldTestResult] = Future()
    context = PendingFutureContext(field_id="field_1", template_name="template_1")

    state.future_queue.register(future, context)
    assert state.future_queue.pending_futures == {future: context}
    assert state.future_queue.pop_completed(future) == context
    assert state.future_queue.pending_futures == {}

    state.future_queue.replace_resumable_batch([context])
    assert state.future_queue.resumable_simulations == [context]
    pending_contexts = state.future_queue.take_resumable_batch()
    assert pending_contexts == [context]
    assert state.future_queue.resumable_simulations == []

    state.future_queue.restore_resumable_batch(pending_contexts)
    assert state.future_queue.resumable_simulations == [context]


def test_execution_state_create_copies_future_queue_inputs() -> None:
    future: Future[FieldTestResult] = Future()
    pending_context = PendingFutureContext(field_id="pending")
    resumable_context = PendingFutureContext(field_id="resumable")
    pending_futures = {future: pending_context}
    resumable_simulations = [resumable_context]

    state = ExecutionState.create(
        pending_futures=pending_futures,
        resumable_simulations=resumable_simulations,
    )
    pending_futures.clear()
    resumable_simulations.clear()

    assert state.future_queue.pending_futures == {future: pending_context}
    assert state.future_queue.resumable_simulations == [resumable_context]


def test_bootstrap_baseline_excludes_historical_submittable_results() -> None:
    historical = FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="tpl",
        status="simulated",
        submittable=True,
        expression="rank(field_1)",
    )
    with (
        patch("alpha.app.bootstrap_state.build_blacklist_runtime_stats", return_value={}),
        patch("alpha.app.bootstrap_state.load_blacklisted_template_keys", return_value=set()),
    ):
        state = create_execution_state(
            dataset_id="fundamental6",
            historical_state=HistoricalRunState(existing_results=[historical]),
        )

    ledger = state.result_ledger
    assert ledger.submittable_baseline_count == 1
    assert ledger.current_run_submittable_count == 0
    assert ledger.reached_submittable_stop_threshold(1) is False

    ledger.append(
        FieldTestResult(
            field_id="field_2",
            field_type="MATRIX",
            field_name="field_2",
            template_name="tpl",
            status="simulated",
            submittable=True,
            expression="rank(field_2)",
        )
    )
    assert ledger.current_run_submittable_count == 1
    assert ledger.reached_submittable_stop_threshold(1) is True
    assert ledger.submitted_count == 0


def test_quality_config_rejects_inverted_turnover_range() -> None:
    try:
        QualityConfig(
            min_sharpe=1.0,
            min_fitness=1.0,
            min_turnover=0.8,
            max_turnover=0.2,
            max_weight=0.1,
        )
    except ValueError as exc:
        assert "min_turnover" in str(exc)
    else:
        raise AssertionError("inverted turnover bounds must be rejected")
