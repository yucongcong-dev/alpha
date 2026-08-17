"""Dedicated check-submissions command tests."""

from __future__ import annotations

from types import SimpleNamespace

from alpha.app.submission_check_refresh import refresh_submission_checks
from alpha.models.domain import FailedCheck, FieldTestResult
from alpha.runtime.contexts import HistoricalRunState


def _pending_result() -> FieldTestResult:
    return FieldTestResult(
        field_id="field_1",
        field_type="MATRIX",
        field_name="field_1",
        template_name="template_1",
        alpha_id="alpha_1",
        status="simulated",
        submittable=None,
        message="checks pending",
        failed_checks=[FailedCheck(name="SELF_CORRELATION", result="PENDING")],
    )


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        paths=SimpleNamespace(
            output="run.json",
            feedback_output="feedback.json",
            creds_file="credentials.json",
            creds_key_file="credentials.key",
        ),
        dataset=SimpleNamespace(dataset_id="fundamental6"),
        credentials=SimpleNamespace(email=None, password=None),
        pending_check_refresh=SimpleNamespace(
            refresh_limit=0,
            max_refresh_seconds=900.0,
            max_workers=1,
        ),
        execution=SimpleNamespace(
            check_submission_retries=3,
            min_request_interval=0.0,
            rate_limit_max_retries=3,
            login_retries=3,
        ),
        runtime_values=SimpleNamespace(http=None),
    )


def test_refresh_submission_checks_uses_only_existing_results_and_closes_clients(
    monkeypatch,
) -> None:
    config = _config()
    pending_state = HistoricalRunState(feedback_results=[_pending_result()])
    resolved_state = HistoricalRunState(feedback_results=[])
    bootstrap_client = SimpleNamespace()
    client_factory = SimpleNamespace()
    closed: list[str] = []
    bootstrap_client.close = lambda: closed.append("bootstrap")
    client_factory.close = lambda: closed.append("factory")
    reconciled: dict[str, object] = {}

    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.load_result_summary_metadata",
        lambda _path: {
            "dataset_id": "fundamental6",
            "settings_fingerprint": "settings",
            "template_library_fingerprint": "templates",
            "run_fingerprint": "run",
            "run_config": {"run": {"name": "batch"}},
        },
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.build_historical_run_state",
        lambda *_args, **_kwargs: pending_state,
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.resolve_credentials",
        lambda _options: ("email", "password"),
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.create_and_login_client",
        lambda *_args: (bootstrap_client, client_factory),
    )

    def _reconcile(client, _state, **kwargs):
        reconciled["client"] = client
        reconciled.update(kwargs)
        return resolved_state

    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.reconcile_pending_check_results",
        _reconcile,
    )

    assert refresh_submission_checks(config) is True
    assert reconciled["client"] is bootstrap_client
    assert reconciled["refresh_limit"] == 0
    assert reconciled["max_refresh_seconds"] == 900.0
    assert reconciled["max_workers"] == 1
    assert reconciled["repeat_until_terminal"] is True
    assert closed == ["bootstrap", "factory"]


def test_refresh_submission_checks_reconciles_pending_run_missing_from_feedback(
    monkeypatch,
) -> None:
    config = _config()
    pending_state = HistoricalRunState(existing_results=[_pending_result()])
    bootstrap_client = SimpleNamespace()
    client_factory = SimpleNamespace()
    reconciled: list[object] = []

    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.load_result_summary_metadata",
        lambda _path: {"dataset_id": "fundamental6"},
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.build_historical_run_state",
        lambda *_args, **_kwargs: pending_state,
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.resolve_credentials",
        lambda _options: ("email", "password"),
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.create_and_login_client",
        lambda *_args: (bootstrap_client, client_factory),
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.reconcile_pending_check_results",
        lambda *_args, **_kwargs: reconciled.append(True) or pending_state,
    )

    assert refresh_submission_checks(config) is True
    assert reconciled == [True]


def test_refresh_submission_checks_does_not_reuse_feedback_aggregate_identity(
    monkeypatch,
) -> None:
    config = _config()
    pending_state = HistoricalRunState(feedback_results=[_pending_result()])
    bootstrap_client = SimpleNamespace(close=lambda: None)
    client_factory = SimpleNamespace(close=lambda: None)
    reconciled: dict[str, object] = {}

    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.load_result_summary_metadata",
        lambda path: (
            {}
            if path == "run.json"
            else {
                "dataset_id": "fundamental6",
                "metadata_scope": "feedback",
                "settings_fingerprint": "old-settings",
                "template_library_fingerprint": "old-templates",
                "run_fingerprint": "old-run",
                "run_config": {"run": {"name": "old"}},
            }
        ),
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.build_historical_run_state",
        lambda *_args, **_kwargs: pending_state,
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.resolve_credentials",
        lambda _options: ("email", "password"),
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.create_and_login_client",
        lambda *_args: (bootstrap_client, client_factory),
    )
    monkeypatch.setattr(
        "alpha.app.submission_check_refresh.reconcile_pending_check_results",
        lambda *_args, **kwargs: reconciled.update(kwargs) or pending_state,
    )

    assert refresh_submission_checks(config) is True
    assert reconciled["settings_fingerprint"] == ""
    assert reconciled["template_library_fingerprint"] == ""
    assert reconciled["run_fingerprint"] == ""
    assert reconciled["run_config"] == {}
