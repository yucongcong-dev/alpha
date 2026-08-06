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
from alpha.config.application import ApplicationConfig
from alpha.models import ExecutionState, HistoricalRunState
from alpha.models.domain import FieldTestResult, TemplateField
from alpha.models.io_types import RunFilters, RunPaths
from alpha.models.runtime_options import FieldSelectionOptions


def _build_config(**overrides: object) -> ApplicationConfig:
    values: dict[str, object] = {
        "output": "",
        "feedback_output": "",
        "log_file": "",
        "template_library_file": "",
        "fields_cache_file": "raw-cache.json",
        "creds_file": "raw-creds.json",
        "creds_key_file": "raw-creds.key",
        "email": None,
        "password": None,
        "dataset_id": "fundamental6",
        "region": "USA",
        "universe": "TOP3000",
        "instrument_type": "EQUITY",
        "delay": 1,
        "decay": 4,
        "neutralization": "SUBINDUSTRY",
        "truncation": 0.08,
        "pasteurization": "ON",
        "unit_handling": "VERIFY",
        "nan_handling": "OFF",
        "max_trade": "OFF",
        "language": "FASTEXPR",
        "start_date": None,
        "end_date": None,
        "page_size": 50,
        "max_concurrent_simulations": 1,
        "max_concurrent_creates": 1,
        "simulation_max_pending_cycles": 10,
        "offset": 0,
        "limit": 10,
        "top_fields_by_feedback": 0,
        "max_templates_per_field": 0,
        "max_templates_per_family": 0,
        "legacy_similarity_penalty": 0,
        "include_fields_file": "",
        "exclude_fields_file": "",
        "include_templates_file": "",
        "exclude_templates_file": "",
    }
    values.update(overrides)
    args = argparse.Namespace(**values)
    paths = RunPaths(
        results_dir="runs",
        log_file=str(values["log_file"]),
        state_file="state.json",
        checkpoint_file="interrupt.json",
        datasets_root=str(values.get("datasets_root", "")),
        output=str(values["output"]),
        feedback_output=str(values["feedback_output"]),
        template_library_file=str(values["template_library_file"]),
        fields_cache_file=str(values["fields_cache_file"]),
        creds_file=str(values["creds_file"]),
        creds_key_file=str(values["creds_key_file"]),
        include_fields_file=str(values["include_fields_file"]),
        exclude_fields_file=str(values["exclude_fields_file"]),
        include_templates_file=str(values["include_templates_file"]),
        exclude_templates_file=str(values["exclude_templates_file"]),
    )
    return ApplicationConfig.from_args(args, paths)


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


def test_initialize_run_context_closes_clients_when_resources_are_unavailable(
    monkeypatch,
) -> None:
    args = _build_config()
    closed: list[str] = []
    bootstrap_client = SimpleNamespace(close=lambda: closed.append("bootstrap"))
    client_factory = SimpleNamespace(close=lambda: closed.append("factory"))

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

    assert initialize_run_context(args) is None
    assert closed == ["bootstrap", "factory"]


