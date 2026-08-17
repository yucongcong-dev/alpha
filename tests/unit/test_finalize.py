"""Finalize output path precedence tests."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from threading import Semaphore
from unittest.mock import patch

import alpha.app.finalize as finalize_module
from alpha.app.finalize import finalize_run
from alpha.config.application import ApplicationConfig
from alpha.core.pending_check_refresh import PendingCheckRefreshResult
from alpha.models.domain import FieldTestResult
from alpha.models.io_types import RunFilters, RunPaths
from alpha.runtime.concurrency import RuntimeConcurrencyState
from alpha.runtime.contexts import HistoricalRunState
from alpha.runtime.state import ExecutionState, InitializedRunContext


def _build_run_ctx(*, client_factory=None) -> InitializedRunContext:
    return InitializedRunContext(
        client_factory=client_factory,
        template_library={},
        filters=RunFilters(),
        expression_policy=None,
        template_library_fingerprint="tpl-fp",
        settings_fingerprint="settings-fp",
        run_fingerprint="run-fp",
        historical_state=HistoricalRunState(),
        fields=[],
        execution_state=ExecutionState.create(),
        runtime_state=RuntimeConcurrencyState(max_workers=1, runtime_max_workers=1),
        create_semaphore=Semaphore(1),
        run_config={},
    )


def _build_config(args: argparse.Namespace, run_paths: RunPaths) -> ApplicationConfig:
    return ApplicationConfig.from_args(args, run_paths)


def test_finalize_run_uses_application_paths(monkeypatch, tmp_path) -> None:
    """Final flush should use the normalized paths owned by ApplicationConfig."""
    args = argparse.Namespace(
        output="raw-results.json",
        dataset_id="fundamental6",
    )
    run_paths = RunPaths(
        results_dir=str(tmp_path / "results"),
        log_file=str(tmp_path / "run.log"),
        state_file=str(tmp_path / "state.json"),
        checkpoint_file=str(tmp_path / "checkpoint.json"),
        output=str(tmp_path / "normalized-results.json"),
    )
    run_ctx = _build_run_ctx()

    with (
        patch("alpha.app.finalize.persist_results") as mock_persist,
        patch("alpha.app.finalize.delete_pipeline_state") as mock_delete,
    ):
        finalize_run(_build_config(args, run_paths), run_ctx)

    assert mock_persist.call_args.args[0].output_path == str(tmp_path / "normalized-results.json")
    assert mock_delete.call_args.args[0] == str(tmp_path / "state.json")


def test_finalize_run_updates_separate_feedback_output(tmp_path) -> None:
    """Finalization should merge current results into the separate feedback history."""
    result = FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="template_1",
        status="simulated",
        expression="rank(field_1)",
    )
    run_ctx = _build_run_ctx()
    run_ctx.execution_state.result_ledger.append(result)
    args = argparse.Namespace(
        output=str(tmp_path / "raw-results.json"),
        dataset_id="fundamental6",
    )
    run_paths = RunPaths(
        results_dir=str(tmp_path),
        log_file=str(tmp_path / "run.log"),
        checkpoint_file=str(tmp_path / "checkpoint.json"),
        output=str(tmp_path / "results.json"),
        feedback_output=str(tmp_path / "feedback.json"),
        state_file=str(tmp_path / "state.json"),
    )

    with (
        patch("alpha.app.finalize.persist_results") as mock_persist,
        patch("alpha.app.finalize.load_existing_results", return_value=[]),
        patch("alpha.app.finalize.exclusive_results_transaction", return_value=nullcontext()),
        patch("alpha.app.finalize.persist_feedback_run_index") as mock_persist_index,
        patch("alpha.app.finalize.delete_pipeline_state") as mock_delete,
    ):
        finalize_run(_build_config(args, run_paths), run_ctx)

    assert [call.args[0].output_path for call in mock_persist.call_args_list] == [
        str(tmp_path / "results.json"),
        str(tmp_path / "feedback.json"),
    ]
    assert mock_persist.call_args_list[-1].args[1] == [result]
    assert mock_persist.call_args_list[-1].args[0].metadata_scope == "feedback"
    mock_persist_index.assert_called_once_with(str(tmp_path / "feedback.json"))
    mock_delete.assert_called_once_with(str(tmp_path / "state.json"))


def test_finalize_run_reconciles_pending_checks_before_persisting(tmp_path, caplog) -> None:
    caplog.set_level("INFO")
    pending = FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="template_1",
        alpha_id="alpha_1",
        status="simulated",
        submittable=None,
        message="checks pending",
        expression="rank(field_1)",
    )
    resolved = FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="template_1",
        alpha_id="alpha_1",
        status="simulated",
        submittable=True,
        message="checks passed",
        expression="rank(field_1)",
        updated_at="2026-08-13T00:00:00Z",
    )
    client_factory = object()
    run_ctx = _build_run_ctx(client_factory=client_factory)
    run_ctx.execution_state.result_ledger.append(pending)
    args = argparse.Namespace(
        output=str(tmp_path / "raw-results.json"),
        dataset_id="fundamental6",
        check_submission_retries=3,
    )
    run_paths = RunPaths(
        results_dir=str(tmp_path),
        log_file=str(tmp_path / "run.log"),
        checkpoint_file=str(tmp_path / "checkpoint.json"),
        output=str(tmp_path / "results.json"),
        state_file=str(tmp_path / "state.json"),
    )

    with (
        patch.object(
            finalize_module.PendingCheckService,
            "refresh",
            return_value=PendingCheckRefreshResult(
                results=[resolved],
                resolved_count=1,
                attempted_alpha_ids=frozenset({"alpha_1"}),
            ),
        ) as mock_refresh,
        patch("alpha.app.finalize.persist_results") as mock_persist,
        patch("alpha.app.finalize.delete_pipeline_state"),
    ):
        finalize_run(_build_config(args, run_paths), run_ctx)

    mock_refresh.assert_called_once_with([pending])
    assert mock_persist.call_args.args[1] == [resolved]
    assert run_ctx.execution_state.result_ledger.pending_check_count == 0
    assert "[check-submission-finalize] attempted=1 resolved=1 remaining=0" in caplog.text
