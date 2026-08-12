"""Top-level command dispatch tests."""

from __future__ import annotations

from contextlib import nullcontext
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from alpha.config.application import CleanConfig
import alpha.main as main_module


def _disable_logging_setup(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "_configure_application_logging", lambda _config: None)
    monkeypatch.setattr(main_module.run_lock, "exclusive_run_lock", lambda _path: nullcontext())


def _config(*, paths: object, dry_run_plan: bool) -> SimpleNamespace:
    return SimpleNamespace(
        command="run",
        paths=SimpleNamespace(output=paths),
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

    main_module._configure_application_logging(config)

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

    main_module._configure_application_logging(config)

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
            "from alpha.__main__ import _bind_active_config; "
            "_bind_active_config(); "
            "from alpha.config._constants_strings import STATUS_ERROR; "
            "print(STATUS_ERROR)",
            "--config",
            str(config_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.stdout.strip() == "custom_error_status"


def test_importing_main_alone_has_no_argv_side_effect(tmp_path) -> None:
    """Importing alpha.main must not scan sys.argv or bind a custom config."""
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
            "import alpha.main; "
            "from alpha.config._constants_strings import STATUS_ERROR; "
            "print(STATUS_ERROR)",
            "--config",
            str(config_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.stdout.strip() == "error"


def test_main_routes_dry_run_around_runtime_bootstrap_and_finalize(monkeypatch) -> None:
    _disable_logging_setup(monkeypatch)
    paths = object()
    config = _config(paths=paths, dry_run_plan=True)
    monkeypatch.setattr(main_module.parser, "parse_application_config", lambda: config)
    monkeypatch.setattr(main_module.planning, "run_dry_run_plan", lambda args: True)

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("runtime bootstrap/finalize must not run for a dry-run plan")

    monkeypatch.setattr(main_module.bootstrap, "initialize_run_context", _unexpected)
    monkeypatch.setattr(main_module.run_loop, "run_field_test_loop", _unexpected)
    monkeypatch.setattr(main_module.finalize, "finalize_run", _unexpected)
    monkeypatch.setattr(main_module.run_lock, "exclusive_run_lock", _unexpected)

    assert main_module.main() == 0


def test_main_routes_clean_before_run_logging_and_bootstrap(monkeypatch) -> None:
    config = CleanConfig(
        command="clean",
        dataset_id=None,
        all_datasets=False,
        include_credentials=False,
        confirm_clean=False,
        dry_run_clean=True,
    )
    monkeypatch.setattr(main_module.parser, "parse_application_config", lambda: config)
    monkeypatch.setattr(main_module.bootstrap, "clean_runtime_artifacts", lambda _config: 0)

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("clean must not enter the run configuration path")

    monkeypatch.setattr(main_module, "_configure_application_logging", _unexpected)
    monkeypatch.setattr(main_module.bootstrap, "initialize_run_context", _unexpected)
    monkeypatch.setattr(main_module.run_lock, "exclusive_run_lock", _unexpected)

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

    class RecordingLock:
        def __enter__(self):
            calls.append("lock")

        def __exit__(self, *_args: object) -> None:
            calls.append("unlock")

    monkeypatch.setattr(main_module.run_lock, "exclusive_run_lock", lambda _path: RecordingLock())
    monkeypatch.setattr(main_module.parser, "parse_application_config", lambda: config)
    monkeypatch.setattr(
        main_module.bootstrap,
        "initialize_run_context",
        lambda args: calls.append("initialize") or init_result,
    )
    monkeypatch.setattr(
        main_module.run_loop,
        "run_field_test_loop",
        lambda args, run_ctx: calls.append("run"),
    )
    monkeypatch.setattr(
        main_module.finalize,
        "finalize_run",
        lambda args, run_ctx: calls.append("finalize"),
    )

    assert main_module.main() == 0
    assert calls == ["lock", "initialize", "run", "finalize", "close", "unlock"]


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
    monkeypatch.setattr(main_module.parser, "parse_application_config", lambda: config)
    monkeypatch.setattr(
        main_module.bootstrap,
        "initialize_run_context",
        lambda args: calls.append("initialize") or init_result,
    )
    monkeypatch.setattr(main_module.run_loop, "run_field_test_loop", _fail_run)
    monkeypatch.setattr(
        main_module.finalize,
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


def test_run_cli_entry_logs_traceback_by_default(monkeypatch) -> None:
    error_logger = Mock()
    monkeypatch.setattr(main_module, "main", Mock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(main_module, "logger", error_logger)

    assert main_module.run_cli_entry() == 1

    error_logger.error.assert_called_once()
    assert error_logger.error.call_args.args[0] == "[error] %s"
    assert str(error_logger.error.call_args.args[1]) == "boom"
    assert error_logger.error.call_args.kwargs == {"exc_info": True}