def test_initialize_run_context_closes_factory_when_state_build_fails(monkeypatch) -> None:
    args = _build_config()
    closed: list[str] = []
    bootstrap_client = SimpleNamespace(close=lambda: closed.append("bootstrap"))
    client_factory = SimpleNamespace(close=lambda: closed.append("factory"))
    prepared = SimpleNamespace(
        historical_state=HistoricalRunState(),
        settings_fingerprint="settings-fp",
        template_library_fingerprint="templates-fp",
        run_config={},
    )

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
        initialize_run_context(args)

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
    reconciliation: dict[str, object] = {}

    monkeypatch.setattr(
        bootstrap_module,
        "load_bootstrap_supporting_resources",
        lambda **_kwargs: supporting_resources,
    )
    monkeypatch.setattr(
        bootstrap_module,
        "reconcile_pending_check_results",
        lambda *_args, **kwargs: (
            reconciliation.update(kwargs) or HistoricalRunState(existing_results=[refreshed])
        ),
    )
    monkeypatch.setattr(bootstrap_module, "load_bootstrap_fields", lambda **_kwargs: [])
    monkeypatch.setattr(bootstrap_module, "stable_fingerprint", lambda _value: "templates-fp")
    monkeypatch.setattr(
        bootstrap_module, "build_settings_fingerprint", lambda _value: "settings-fp"
    )

    result = prepare_bootstrap_resources(
        SimpleNamespace(dataset_id="fundamental6", check_submission_retries=1, fetch=None),
        SimpleNamespace(backfill_window=504),
        SimpleNamespace(output="results.json", feedback_output=""),
        object(),
        run_config={"run_name": "test"},
    )

    assert result is None
    assert reconciliation["output_file"] == "results.json"
    assert reconciliation["settings_fingerprint"] == "settings-fp"
    assert reconciliation["template_library_fingerprint"] == "templates-fp"
    assert reconciliation["run_config"] == {
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
    reconciliation: dict[str, object] = {}

    monkeypatch.setattr(
        bootstrap_module,
        "load_bootstrap_supporting_resources",
        lambda **_kwargs: supporting_resources,
    )
    monkeypatch.setattr(
        bootstrap_module,
        "reconcile_pending_check_results",
        lambda *_args, **kwargs: (
            reconciliation.update(kwargs) or HistoricalRunState(feedback_results=[refreshed])
        ),
    )
    monkeypatch.setattr(bootstrap_module, "load_bootstrap_fields", lambda **_kwargs: [])
    monkeypatch.setattr(bootstrap_module, "stable_fingerprint", lambda _value: "templates-fp")
    monkeypatch.setattr(
        bootstrap_module, "build_settings_fingerprint", lambda _value: "settings-fp"
    )

    result = prepare_bootstrap_resources(
        SimpleNamespace(dataset_id="fundamental6", check_submission_retries=1, fetch=None),
        SimpleNamespace(backfill_window=504),
        SimpleNamespace(output="run.json", feedback_output="feedback.json"),
        object(),
        run_config={"run_name": "test"},
    )

    assert result is None
    assert reconciliation["output_file"] == "run.json"
    assert reconciliation["feedback_output"] == "feedback.json"


def test_initialize_run_context_uses_application_paths_for_cache_and_credentials(
    monkeypatch, tmp_path
) -> None:
    """Runtime initialization should use the normalized paths in ApplicationConfig."""
    args = _build_config(
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
        "alpha.app.bootstrap_runtime_outputs.cleanup_legacy_sidecar_files",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_runtime_outputs.ensure_analysis_synced",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_runtime_outputs.build_run_config_snapshot",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.ensure_dataset_template_library",
        lambda template_library_file, _dataset_id: template_library_file,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.ensure_template_blacklist_file",
        lambda *_args, **_kwargs: None,
    )

    def _capture_credentials(passed_args):
        captured["creds_file"] = passed_args.creds_file
        captured["creds_key_file"] = passed_args.creds_key_file
        return "user@example.com", "secret"

    monkeypatch.setattr("alpha.app.bootstrap_clients.load_credentials", _capture_credentials)
    monkeypatch.setattr(
        "alpha.app.bootstrap.create_and_login_client",
        lambda *_args, **_kwargs: ("bootstrap-client", "worker-factory"),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.load_template_library",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.load_run_filters_extended",
        lambda *_args, **_kwargs: RunFilters(),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.get_dataset_expression_policy",
        lambda *_args, **_kwargs: type("Policy", (), {"use_curated_heuristics": False})(),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.stable_fingerprint", lambda *_args, **_kwargs: "tpl-fp"
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.build_settings_fingerprint", lambda *_args, **_kwargs: "settings-fp"
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.build_historical_run_state",
        lambda *_args, **_kwargs: HistoricalRunState(),
    )

    def _capture_cache_path(cache_path, **_kwargs):
        captured["fields_cache_file"] = cache_path
        return []

    monkeypatch.setattr(
        "alpha.app.bootstrap_field_resources.load_fields_cache", _capture_cache_path
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_field_resources.fetch_fields_with_cache",
        lambda *_args, **_kwargs: [TemplateField("field_1", "field_1", "MATRIX")],
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

    run_ctx = initialize_run_context(args)

    assert run_ctx is not None
    assert captured["creds_file"] == args.paths.creds_file
    assert captured["creds_key_file"] == args.paths.creds_key_file
    assert captured["fields_cache_file"] == args.paths.fields_cache_file


def test_initialize_run_context_shares_application_paths_with_resource_loaders(
    monkeypatch, tmp_path
) -> None:
    """Run config and local filters should receive the same authoritative path snapshot."""
    args = _build_config(
        datasets_root=str(tmp_path / "datasets"),
        output=str(tmp_path / "raw-output.json"),
        template_library_file=str(tmp_path / "raw-templates.json"),
        include_fields_file=str(tmp_path / "include_fields.txt"),
        exclude_templates_file=str(tmp_path / "exclude_templates.txt"),
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "alpha.app.bootstrap_runtime_outputs.cleanup_legacy_sidecar_files",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_runtime_outputs.ensure_analysis_synced",
        lambda *_args, **_kwargs: None,
    )

    def _capture_run_config(_args, run_paths):
        captured["run_paths"] = run_paths
        return {"paths": {"output": run_paths.output}}

    monkeypatch.setattr(
        "alpha.app.bootstrap_runtime_outputs.build_run_config_snapshot", _capture_run_config
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.ensure_dataset_template_library",
        lambda template_library_file, _dataset_id: template_library_file,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.ensure_template_blacklist_file",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_clients.load_credentials",
        lambda *_args, **_kwargs: ("user@example.com", "secret"),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.create_and_login_client",
        lambda *_args, **_kwargs: ("bootstrap-client", "worker-factory"),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.load_template_library",
        lambda *_args, **_kwargs: {},
    )

    def _capture_filters(run_paths):
        captured["filter_paths"] = run_paths
        return RunFilters()

    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.load_run_filters_extended", _capture_filters
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.get_dataset_expression_policy",
        lambda *_args, **_kwargs: type("Policy", (), {"use_curated_heuristics": False})(),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.stable_fingerprint", lambda *_args, **_kwargs: "tpl-fp"
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap.build_settings_fingerprint", lambda *_args, **_kwargs: "settings-fp"
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_supporting_resources.build_historical_run_state",
        lambda *_args, **_kwargs: HistoricalRunState(),
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_field_resources.load_fields_cache", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        "alpha.app.bootstrap_field_resources.fetch_fields_with_cache",
        lambda *_args, **_kwargs: [TemplateField("field_1", "field_1", "MATRIX")],
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

    run_ctx = initialize_run_context(args)

    assert run_ctx is not None
    run_config_paths = captured["run_paths"]
    filter_paths = captured["filter_paths"]
    assert isinstance(run_config_paths, RunPaths)
    assert isinstance(filter_paths, RunPaths)
    assert run_config_paths is args.paths
    assert filter_paths is args.paths
