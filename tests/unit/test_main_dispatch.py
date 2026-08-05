"""Top-level command dispatch tests."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import alpha.main as main_module


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
    paths = object()
    config = SimpleNamespace(command="run", dry_run_plan=True, paths=paths)
    monkeypatch.setattr(main_module, "parse_application_config", lambda: config)
    monkeypatch.setattr(main_module, "run_dry_run_plan", lambda args, run_paths: True)

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("runtime bootstrap/finalize must not run for a dry-run plan")

    monkeypatch.setattr(main_module, "initialize_run_context", _unexpected)
    monkeypatch.setattr(main_module, "run_field_test_loop", _unexpected)
    monkeypatch.setattr(main_module, "finalize_run", _unexpected)

    assert main_module.main() == 0


def test_main_routes_blacklist_command_without_runtime_bootstrap(monkeypatch) -> None:
    datasets_root = "datasets"
    config = SimpleNamespace(
        command="blacklist-review",
        dataset_id="fundamental6",
        paths=SimpleNamespace(datasets_root=datasets_root),
    )
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(main_module, "parse_application_config", lambda: config)
    monkeypatch.setattr(
        main_module,
        "run_blacklist_command",
        lambda command, *, dataset_id, datasets_root: calls.append(
            (command, dataset_id, datasets_root)
        )
        or 0,
    )

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("blacklist commands must not start runtime bootstrap")

    monkeypatch.setattr(main_module, "initialize_run_context", _unexpected)

    assert main_module.main() == 0
    assert calls == [("blacklist-review", "fundamental6", datasets_root)]


def test_main_runs_runtime_pipeline_and_closes_client_factory(monkeypatch) -> None:
    paths = object()
    config = SimpleNamespace(command="run", dry_run_plan=False, paths=paths)
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
        lambda args, run_paths: calls.append("initialize") or init_result,
    )
    monkeypatch.setattr(
        main_module,
        "run_field_test_loop",
        lambda args, run_ctx, run_paths: calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "finalize_run",
        lambda args, run_ctx, run_paths: calls.append("finalize"),
    )

    assert main_module.main() == 0
    assert calls == ["initialize", "run", "finalize", "close"]


def test_main_closes_client_factory_when_runtime_pipeline_fails(monkeypatch) -> None:
    paths = object()
    config = SimpleNamespace(command="run", dry_run_plan=False, paths=paths)
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
        lambda args, run_paths: calls.append("initialize") or init_result,
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
