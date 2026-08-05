"""Bootstrap path precedence tests."""

from __future__ import annotations

import argparse
import logging
from types import SimpleNamespace

import pytest

import alpha.app.bootstrap as bootstrap_module
from alpha.app.bootstrap import initialize_run_context, prepare_bootstrap_resources
from alpha.app.bootstrap_field_resources import log_field_selection_stats
from alpha.app.bootstrap_supporting_resources import BootstrapLoadedResources
from alpha.models.domain import FieldTestResult, TemplateField
from alpha.models.io_types import RunFilters, RunPaths
from alpha.models.runtime import ExecutionState, HistoricalRunState
from alpha.models.runtime_options import FieldSelectionOptions


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
        decay=4,
        neutralization="SUBINDUSTRY",
        truncation=0.08,
        pasteurization="ON",
        unit_handling="VERIFY",
        nan_handling="OFF",
        max_trade="OFF",
        language="FASTEXPR",
        start_date=None,
        end_date=None,
        page_size=50,
        max_concurrent_simulations=1,
        max_concurrent_creates=1,
        simulation_max_pending_cycles=10,
        offset=0,
        limit=10,
        top_fields_by_feedback=0,
        max_templates_per_field=0,
        max_templates_per_family=0,
        legacy_similarity_penalty=0,
        include_fields_file="",
        exclude_fields_file="",
        include_templates_file="",
        exclude_templates_file="",
    )


def test_field_selection_log_describes_selected_execution_fields(caplog) -> None:
    caplog.set_level(logging.INFO, logger="alpha.app.bootstrap_field_resources")
    field = TemplateField("f1", "f1", "MATRIX")

    log_field_selection_stats(
        dataset_id="fundamental6",
        selection_options=FieldSelectionOptions(limit=1),
        field_stats={
            "prefiltered_count": 0,
            "low_coverage_count": 0,
            "low_date_coverage_count": 0,
            "low_alpha_count": 0,
            "low_user_count": 0,
            "high_alpha_count": 0,
            "high_user_count": 0,
            "unknown_coverage_count": 0,
            "unknown_date_coverage_count": 0,
            "unknown_alpha_count": 0,
            "unknown_user_count": 0,
            "cached_field_count": 10,
            "filtered_field_count": 4,
            "ranked_field_count": 4,
        },
        fields=[field],
    )

    assert "本次选中数据集 fundamental6 的 1 个字段进入执行" in caplog.text
    assert "从数据集 fundamental6 获取 1 个字段" not in caplog.text


def test_build_bootstrap_services_reads_current_module_dependencies(monkeypatch) -> None:
    """Service assembly should preserve late monkeypatch/plugin overrides."""

    def first_fingerprint(_payload) -> str:
        return "first"

    def second_fingerprint(_payload) -> str:
        return "second"

    def replacement_login(_client, _retries) -> None:
        return None

    monkeypatch.setattr(bootstrap_module, "stable_fingerprint", first_fingerprint)
    first_services = bootstrap_module.build_bootstrap_services()

    monkeypatch.setattr(bootstrap_module, "stable_fingerprint", second_fingerprint)
    monkeypatch.setattr(bootstrap_module, "login_with_retry", replacement_login)
    second_services = bootstrap_module.build_bootstrap_services()

    assert first_services.supporting_resources.stable_fingerprint is first_fingerprint
    assert second_services.supporting_resources.stable_fingerprint is second_fingerprint
    assert (
        second_services.runtime_outputs.cleanup_legacy_sidecar_files
        is bootstrap_module.cleanup_legacy_sidecar_files
    )
    assert (
        second_services.field_loading.prepare_fields_for_execution
        is bootstrap_module.prepare_fields_for_execution
    )
    assert second_services.credentials.load_credentials is bootstrap_module.load_credentials
    assert second_services.api_client.login_with_retry is replacement_login


def test_initialize_run_context_closes_clients_when_resources_are_unavailable(
    monkeypatch,
) -> None:
    args = _build_args()
    paths = SimpleNamespace(
        creds_file="creds.json",
        creds_key_file="creds.key",
    )
    closed: list[str] = []
    bootstrap_client = SimpleNamespace(close=lambda: closed.append("bootstrap"))
    client_factory = SimpleNamespace(close=lambda: closed.append("factory"))

    monkeypatch.setattr(bootstrap_module, "resolve_bootstrap_paths", lambda *_args: paths)
    monkeypatch.setattr(bootstrap_module, "prepare_runtime_outputs", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        bootstrap_module,
        "resolve_credentials",
        lambda *_args, **_kwargs: ("user@example.com", "secret"),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "create_and_login_client",
        lambda *_args, **_kwargs: (bootstrap_client, client_factory),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "prepare_bootstrap_resources",
        lambda *_args, **_kwargs: None,
    )

    assert initialize_run_context(args, None) is None
    assert closed == ["bootstrap", "factory"]


