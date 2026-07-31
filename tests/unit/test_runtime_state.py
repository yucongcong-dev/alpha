"""Derived execution-state metric tests."""

from __future__ import annotations

from concurrent.futures import Future
from unittest.mock import patch

from alpha.analysis.feedback_history import should_stop_after_submittable
from alpha.app.bootstrap_state import create_execution_state
from alpha.config.application_sections import QualityConfig
from alpha.models.domain import FieldTestResult
from alpha.runtime.contexts import HistoricalRunState, PendingFutureContext
from alpha.runtime.state import ExecutionState


def _state() -> ExecutionState:
    return ExecutionState(
        results=[],
        attempted_keys=set(),
        template_stats={},
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )


def test_execution_metrics_follow_results_without_manual_refresh() -> None:
    state = _state()
    state.results.append(
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

    assert state.unique_field_ids == {"field_1"}
    assert state.submittable_count == 1
    assert state.submitted_count == 1
    assert state.error_count == 0

    state.results.clear()
    assert state.unique_field_ids == set()
    assert state.submittable_count == 0


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


def test_result_ledger_state_updates_legacy_views() -> None:
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
    ledger.submittable_baseline_count = 1
    ledger.persisted_result_count = 1
    state.sync_result_ledger()

    assert metrics.submittable_count == 1
    assert state.results == [result]
    assert state.submittable_baseline_count == 1
    assert state.persisted_result_count == 1
    assert state.current_run_submittable_count == 0


def test_future_queue_state_updates_legacy_views() -> None:
    state = _state()
    future: Future[FieldTestResult] = Future()
    context = PendingFutureContext(field_id="field_1", template_name="template_1")

    state.future_queue.register(future, context)
    assert state.pending_futures == {future: context}
    assert state.future_queue.pop_completed(future) == context
    assert state.pending_futures == {}

    state.resumable_simulations = [context]
    pending_contexts = state.future_queue.take_resumable_batch()
    assert pending_contexts == [context]
    assert state.resumable_simulations == []

    state.future_queue.restore_resumable_batch(pending_contexts)
    assert state.resumable_simulations == [context]


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

    assert state.submittable_baseline_count == 1
    assert state.current_run_submittable_count == 0
    assert (
        should_stop_after_submittable(
            1,
            state.results,
            baseline_count=state.submittable_baseline_count,
        )
        is False
    )

    state.results.append(
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
    assert state.current_run_submittable_count == 1
    assert (
        should_stop_after_submittable(
            1,
            state.results,
            baseline_count=state.submittable_baseline_count,
        )
        is True
    )
    assert state.submitted_count == 0


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
