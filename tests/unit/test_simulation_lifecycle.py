"""Simulation create, poll, resume, and worker lifecycle tests."""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from alpha.config.constants import STATUS_SKIPPED
from alpha.core.simulation import (
    resume_field_test,
    resume_field_test_in_worker,
    run_field_test,
    run_field_test_in_worker,
)
from alpha.core.simulation_create import run_simulation_create_stage
from alpha.core.simulation_poll import run_simulation_poll_stage
from alpha.exceptions import BrainStopRequested
from alpha.models.domain import FieldTestContext, FieldTestResult, SettingsVariant, TemplateField
from alpha.models.runtime import PendingFutureContext
from alpha.models.runtime_config import SimulationStageConfig
from tests.unit.simulation_config_support import build_simulation_stage_config


def _stage_config() -> SimulationStageConfig:
    return build_simulation_stage_config()


def test_run_simulation_create_stage_merges_settings_with_baseline(monkeypatch) -> None:
    ctx = FieldTestContext(
        field_id="cash_st",
        field_type="MATRIX",
        field_name="cash_st",
        template_name="account_ts_rank_60",
        expression="rank(ts_rank(cash_st, 60))",
        settings_fingerprint="fp1",
        template_library_fingerprint="lib1",
    )
    captured: dict[str, object] = {}

    class DummyClient:
        def create_simulation(self, payload: dict[str, object]) -> str:
            captured["payload"] = payload
            return "/simulations/sim_123"

    monkeypatch.setattr("alpha.core.simulation_create.retry_operation", lambda *a, **k: a[2]())

    result = run_simulation_create_stage(
        ctx,
        DummyClient(),
        _stage_config(),
        simulation_settings=SettingsVariant(decay=2, neutralization="MARKET"),
    )

    assert result == ("/simulations/sim_123", "sim_123")
    payload = captured["payload"]
    assert isinstance(payload, dict)
    settings = payload["settings"]
    assert isinstance(settings, dict)
    assert settings["instrumentType"] == "EQUITY"
    assert settings["region"] == "USA"
    assert settings["unitHandling"] == "VERIFY"
    assert settings["nanHandling"] == "OFF"
    assert settings["maxTrade"] == "OFF"
    assert settings["visualization"] is False
    assert settings["decay"] == 2
    assert settings["neutralization"] == "MARKET"


def test_run_simulation_create_stage_merges_settings_variant_with_baseline(monkeypatch) -> None:
    ctx = FieldTestContext(
        field_id="cash_st",
        field_type="MATRIX",
        field_name="cash_st",
        template_name="account_ts_rank_252",
        expression="rank(ts_rank(cash_st, 252))",
        settings_fingerprint="fp2",
        template_library_fingerprint="lib2",
    )
    captured: dict[str, object] = {}

    class DummyClient:
        def create_simulation(self, payload: dict[str, object]) -> str:
            captured["payload"] = payload
            return "/simulations/sim_456"

    monkeypatch.setattr("alpha.core.simulation_create.retry_operation", lambda *a, **k: a[2]())

    result = run_simulation_create_stage(
        ctx,
        DummyClient(),
        _stage_config(),
        simulation_settings=SettingsVariant(decay=6, truncation=0.05),
    )

    assert result == ("/simulations/sim_456", "sim_456")
    payload = captured["payload"]
    assert isinstance(payload, dict)
    settings = payload["settings"]
    assert isinstance(settings, dict)
    assert settings["instrumentType"] == "EQUITY"
    assert settings["visualization"] is False
    assert settings["decay"] == 6
    assert settings["truncation"] == 0.05


def test_run_simulation_create_stage_skips_when_stop_signal_is_set() -> None:
    ctx = FieldTestContext(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="cashflow_op",
        template_name="group_ratio",
        expression="rank(cashflow_op)",
        settings_fingerprint="fp-stop",
        template_library_fingerprint="lib-stop",
    )
    stop_signal = Event()
    stop_signal.set()

    result = run_simulation_create_stage(
        ctx,
        client=object(),  # type: ignore[arg-type]
        config=_stage_config(),
        should_abort=stop_signal.is_set,
    )

    assert isinstance(result, FieldTestResult)
    assert result.status == STATUS_SKIPPED
    assert result.failed_stage == "stopped"


def test_run_simulation_poll_stage_skips_when_stop_is_requested() -> None:
    ctx = FieldTestContext(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="cashflow_op",
        template_name="group_ratio",
        expression="rank(cashflow_op)",
        settings_fingerprint="fp-stop",
        template_library_fingerprint="lib-stop",
    )

    with (
        patch(
            "alpha.core.simulation_poll.poll_simulation_with_retry",
            side_effect=BrainStopRequested("polling stopped"),
        ),
    ):
        result = run_simulation_poll_stage(
            ctx,
            client=object(),  # type: ignore[arg-type]
            config=_stage_config(),
            simulation_location="/simulations/sim-1",
            simulation_id="sim-1",
            should_abort=lambda: True,
        )

    assert isinstance(result, FieldTestResult)
    assert result.status == STATUS_SKIPPED
    assert result.failed_stage == "stopped"
    assert result.simulation_id == "sim-1"