def test_initialize_run_context_closes_factory_when_state_build_fails(monkeypatch) -> None:
    args = _build_args()
    paths = SimpleNamespace(
        creds_file="creds.json",
        creds_key_file="creds.key",
        output_file="results.json",
        datasets_root="datasets",
    )
    closed: list[str] = []
    bootstrap_client = SimpleNamespace(close=lambda: closed.append("bootstrap"))
    client_factory = SimpleNamespace(close=lambda: closed.append("factory"))
    prepared = SimpleNamespace(
        historical_state=HistoricalRunState(),
        settings_fingerprint="settings-fp",
        template_library_fingerprint="templates-fp",
        run_config={},
    )

    monkeypatch.setattr(bootstrap_module, "resolve_bootstrap_paths", lambda *_args: paths)
    monkeypatch.setattr(bootstrap_module, "prepare_runtime_outputs", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        bootstrap_module,
        "resolve_credentials",
        lambda *_args, **_kwargs: ("user@example.com", "secret"),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "create_and_login_client",
        lambda *_args, **_kwargs: (bootstrap_client, client_factory),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "prepare_bootstrap_resources",
        lambda *_args, **_kwargs: prepared,
    )

    def _fail_state_build(**_kwargs):
        raise RuntimeError("state failed")

    monkeypatch.setattr(
        bootstrap_module,
        "build_execution_state",
        _fail_state_build,
    )

    with pytest.raises(RuntimeError, match="state failed"):
        initialize_run_context(args, None)

    assert closed == ["bootstrap", "factory"]


def test_prepare_bootstrap_resources_persists_pending_refresh_before_empty_field_return(
    monkeypatch,
) -> None:
    original = FieldTestResult(
        field_id="f1",
        field_type="MATRIX",
        field_name="f1",
        template_name="t1",
    )
    refreshed = FieldTestResult(
        field_id="f1",
        field_type="MATRIX",
        field_name="f1",
        template_name="t1",
        updated_at="2026-08-04T00:00:00Z",
    )
    historical_state = HistoricalRunState(existing_results=[original])
    expression_policy = SimpleNamespace(
        policy_version="policy-v1",
        feedback_scope="field_type",
        use_curated_heuristics=True,
    )
    supporting_resources = BootstrapLoadedResources(
        historical_state=historical_state,
        expression_policy=expression_policy,
        template_library={"MATRIX": []},
        filters={},
    )
    persisted: dict[str, object] = {}

    monkeypatch.setattr(
        bootstrap_module,
        "build_effective_run_paths",
        lambda *_args: SimpleNamespace(),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "load_bootstrap_supporting_resources",
        lambda **_kwargs: supporting_resources,
    )
    monkeypatch.setattr(
        bootstrap_module,
        "refresh_pending_check_results",
        lambda *_args, **_kwargs: ([refreshed], 1),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "rebuild_historical_run_state",
        lambda _state, results: HistoricalRunState(existing_results=list(results)),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "persist_reconciled_historical_results",
        lambda **kwargs: persisted.update(kwargs),
    )
    monkeypatch.setattr(bootstrap_module, "load_bootstrap_fields", lambda **_kwargs: [])

    result = prepare_bootstrap_resources(
        SimpleNamespace(),
        SimpleNamespace(dataset_id="fundamental6", check_submission_retries=1, fetch=None),
        SimpleNamespace(),
        SimpleNamespace(output_file="results.json"),
        object(),
        run_config={"run_name": "test"},
        run_paths=None,
        supporting_services=SimpleNamespace(
            stable_fingerprint=lambda _value: "templates-fp",
            build_settings_fingerprint=lambda _value: "settings-fp",
        ),
        field_services=SimpleNamespace(),
    )

    assert result is None
    assert persisted["results"] == [refreshed]
    assert persisted["output_file"] == "results.json"
    assert persisted["settings_fingerprint"] == "settings-fp"
    assert persisted["template_library_fingerprint"] == "templates-fp"
    assert persisted["run_config"] == {
        "run_name": "test",
        "heuristic_policy": {
            "dataset_id": "fundamental6",
            "policy_version": "policy-v1",
            "feedback_scope": "field_type",
            "use_curated_heuristics": True,
        },
    }


