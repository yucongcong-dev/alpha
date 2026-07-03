"""Finalize output path precedence tests."""

from __future__ import annotations

import argparse
from dataclasses import replace
from threading import Semaphore
from unittest.mock import patch

from alpha.app.finalize import (
    finalize_run,
    recheck_pending_self_correlation_results,
    should_finalize_recheck_pending_self_correlation,
)
from alpha.models.domain import FieldTestResult
from alpha.models.io_types import RunFilters, RunPaths
from alpha.models.runtime import (
    ExecutionState,
    HistoricalRunState,
    InitializedRunContext,
    RuntimeConcurrencyState,
)


def _build_run_ctx() -> InitializedRunContext:
    return InitializedRunContext(
        client_factory=None,
        template_library={},
        filters=RunFilters(),
        expression_policy=None,
        use_dataset_heuristics=False,
        template_library_fingerprint="tpl-fp",
        settings_fingerprint="settings-fp",
        historical_state=HistoricalRunState(),
        fields=[],
        execution_state=ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        ),
        runtime_state=RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1),
        create_semaphore=Semaphore(1),
        run_config={},
    )


def test_finalize_run_prefers_run_paths_output(monkeypatch) -> None:
    """Final flush should honor normalized output paths over raw args.output."""
    args = argparse.Namespace(
        output="raw-results.json",
        dataset_id="fundamental6",
        auto_update_blacklist=False,
    )
    run_paths = RunPaths(
        results_dir="/tmp/results",
        log_file="/tmp/run.log",
        state_file="/tmp/state.json",
        checkpoint_file="/tmp/checkpoint.json",
        output="/tmp/normalized-results.json",
    )
    run_ctx = _build_run_ctx()

    with (
        patch("alpha.app.finalize.dump_results") as mock_dump,
        patch("alpha.app.finalize.delete_pipeline_state") as mock_delete,
    ):
        finalize_run(args, run_ctx, run_paths=run_paths)

    assert mock_dump.call_args.args[0] == "/tmp/normalized-results.json"
    assert mock_delete.call_args.args[0] == "/tmp/state.json"


def test_finalize_run_does_not_recheck_pending_self_correlation_by_default(monkeypatch) -> None:
    pending_result = FieldTestResult(
        field_id="f1",
        field_type="MATRIX",
        field_name="f1",
        template_name="tpl1",
        simulation_id="sim1",
        alpha_id="alpha1",
        status="pending_self_correlation",
        submittable=None,
        submitted=False,
        message="self correlation pending",
        expression="rank(f1)",
        settings_fingerprint="settings-fp",
        template_library_fingerprint="tpl-fp",
        failed_checks=[{"name": "SELF_CORRELATION", "result": "PENDING", "value": None, "limit": None}],
        self_correlation_pending_since=123.0,
    )
    run_ctx = replace(
        _build_run_ctx(),
        client_factory=type("Factory", (), {"get_client": lambda self: object()})(),
        execution_state=ExecutionState(
            results=[pending_result],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        ),
    )
    args = argparse.Namespace(
        output="raw-results.json",
        dataset_id="fundamental6",
        auto_update_blacklist=False,
        finalize_recheck_pending_self_correlation=False,
        check_submit_retries=3,
        self_correlation_max_polls=2,
        self_correlation_poll_seconds=0.0,
        submit=False,
        submit_retries=3,
    )

    with (
        patch("alpha.app.finalize.dump_results") as mock_dump,
        patch("alpha.app.finalize.delete_pipeline_state"),
        patch(
            "alpha.app.finalize.checksubmit_with_retry",
            return_value=(True, "checks passed", []),
        ) as mock_recheck,
    ):
        finalize_run(args, run_ctx)

    assert pending_result.submittable is None
    assert pending_result.status == "pending_self_correlation"
    assert pending_result.message == "self correlation pending"
    assert pending_result.self_correlation_pending_since == 123.0
    assert pending_result.self_correlation_recheck_count == 0
    assert pending_result.self_correlation_last_recheck_at == 0.0
    assert not mock_recheck.called
    dumped_results = mock_dump.call_args.args[2]
    assert dumped_results[0].submittable is None


def test_finalize_run_rechecks_pending_self_correlation_when_enabled() -> None:
    pending_result = FieldTestResult(
        field_id="f1",
        field_type="MATRIX",
        field_name="f1",
        template_name="tpl1",
        simulation_id="sim1",
        alpha_id="alpha1",
        status="pending_self_correlation",
        submittable=None,
        submitted=False,
        message="self correlation pending",
        expression="rank(f1)",
        settings_fingerprint="settings-fp",
        template_library_fingerprint="tpl-fp",
        failed_checks=[{"name": "SELF_CORRELATION", "result": "PENDING", "value": None, "limit": None}],
        self_correlation_pending_since=123.0,
    )
    run_ctx = replace(
        _build_run_ctx(),
        client_factory=type("Factory", (), {"get_client": lambda self: object()})(),
        execution_state=ExecutionState(
            results=[pending_result],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        ),
    )
    args = argparse.Namespace(
        output="raw-results.json",
        dataset_id="fundamental6",
        auto_update_blacklist=False,
        finalize_recheck_pending_self_correlation=True,
        check_submit_retries=3,
        self_correlation_max_polls=2,
        self_correlation_poll_seconds=0.0,
        submit=False,
        submit_retries=3,
    )

    with (
        patch("alpha.app.finalize.dump_results") as mock_dump,
        patch("alpha.app.finalize.delete_pipeline_state"),
        patch(
            "alpha.app.finalize.checksubmit_with_retry",
            return_value=(True, "checks passed", []),
        ) as mock_recheck,
    ):
        finalize_run(args, run_ctx)

    assert pending_result.submittable is True
    assert pending_result.status == "simulated"
    assert pending_result.message == "checks passed"
    assert pending_result.failed_checks == []
    assert pending_result.self_correlation_pending_since == 0.0
    assert pending_result.self_correlation_recheck_count == 1
    assert pending_result.self_correlation_last_recheck_at > 0.0
    assert mock_recheck.called
    dumped_results = mock_dump.call_args.args[2]
    assert dumped_results[0].submittable is True


def test_recheck_pending_self_correlation_results_returns_refresh_count() -> None:
    pending_result = FieldTestResult(
        field_id="f1",
        field_type="MATRIX",
        field_name="f1",
        template_name="tpl1",
        simulation_id="sim1",
        alpha_id="alpha1",
        status="pending_self_correlation",
        submittable=None,
        submitted=False,
        message="self correlation pending",
        expression="rank(f1)",
        settings_fingerprint="settings-fp",
        template_library_fingerprint="tpl-fp",
        failed_checks=[{"name": "SELF_CORRELATION", "result": "PENDING", "value": None, "limit": None}],
    )
    run_ctx = replace(
        _build_run_ctx(),
        client_factory=type("Factory", (), {"get_client": lambda self: object()})(),
        execution_state=ExecutionState(
            results=[pending_result],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        ),
    )
    args = argparse.Namespace(
        check_submit_retries=3,
        self_correlation_max_polls=1,
        self_correlation_poll_seconds=0.0,
        submit=False,
        submit_retries=3,
    )

    with patch(
        "alpha.app.finalize.checksubmit_with_retry",
        return_value=(None, "self correlation pending", pending_result.failed_checks),
    ):
        refreshed = recheck_pending_self_correlation_results(args, run_ctx)

    assert refreshed == 1


def test_should_finalize_recheck_pending_self_correlation_defaults_false() -> None:
    args = argparse.Namespace()
    assert should_finalize_recheck_pending_self_correlation(args) is False