def test_resume_field_test_skips_create_and_completes_existing_simulation() -> None:
    pending = PendingFutureContext(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="Cashflow",
        template_name="group_ratio",
        expression="rank(cashflow_op)",
        settings_fingerprint="settings-v1",
        simulation_location="/simulations/sim-1",
        simulation_id="sim-1",
    )

    with (
        patch("alpha.core.simulation.run_simulation_create_stage") as mock_create,
        patch(
            "alpha.core.simulation.run_simulation_poll_stage",
            return_value=("alpha-1", {"status": "COMPLETE"}),
        ) as mock_poll,
        patch(
            "alpha.core.simulation.run_check_submission_stage",
            return_value=(True, "checks passed", []),
        ),
    ):
        result = resume_field_test(
            client=object(),  # type: ignore[arg-type]
            config=_stage_config(),
            pending=pending,
            template_library_fingerprint="library-v1",
        )

    mock_create.assert_not_called()
    mock_poll.assert_called_once()
    assert result.simulation_id == "sim-1"
    assert result.alpha_id == "alpha-1"
    assert result.submittable is True


def _orchestration_field() -> TemplateField:
    return TemplateField(
        field_id="cashflow_op",
        field_name="Cashflow",
        field_type="MATRIX",
        metadata={
            "id": "cashflow_op",
            "name": "Cashflow",
            "type": "MATRIX",
            "template_family": "rank",
            "template_stage": "first_order",
        },
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"expression": ""}, "expression cannot be empty"),
        ({"template_name": ""}, "template_name cannot be empty"),
        ({"settings_fingerprint": ""}, "settings_fingerprint cannot be empty"),
        ({"template_library_fingerprint": ""}, "template_library_fingerprint cannot be empty"),
    ],
)
def test_run_field_test_validates_required_inputs(overrides, message) -> None:
    kwargs = {
        "client": object(),
        "config": _stage_config(),
        "field": _orchestration_field(),
        "template_name": "rank",
        "expression": "rank(cashflow_op)",
        "settings_fingerprint": "settings",
        "template_library_fingerprint": "templates",
    }
    kwargs.update(overrides)

    with pytest.raises(ValueError, match=message):
        run_field_test(**kwargs)  # type: ignore[arg-type]


def test_run_field_test_rejects_field_without_id() -> None:
    field = TemplateField("", "Field", "MATRIX", metadata={"name": "Field"})

    with pytest.raises(ValueError, match="field_id cannot be empty"):
        run_field_test(
            object(),  # type: ignore[arg-type]
            _stage_config(),
            field,
            "rank",
            "rank(field)",
            "settings",
            "templates",
        )


def test_run_field_test_calls_create_callback_and_completion() -> None:
    completed = FieldTestResult(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="Cashflow",
        template_name="rank",
        status="simulated",
        submittable=True,
        expression="rank(cashflow_op)",
    )
    callback_calls: list[tuple[str, str]] = []
    with (
        patch(
            "alpha.core.simulation.run_simulation_create_stage",
            return_value=("/simulations/sim-7", "sim-7"),
        ),
        patch(
            "alpha.core.simulation._complete_field_test_from_simulation",
            return_value=completed,
        ) as mock_complete,
    ):
        result = run_field_test(
            object(),  # type: ignore[arg-type]
            _stage_config(),
            _orchestration_field(),
            "rank",
            "rank(cashflow_op)",
            "settings",
            "templates",
            simulation_settings=SettingsVariant(decay=4),
            on_simulation_created=lambda location, simulation_id: callback_calls.append(
                (location, simulation_id)
            ),
        )

    assert result is completed
    assert callback_calls == [("/simulations/sim-7", "sim-7")]
    assert mock_complete.call_args.kwargs["simulation_id"] == "sim-7"


def test_run_field_test_returns_create_stage_failure() -> None:
    failure = FieldTestContext(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="Cashflow",
        template_name="rank",
        expression="rank(cashflow_op)",
    ).failure(failed_stage="create", message="queue busy")
    with patch("alpha.core.simulation.run_simulation_create_stage", return_value=failure):
        result = run_field_test(
            object(),  # type: ignore[arg-type]
            _stage_config(),
            _orchestration_field(),
            "rank",
            "rank(cashflow_op)",
            "settings",
            "templates",
        )

    assert result is failure


def test_resume_field_test_requires_location() -> None:
    with pytest.raises(ValueError, match="must contain simulation_location"):
        resume_field_test(
            object(),  # type: ignore[arg-type]
            _stage_config(),
            PendingFutureContext(),
            "templates",
        )


def test_worker_entrypoints_resolve_thread_client() -> None:
    client = object()
    factory = SimpleNamespace(get_client=lambda: client)
    completed = FieldTestResult(
        field_id="f",
        field_type="MATRIX",
        field_name="f",
        template_name="rank",
        expression="rank(f)",
    )
    pending = PendingFutureContext(simulation_location="/simulations/s1")
    with (
        patch("alpha.core.simulation.run_field_test", return_value=completed) as mock_run,
        patch("alpha.core.simulation.resume_field_test", return_value=completed) as mock_resume,
    ):
        assert (
            run_field_test_in_worker(
                factory,
                _stage_config(),
                _orchestration_field(),
                "rank",
                "rank(cashflow_op)",
                "settings",
                "templates",
            )
            is completed
        )
        assert (
            resume_field_test_in_worker(factory, _stage_config(), pending, "templates") is completed
        )

    assert mock_run.call_args.args[0] is client
    assert mock_resume.call_args.args[0] is client
