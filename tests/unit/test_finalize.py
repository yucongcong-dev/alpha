"""Finalize output path precedence tests."""

from __future__ import annotations

import argparse
from threading import Semaphore
from unittest.mock import patch

from alpha.app.finalize import finalize_run
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
        blacklists_dir="/tmp/blacklists",
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
        blacklists_dir="/tmp/blacklists",
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