def test_prepare_bootstrap_resources_refreshes_cross_run_feedback_pending(
    monkeypatch,
) -> None:
    original = FieldTestResult(
        field_id="f1",
        field_type="MATRIX",
        field_name="f1",
        template_name="t1",
        alpha_id="alpha_1",
        status="simulated",
        submittable=None,
        message="checks pending",
        expression="rank(f1)",
        settings_fingerprint="settings",
    )
    refreshed = FieldTestResult(
        field_id="f1",
        field_type="MATRIX",
        field_name="f1",
        template_name="t1",
        alpha_id="alpha_1",
        status="simulated",
        submittable=True,
        message="checks passed",
        expression="rank(f1)",
        settings_fingerprint="settings",
    )
    historical_state = HistoricalRunState(
        existing_results=[],
        feedback_results=[original],
    )
    expression_policy = SimpleNamespace(
        policy_version="policy-v1",
        feedback_scope="field_type",
        use_curated_heuristics=True,
    )
    supporting_resources = BootstrapLoadedResources(
        historical_state=historical_state,
        expression_policy=expression_policy,
        template_library={"MATRIX": []},
        filters={},
    )
    persisted: list[dict[str, object]] = []
    indexed_feedback_paths: list[str] = []

    monkeypatch.setattr(
        bootstrap_module,
        "build_effective_run_paths",
        lambda *_args: SimpleNamespace(),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "load_bootstrap_supporting_resources",
        lambda **_kwargs: supporting_resources,
    )
    monkeypatch.setattr(
        bootstrap_module,
        "refresh_pending_check_results",
        lambda *_args, **_kwargs: ([refreshed], 1),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "persist_reconciled_historical_results",
        lambda **kwargs: persisted.append(kwargs),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "persist_feedback_run_index",
        indexed_feedback_paths.append,
    )
    monkeypatch.setattr(bootstrap_module, "load_bootstrap_fields", lambda **_kwargs: [])

    result = prepare_bootstrap_resources(
        SimpleNamespace(),
        SimpleNamespace(dataset_id="fundamental6", check_submission_retries=1, fetch=None),
        SimpleNamespace(),
        SimpleNamespace(output_file="run.json", feedback_output="feedback.json"),
        object(),
        run_config={"run_name": "test"},
        run_paths=None,
        supporting_services=SimpleNamespace(
            stable_fingerprint=lambda _value: "templates-fp",
            build_settings_fingerprint=lambda _value: "settings-fp",
        ),
        field_services=SimpleNamespace(),
    )

    assert result is None
    assert len(persisted) == 1
    assert persisted[0]["output_file"] == "feedback.json"
    assert persisted[0]["results"] == [refreshed]
    assert indexed_feedback_paths == ["feedback.json"]


def test_initialize_run_context_prefers_run_paths_for_cache_and_credentials(
    monkeypatch, tmp_path
) -> None:
    """Runtime initialization should honor normalized run_paths before raw args paths."""
    args = _build_args()
    run_paths = RunPaths(
        results_dir=str(tmp_path / "results"),
        log_file=str(tmp_path / "run.log"),
        state_file=str(tmp_path / "state.json"),
        checkpoint_file=str(tmp_path / "checkpoint.json"),
        datasets_root=str(tmp_path / "datasets"),
        fields_cache_file=str(tmp_path / "normalized-fields.json"),
        template_library_file=str(tmp_path / "templates.json"),
        output=str(tmp_path / "output.json"),
        feedback_output=str(tmp_path / "feedback.json"),
        creds_file=str(tmp_path / "normalized-creds.json"),
        creds_key_file=str(tmp_path / "normalized-creds.key"),
    )
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        "alpha.app.bootstrap.cleanup_legacy_sidecar_files", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.ensure_analysis_synced", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.build_run_config_snapshot", lambda *_args, **_kwargs: {}
    )
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
    monkeypatch.setattr(
        "alpha.app.bootstrap.stable_fingerprint", lambda *_args, **_kwargs: "tpl-fp"
    )
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
        lambda **_kwargs: ExecutionState.create(),
    )

    run_ctx = initialize_run_context(args, run_paths)

    assert run_ctx is not None
    assert captured["creds_file"] == run_paths.creds_file
    assert captured["creds_key_file"] == run_paths.creds_key_file
    assert captured["fields_cache_file"] == run_paths.fields_cache_file
    assert args.creds_file == "raw-creds.json"
    assert args.creds_key_file == "raw-creds.key"


def test_initialize_run_context_builds_fallback_run_paths_when_missing(
    monkeypatch, tmp_path
) -> None:
    """Initialization should build a minimal RunPaths snapshot when no normalized paths are passed."""
    args = _build_args()
    args.output = str(tmp_path / "raw-output.json")
    args.template_library_file = str(tmp_path / "raw-templates.json")
    args.include_fields_file = str(tmp_path / "include_fields.txt")
    args.exclude_templates_file = str(tmp_path / "exclude_templates.txt")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "alpha.app.bootstrap.cleanup_legacy_sidecar_files", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.ensure_analysis_synced", lambda *_args, **_kwargs: None
    )

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
    monkeypatch.setattr(
        "alpha.app.bootstrap.stable_fingerprint", lambda *_args, **_kwargs: "tpl-fp"
    )
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
        lambda **_kwargs: ExecutionState.create(),
    )

    run_ctx = initialize_run_context(args, None)

    assert run_ctx is not None
    run_config_paths = captured["run_paths"]
    filter_paths = captured["filter_paths"]
    assert isinstance(run_config_paths, RunPaths)
    assert isinstance(filter_paths, RunPaths)
    assert run_config_paths.output == args.output
    assert run_config_paths.template_library_file == args.template_library_file
    assert isinstance(run_config_paths.datasets_root, str)
    assert run_config_paths.datasets_root
    assert filter_paths.include_fields_file == args.include_fields_file
    assert filter_paths.exclude_templates_file == args.exclude_templates_file
