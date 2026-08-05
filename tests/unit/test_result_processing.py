"""Typed result-processing service assembly tests."""

from __future__ import annotations

import alpha.analysis.results_persistence as results_persistence
import alpha.core.result_processing as result_processing
from alpha.models.domain import FieldTestResult
from alpha.models.runtime import ExecutionState, FutureCompletionContext, ResultWriteOptions


def test_build_result_processing_services_reads_current_dependencies(monkeypatch) -> None:
    """Late test/plugin overrides should be captured for each processing call."""

    def attempted(_result) -> bool:
        return False

    def writer(*_args, **_kwargs) -> int:
        return 7

    monkeypatch.setattr(result_processing, "is_attempted_result", attempted)
    monkeypatch.setattr(results_persistence, "dump_results_incremental", writer)

    services = result_processing.build_result_processing_services()

    assert services.is_attempted_result is attempted
    assert services.dump_results_incremental is writer
    assert services.result_identity is result_processing.result_identity


def test_failed_result_persistence_does_not_commit_runtime_state(monkeypatch, tmp_path) -> None:
    result = FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="tpl",
        expression="rank(field_1)",
        status="simulated",
        submittable=True,
    )
    state = ExecutionState.create()
    context = FutureCompletionContext(
        result_write_options=ResultWriteOptions(
            dataset_id="fundamental6",
            output_path=str(tmp_path / "results.json"),
        ),
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
    )

    def fail_writer(*_args, **_kwargs):
        raise OSError("summary write failed")

    monkeypatch.setattr(results_persistence, "dump_results_incremental", fail_writer)
    try:
        result_processing.apply_completed_result(
            result, completion_ctx=context, execution_state=state
        )
    except OSError:
        pass
    else:
        raise AssertionError("persistence failure should be raised")

    assert state.result_ledger.results == []
    assert state.result_ledger.persisted_result_count == 0
    assert state.template_stats == {}
    assert state.attempted_keys == set()

    monkeypatch.setattr(results_persistence, "dump_results_incremental", lambda *_a, **_k: 1)
    result_processing.apply_completed_result(result, completion_ctx=context, execution_state=state)
    assert state.result_ledger.results == [result]
    assert state.result_ledger.persisted_result_count == 1
    assert state.attempted_keys == {result_processing.result_identity(result)}


def test_blacklist_write_failure_does_not_abort_completed_result(monkeypatch, tmp_path) -> None:
    result = FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="tpl",
        expression="rank(field_1)",
        status="simulated",
        submittable=False,
    )
    state = ExecutionState.create()
    context = FutureCompletionContext(
        result_write_options=ResultWriteOptions(
            dataset_id="fundamental6",
            output_path=str(tmp_path / "results.json"),
            auto_update_blacklist=True,
            auto_update_blacklist_mode="staging",
        ),
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
    )

    monkeypatch.setattr(results_persistence, "dump_results_incremental", lambda *_a, **_k: 1)

    def _fail_blacklist(*_args, **_kwargs):
        raise OSError("blacklist is read-only")

    monkeypatch.setattr(
        result_processing,
        "auto_update_blacklist_incremental",
        _fail_blacklist,
    )

    result_processing.apply_completed_result(
        result,
        completion_ctx=context,
        execution_state=state,
    )

    assert state.result_ledger.results == [result]
    assert state.result_ledger.persisted_result_count == 1
    assert state.attempted_keys == {result_processing.result_identity(result)}


def test_worker_failure_is_persisted_without_marking_candidate_attempted(monkeypatch, tmp_path) -> None:
    result = FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="tpl",
        expression="rank(field_1)",
        settings_fingerprint="settings",
        status="error",
        failed_stage="worker",
        message="connection reset",
    )
    state = ExecutionState.create()
    context = FutureCompletionContext(
        result_write_options=ResultWriteOptions(
            dataset_id="fundamental6",
            output_path=str(tmp_path / "results.json"),
        ),
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
    )
    monkeypatch.setattr(results_persistence, "dump_results_incremental", lambda *_a, **_k: 1)

    result_processing.apply_completed_result(
        result,
        completion_ctx=context,
        execution_state=state,
    )

    assert state.result_ledger.results == [result]
    assert state.attempted_keys == set()
