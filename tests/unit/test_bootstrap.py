"""Bootstrap path precedence tests."""

from __future__ import annotations

import argparse

from alpha.bootstrap import initialize_run_context
from alpha.models.base import ExecutionState, HistoricalRunState, RunFilters, RunPaths


def _build_args() -> argparse.Namespace:
    return argparse.Namespace(
        output="",
        log_file="",
        template_library_file="",
        fields_cache_file="raw-cache.json",
        creds_file="raw-creds.json",
        creds_key_file="raw-creds.key",
        dataset_id="fundamental6",
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
        max_concurrent_simulations=1,
        max_concurrent_creates=1,
        simulation_max_pending_cycles=10,
        offset=0,
        limit=10,
        top_fields_by_feedback=0,
    )


def test_initialize_run_context_prefers_run_paths_for_cache_and_credentials(monkeypatch) -> None:
    """Runtime initialization should honor normalized run_paths before raw args paths."""
    args = _build_args()
    run_paths = RunPaths(
        results_dir="/tmp/results",
        log_file="/tmp/run.log",
        state_file="/tmp/state.json",
        checkpoint_file="/tmp/checkpoint.json",
        fields_cache_file="/tmp/normalized-fields.json",
        template_library_file="/tmp/templates.json",
        output="/tmp/output.json",
        feedback_output="/tmp/feedback.json",
        creds_file="/tmp/normalized-creds.json",
        creds_key_file="/tmp/normalized-creds.key",
    )
    captured: dict[str, str] = {}

    monkeypatch.setattr("alpha.bootstrap.setup_runtime_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "alpha.bootstrap.cleanup_legacy_sidecar_files", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr("alpha.bootstrap.ensure_analysis_synced", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("alpha.bootstrap.build_run_config_snapshot", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        "alpha.bootstrap.ensure_dataset_template_library",
        lambda template_library_file, _dataset_id: template_library_file,
    )
    monkeypatch.setattr(
        "alpha.bootstrap.ensure_template_blacklist_file", lambda *_args, **_kwargs: None
    )

    def _capture_credentials(passed_args):
        captured["creds_file"] = passed_args.creds_file
        captured["creds_key_file"] = passed_args.creds_key_file
        return "user@example.com", "secret"

    monkeypatch.setattr("alpha.bootstrap.load_credentials", _capture_credentials)
    monkeypatch.setattr(
        "alpha.bootstrap.create_and_login_client",
        lambda *_args, **_kwargs: ("bootstrap-client", "worker-factory"),
    )
    monkeypatch.setattr("alpha.bootstrap.load_template_library", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("alpha.bootstrap.load_run_filters_extended", lambda *_args, **_kwargs: RunFilters())
    monkeypatch.setattr(
        "alpha.bootstrap.get_dataset_expression_policy",
        lambda *_args, **_kwargs: type("Policy", (), {"use_curated_heuristics": False})(),
    )
    monkeypatch.setattr("alpha.bootstrap.stable_fingerprint", lambda *_args, **_kwargs: "tpl-fp")
    monkeypatch.setattr(
        "alpha.bootstrap.build_settings_fingerprint", lambda *_args, **_kwargs: "settings-fp"
    )
    monkeypatch.setattr(
        "alpha.bootstrap.build_historical_run_state",
        lambda *_args, **_kwargs: HistoricalRunState(),
    )

    def _capture_cache_path(cache_path, **_kwargs):
        captured["fields_cache_file"] = cache_path
        return []

    monkeypatch.setattr("alpha.bootstrap.load_fields_cache", _capture_cache_path)
    monkeypatch.setattr(
        "alpha.bootstrap.fetch_fields_with_cache",
        lambda *_args, **_kwargs: [{"id": "field_1", "type": "MATRIX", "name": "field_1"}],
    )
    monkeypatch.setattr(
        "alpha.bootstrap.prepare_fields_for_execution",
        lambda fields, **_kwargs: (
            fields,
            {
                "prefiltered_count": 0,
                "low_coverage_count": 0,
                "low_date_coverage_count": 0,
                "low_alpha_count": 0,
                "low_user_count": 0,
                "cached_field_count": len(fields),
                "filtered_field_count": len(fields),
                "ranked_field_count": len(fields),
            },
        ),
    )
    monkeypatch.setattr(
        "alpha.bootstrap.build_execution_state",
        lambda **_kwargs: ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        ),
    )

    run_ctx = initialize_run_context(args, run_paths)

    assert run_ctx is not None
    assert captured["creds_file"] == run_paths.creds_file
    assert captured["creds_key_file"] == run_paths.creds_key_file
    assert captured["fields_cache_file"] == run_paths.fields_cache_file
    assert args.creds_file == run_paths.creds_file
    assert args.creds_key_file == run_paths.creds_key_file
