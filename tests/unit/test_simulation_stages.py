"""Simulation stage boundary and failure-path tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from alpha.core import simulation_create as create_stages
from alpha.core import simulation_poll as poll_stages
from alpha.core import submission_checks as check_stages
from alpha.exceptions import BrainStopRequested
from alpha.models.domain import FailedCheck, FieldTestContext, FieldTestResult, SettingsVariant
from tests.conftest import MockArgs


def _context() -> FieldTestContext:
    return FieldTestContext(
        field_id="f1",
        field_type="MATRIX",
        field_name="Field 1",
        template_name="template",
        expression="rank(f1)",
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
    )


def _stage_config() -> SimpleNamespace:
    return SimpleNamespace(
        simulation_create_retries=2,
        simulation_poll_retries=3,
        simulation_max_polls=10,
        simulation_max_wait_seconds=60,
        simulation_max_pending_cycles=5,
        simulation_max_queue_seconds=30,
    )


def test_int_arg_and_settings_override_boundaries() -> None:
    assert check_stages._int_arg(SimpleNamespace(value=0), "value", default=3) == 0
    assert check_stages._int_arg(SimpleNamespace(value="invalid"), "value", default=2) == 2
    assert create_stages._serialize_settings_overrides(None) == {}
    assert create_stages._serialize_settings_overrides({"unitHandling": "OFF"}) == {
        "unitHandling": "OFF"
    }
    assert create_stages._serialize_settings_overrides(SettingsVariant(decay=6)) == {"decay": 6}


def test_create_and_poll_retry_wrappers_forward_parameters(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    def _retry(name, retries, operation, **_kwargs):
        calls.append((name, retries))
        return operation()

    class Client:
        def create_simulation(self, _payload):
            return "/simulations/sim-1"

        def poll_simulation(self, location, **kwargs):
            assert location == "/simulations/sim-1"
            assert kwargs["max_polls"] == 10
            assert kwargs["max_wait_seconds"] == 60
            assert kwargs["max_pending_cycles"] == 5
            assert kwargs["max_queue_seconds"] == 30
            return {"alpha": "alpha-1"}

    monkeypatch.setattr(create_stages, "retry_operation", _retry)
    monkeypatch.setattr(poll_stages, "retry_operation", _retry)
    client = Client()

    assert create_stages.create_simulation_with_retry(client, {}, 2) == (
        "/simulations/sim-1",
        "sim-1",
    )
    assert poll_stages.poll_simulation_with_retry(
        client,
        "/simulations/sim-1",
        3,
        max_polls=10,
        max_wait_seconds=60,
        max_pending_cycles=5,
        max_queue_seconds=30,
    ) == {"alpha": "alpha-1"}
    assert calls == [("create simulation", 2), ("poll simulation", 3)]


def test_create_stage_releases_semaphore_when_stop_arrives_after_acquire() -> None:
    abort = False

    class Semaphore:
        released = False

        def acquire(self) -> bool:
            nonlocal abort
            abort = True
            return True

        def release(self) -> None:
            self.released = True

    semaphore = Semaphore()
    with (
        patch(
            "alpha.core.simulation_create.SimulationStageConfig.from_stage_args",
            return_value=_stage_config(),
        ),
        patch(
            "alpha.core.simulation_create.build_simulation_payload",
            return_value={"settings": {}, "regular": "rank(f1)"},
        ),
        patch("alpha.core.simulation_create.create_simulation_with_retry") as create,
    ):
        result = create_stages.run_simulation_create_stage(
            _context(),
            client=object(),  # type: ignore[arg-type]
            args=MockArgs(),
            create_semaphore=semaphore,
            should_abort=lambda: abort,
        )

    assert isinstance(result, FieldTestResult)
    assert result.failed_stage == "stopped"
    assert semaphore.released is True
    create.assert_not_called()


def test_create_stage_converts_unexpected_error_to_failure() -> None:
    with (
        patch(
            "alpha.core.simulation_create.SimulationStageConfig.from_stage_args",
            return_value=_stage_config(),
        ),
        patch(
            "alpha.core.simulation_create.build_simulation_payload",
            return_value={"settings": {}, "regular": "rank(f1)"},
        ),
        patch(
            "alpha.core.simulation_create.create_simulation_with_retry",
            side_effect=RuntimeError("create failed"),
        ),
    ):
        result = create_stages.run_simulation_create_stage(
            _context(),
            client=object(),  # type: ignore[arg-type]
            args=MockArgs(),
        )

    assert isinstance(result, FieldTestResult)
    assert result.failed_stage == "simulation"
    assert "create failed" in result.message


def test_poll_stage_returns_alpha_and_reports_missing_alpha() -> None:
    with (
        patch(
            "alpha.core.simulation_poll.SimulationStageConfig.from_stage_args",
            return_value=_stage_config(),
        ),
        patch(
            "alpha.core.simulation_poll.poll_simulation_with_retry",
            side_effect=[
                {"progress": "100%", "alpha": "alpha-1"},
                {"status": "ERROR", "message": "invalid expression"},
            ],
        ),
    ):
        success = poll_stages.run_simulation_poll_stage(
            _context(),
            client=object(),  # type: ignore[arg-type]
            args=MockArgs(),
            simulation_location="/simulations/sim-1",
            simulation_id="sim-1",
        )
        failure = poll_stages.run_simulation_poll_stage(
            _context(),
            client=object(),  # type: ignore[arg-type]
            args=MockArgs(),
            simulation_location="/simulations/sim-2",
            simulation_id="sim-2",
        )

    assert success == ("alpha-1", {"progress": "100%", "alpha": "alpha-1"})
    assert isinstance(failure, FieldTestResult)
    assert failure.status == "simulation_failed"
    assert failure.simulation_id == "sim-2"


def test_poll_stage_converts_stop_and_unexpected_errors() -> None:
    with (
        patch(
            "alpha.core.simulation_poll.SimulationStageConfig.from_stage_args",
            return_value=_stage_config(),
        ),
        patch(
            "alpha.core.simulation_poll.poll_simulation_with_retry",
            side_effect=RuntimeError("poll failed"),
        ),
    ):
        failure = poll_stages.run_simulation_poll_stage(
            _context(),
            client=object(),  # type: ignore[arg-type]
            args=MockArgs(),
            simulation_location="/simulations/sim-1",
            simulation_id="sim-1",
        )

    assert isinstance(failure, FieldTestResult)
    assert failure.failed_stage == "simulation"
    assert "poll failed" in failure.message

    with (
        patch(
            "alpha.core.simulation_poll.SimulationStageConfig.from_stage_args",
            return_value=_stage_config(),
        ),
        patch(
            "alpha.core.simulation_poll.poll_simulation_with_retry",
            side_effect=BrainStopRequested("stopped"),
        ),
    ):
        stopped = poll_stages.run_simulation_poll_stage(
            _context(),
            client=object(),  # type: ignore[arg-type]
            args=MockArgs(),
            simulation_location="/simulations/sim-1",
            simulation_id="sim-1",
        )
    assert isinstance(stopped, FieldTestResult)
    assert stopped.failed_stage == "stopped"


def test_check_submission_stage_precheck_failure_still_calls_remote_check() -> None:
    client = object()
    failed_check = {
        "name": "LOW_SHARPE",
        "value": 0.5,
        "limit": 1.25,
        "result": "FAIL",
    }
    with (
        patch(
            "alpha.core.submission_checks.PrecheckConfig.from_args",
            return_value=SimpleNamespace(
                min_sharpe=1.25,
                min_fitness=1.0,
                min_turnover=0.01,
                max_turnover=0.7,
                max_weight=0.1,
            ),
        ),
        patch(
            "alpha.core.submission_checks.precheck_simulation_metrics",
            return_value=(False, "low sharpe", [failed_check]),
        ),
        patch(
            "alpha.core.submission_checks.check_submission_with_retry",
            return_value=(
                False,
                "checks failed",
                [FailedCheck(name="LOW_SHARPE", result="FAIL")],
            ),
        ) as check_submission,
    ):
        rejected = check_stages.run_check_submission_stage(
            _context(),
            client=client,  # type: ignore[arg-type]
            args=SimpleNamespace(check_submission_retries=3),  # type: ignore[arg-type]
            alpha_id="alpha-1",
            simulation_id="sim-1",
            simulation_result={"alpha": "alpha-1"},
        )

    assert rejected == (
        False,
        "checks failed",
        [FailedCheck(name="LOW_SHARPE", result="FAIL")],
    )
    check_submission.assert_called_once_with(client, "alpha-1", 3)


def test_check_submission_stage_success_and_error() -> None:
    client = object()
    with patch(
        "alpha.core.submission_checks.check_submission_with_retry",
        return_value=(True, "checks passed", []),
    ) as check_submission:
        passed = check_stages.run_check_submission_stage(
            _context(),
            client=client,  # type: ignore[arg-type]
            args=SimpleNamespace(check_submission_retries=2),  # type: ignore[arg-type]
            alpha_id="alpha-1",
            simulation_id="sim-1",
        )
    assert passed == (True, "checks passed", [])
    check_submission.assert_called_once_with(client, "alpha-1", 2)

    with patch(
        "alpha.core.submission_checks.check_submission_with_retry",
        side_effect=RuntimeError("checks failed remotely"),
    ):
        error = check_stages.run_check_submission_stage(
            _context(),
            client=object(),  # type: ignore[arg-type]
            args=SimpleNamespace(check_submission_retries="invalid"),  # type: ignore[arg-type]
            alpha_id="alpha-1",
            simulation_id="sim-1",
        )
    assert isinstance(error, FieldTestResult)
    assert error.failed_stage == "check_submission"
    assert error.alpha_id == "alpha-1"
