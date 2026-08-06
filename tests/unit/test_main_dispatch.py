"""Top-level command dispatch tests."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import alpha.main as main_module


def _disable_logging_setup(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "configure_application_logging", lambda _config: None)


def _config(*, paths: object, dry_run_plan: bool) -> SimpleNamespace:
    return SimpleNamespace(
        command="run",
        paths=paths,
        planning=SimpleNamespace(dry_run_plan=dry_run_plan),
        runtime_flags=SimpleNamespace(verbose=False, quiet=False),
    )


def test_configure_application_logging_uses_console_only_for_dry_run(monkeypatch, tmp_path) -> None:
    setup = Mock()
    monkeypatch.setattr("alpha.cli.filters.setup_runtime_logging", setup)
    config = SimpleNamespace(
        command="run",
        planning=SimpleNamespace(dry_run_plan=True),
        paths=SimpleNamespace(log_file=str(tmp_path / "run.log")),
        runtime_flags=SimpleNamespace(verbose=True, quiet=False),
    )

    main_module.configure_application_logging(config)

    setup.assert_called_once_with("", verbose=True, quiet=False)


def test_configure_application_logging_uses_file_for_live_run(monkeypatch, tmp_path) -> None:
    setup = Mock()
    monkeypatch.setattr("alpha.cli.filters.setup_runtime_logging", setup)
    log_file = str(tmp_path / "run.log")
    config = SimpleNamespace(
        command="run",
        planning=SimpleNamespace(dry_run_plan=False),
        paths=SimpleNamespace(log_file=log_file),
        runtime_flags=SimpleNamespace(verbose=False, quiet=True),
    )

    main_module.configure_application_logging(config)

    setup.assert_called_once_with(log_file, verbose=False, quiet=True)


def test_main_activates_custom_config_before_yaml_backed_constants(tmp_path) -> None:
    config_path = tmp_path / "custom-settings.yaml"
    config_path.write_text(
        "global:\n  strings:\n    status:\n      error: custom_error_status\n",
        encoding="utf-8",
    )
    project_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(project_root / "src"), env.get("PYTHONPATH", "")])
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import alpha.main; from alpha.config.constants import STATUS_ERROR; print(STATUS_ERROR)",
            "--config",
            str(config_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.stdout.strip() == "custom_error_status"


def test_main_routes_dry_run_around_runtime_bootstrap_and_finalize(monkeypatch) -> None:
    _disable_logging_setup(monkeypatch)
    paths = object()
    config = _config(paths=paths, dry_run_plan=True)
    monkeypatch.setattr(main_module, "parse_application_config", lambda: config)
    monkeypatch.setattr(main_module, "run_dry_run_plan", lambda args: True)

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("runtime bootstrap/finalize must not run for a dry-run plan")

    monkeypatch.setattr(main_module, "initialize_run_context", _unexpected)
    monkeypatch.setattr(main_module, "run_field_test_loop", _unexpected)
    monkeypatch.setattr(main_module, "finalize_run", _unexpected)

    assert main_module.main() == 0


def test_main_runs_runtime_pipeline_and_closes_client_factory(monkeypatch) -> None:
    _disable_logging_setup(monkeypatch)
    paths = object()
    config = _config(paths=paths, dry_run_plan=False)
    client_factory = SimpleNamespace()
    init_result = SimpleNamespace(client_factory=client_factory)
    calls: list[str] = []

    def _close() -> None:
        calls.append("close")

    client_factory.close = _close
    monkeypatch.setattr(main_module, "parse_application_config", lambda: config)
    monkeypatch.setattr(
        main_module,
        "initialize_run_context",
        lambda args: calls.append("initialize") or init_result,
    )
    monkeypatch.setattr(
        main_module,
        "run_field_test_loop",
        lambda args, run_ctx: calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "finalize_run",
        lambda args, run_ctx: calls.append("finalize"),
    )

    assert main_module.main() == 0
    assert calls == ["initialize", "run", "finalize", "close"]


def test_main_closes_client_factory_when_runtime_pipeline_fails(monkeypatch) -> None:
    _disable_logging_setup(monkeypatch)
    paths = object()
    config = _config(paths=paths, dry_run_plan=False)
    client_factory = SimpleNamespace()
    init_result = SimpleNamespace(client_factory=client_factory)
    calls: list[str] = []

    def _close() -> None:
        calls.append("close")

    def _fail_run(*_args) -> None:
        calls.append("run")
        raise RuntimeError("boom")

    client_factory.close = _close
    monkeypatch.setattr(main_module, "parse_application_config", lambda: config)
    monkeypatch.setattr(
        main_module,
        "initialize_run_context",
        lambda args: calls.append("initialize") or init_result,
    )
    monkeypatch.setattr(main_module, "run_field_test_loop", _fail_run)
    monkeypatch.setattr(
        main_module,
        "finalize_run",
        lambda *_args: calls.append("finalize"),
    )

    try:
        main_module.main()
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("runtime failure should propagate from main()")
    assert calls == ["initialize", "run", "close"]


def test_run_cli_entry_includes_traceback_in_verbose_logging(monkeypatch) -> None:
    error_logger = Mock()
    root_logger = main_module.logging.getLogger()
    monkeypatch.setattr(main_module, "main", Mock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(main_module, "logger", error_logger)
    monkeypatch.setattr(root_logger, "isEnabledFor", lambda _level: True)

    assert main_module.run_cli_entry() == 1

    error_logger.error.assert_called_once()
    assert error_logger.error.call_args.args[0] == "[error] %s"
    assert str(error_logger.error.call_args.args[1]) == "boom"
    assert error_logger.error.call_args.kwargs == {"exc_info": True}
