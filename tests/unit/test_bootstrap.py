"""Bootstrap path precedence tests."""

from __future__ import annotations

import argparse

from alpha.app.bootstrap import initialize_run_context
from alpha.models.io_types import RunFilters, RunPaths
from alpha.models.runtime import ExecutionState, HistoricalRunState


def _build_args() -> argparse.Namespace:
    return argparse.Namespace(
        output="",
        log_file="",
        template_library_file="",
        fields_cache_file="raw-cache.json",
        creds_file="raw-creds.json",
        creds_key_file="raw-creds.key",
        email=None,
        password=None,
        dataset_id="fundamental6",
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
        page_size=50,
        max_concurrent_simulations=1,
        max_concurrent_creates=1,
        simulation_max_pending_cycles=10,
        offset=0,
        limit=10,
        top_fields_by_feedback=0,
        include_fields_file="",
        exclude_fields_file="",
        include_templates_file="",
        exclude_templates_file="",
    )


def test_initialize_run_context_prefers_run_paths_for_cache_and_credentials(monkeypatch) -> None:
    """Runtime initialization should honor normalized run_paths before raw args paths."""
    args = _build_args()
    run_paths = RunPaths(
        results_dir="/tmp/results",
        log_file="/tmp/run.log",
        state_file="/tmp/state.json",
        checkpoint_file="/tmp/checkpoint.json",
        blacklists_dir="/tmp/blacklists",
        fields_cache_file="/tmp/normalized-fields.json",
        template_library_file="/tmp/templates.json",
        output="/tmp/output.json",
        feedback_output="/tmp/feedback.json",
        creds_file="/tmp/normalized-creds.json",
        creds_key_file="/tmp/normalized-creds.key",
    )
    captured: dict[str, str] = {}

    monkeypatch.setattr("alpha.app.bootstrap.setup_runtime_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "alpha.app.bootstrap.cleanup_legacy_sidecar_files", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr("alpha.app.bootstrap.ensure_analysis_synced", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("alpha.app.bootstrap.build_run_config_snapshot", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        "alpha.app.bootstrap.ensure_dataset_template_library",
        lambda template_library_file, _dataset_id: template_library_file,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.ensure_template_blacklist_file", lambda *_args, **_kwargs: None
    )

    def _capture_credentials(passed_args):
        captured["creds_file"] = passed_args.creds_file
        captured["creds_key_file"] = passed_args.creds_key_file
        return "user@example.com", "secret"

    monkeypatch.setattr("alpha.app.bootstrap.load_credentials", _capture_credentials)
    monkeypatch.setattr(
        "alpha.app.bootstrap.create_and_login_client",
        lambda *_args, **_kwargs: ("bootstrap-client", "worker-factory"),
    )
    monkeypatch.setattr("alpha.app.bootstrap.load_template_library", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        "alpha.app.bootstrap.load_run_filters_extended", lambda *_args, **_kwargs: RunFilters()
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.get_dataset_expression_policy",
        lambda *_args, **_kwargs: type("Policy", (), {"use_curated_heuristics": False})(),
    )
    monkeypatch.setattr("alpha.app.bootstrap.stable_fingerprint", lambda *_args, **_kwargs: "tpl-fp")
    monkeypatch.setattr(
        "alpha.app.bootstrap.build_settings_fingerprint", lambda *_args, **_kwargs: "settings-fp"
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.build_historical_run_state",
        lambda *_args, **_kwargs: HistoricalRunState(),
    )

    def _capture_cache_path(cache_path, **_kwargs):
        captured["fields_cache_file"] = cache_path
        return []

    monkeypatch.setattr("alpha.app.bootstrap.load_fields_cache", _capture_cache_path)
    monkeypatch.setattr(
        "alpha.app.bootstrap.fetch_fields_with_cache",
        lambda *_args, **_kwargs: [{"id": "field_1", "type": "MATRIX", "name": "field_1"}],
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.prepare_fields_for_execution",
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
        "alpha.app.bootstrap.build_execution_state",
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
    assert run_ctx.blacklists_dir == run_paths.blacklists_dir
    assert args.creds_file == "raw-creds.json"
    assert args.creds_key_file == "raw-creds.key"


def test_initialize_run_context_builds_fallback_run_paths_when_missing(monkeypatch) -> None:
    """Initialization should build a minimal RunPaths snapshot when no normalized paths are passed."""
    args = _build_args()
    args.output = "/tmp/raw-output.json"
    args.template_library_file = "/tmp/raw-templates.json"
    args.include_fields_file = "/tmp/include_fields.txt"
    args.exclude_templates_file = "/tmp/exclude_templates.txt"
    captured: dict[str, object] = {}

    monkeypatch.setattr("alpha.app.bootstrap.setup_runtime_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "alpha.app.bootstrap.cleanup_legacy_sidecar_files", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr("alpha.app.bootstrap.ensure_analysis_synced", lambda *_args, **_kwargs: None)

    def _capture_run_config(_args, run_paths):
        captured["run_paths"] = run_paths
        return {"paths": {"output": run_paths.output}}

    monkeypatch.setattr("alpha.app.bootstrap.build_run_config_snapshot", _capture_run_config)
    monkeypatch.setattr(
        "alpha.app.bootstrap.ensure_dataset_template_library",
        lambda template_library_file, _dataset_id: template_library_file,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.ensure_template_blacklist_file", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.load_credentials",
        lambda *_args, **_kwargs: ("user@example.com", "secret"),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.create_and_login_client",
        lambda *_args, **_kwargs: ("bootstrap-client", "worker-factory"),
    )
    monkeypatch.setattr("alpha.app.bootstrap.load_template_library", lambda *_args, **_kwargs: {})

    def _capture_filters(run_paths):
        captured["filter_paths"] = run_paths
        return RunFilters()

    monkeypatch.setattr("alpha.app.bootstrap.load_run_filters_extended", _capture_filters)
    monkeypatch.setattr(
        "alpha.app.bootstrap.get_dataset_expression_policy",
        lambda *_args, **_kwargs: type("Policy", (), {"use_curated_heuristics": False})(),
    )
    monkeypatch.setattr("alpha.app.bootstrap.stable_fingerprint", lambda *_args, **_kwargs: "tpl-fp")
    monkeypatch.setattr(
        "alpha.app.bootstrap.build_settings_fingerprint", lambda *_args, **_kwargs: "settings-fp"
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.build_historical_run_state",
        lambda *_args, **_kwargs: HistoricalRunState(),
    )
    monkeypatch.setattr("alpha.app.bootstrap.load_fields_cache", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "alpha.app.bootstrap.fetch_fields_with_cache",
        lambda *_args, **_kwargs: [{"id": "field_1", "type": "MATRIX", "name": "field_1"}],
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.prepare_fields_for_execution",
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
        "alpha.app.bootstrap.build_execution_state",
        lambda **_kwargs: ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        ),
    )

    run_ctx = initialize_run_context(args, None)

    assert run_ctx is not None
    run_config_paths = captured["run_paths"]
    filter_paths = captured["filter_paths"]
    assert isinstance(run_config_paths, RunPaths)
    assert isinstance(filter_paths, RunPaths)
    assert run_config_paths.output == args.output
    assert run_config_paths.template_library_file == args.template_library_file
    assert isinstance(run_config_paths.blacklists_dir, str)
    assert run_config_paths.blacklists_dir
    assert filter_paths.include_fields_file == args.include_fields_file
    assert filter_paths.exclude_templates_file == args.exclude_templates_file
