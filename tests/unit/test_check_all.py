"""Cross-platform repository check orchestrator tests."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys


def _load_check_all_module():
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_all.py"
    spec = importlib.util.spec_from_file_location("check_all", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_check_environment_prepends_repo_src(monkeypatch, tmp_path) -> None:
    module = _load_check_all_module()
    monkeypatch.setenv("PYTHONPATH", "existing")

    env = module.build_check_environment(tmp_path)

    assert env["PYTHONPATH"] == f"{tmp_path / 'src'}{os.pathsep}existing"


def test_test_task_uses_current_python_module_entry() -> None:
    module = _load_check_all_module()

    commands = module.build_task_commands("python-command")

    assert commands["test"][0].argv == ("python-command", "-m", "pytest", "-q")


def test_ruff_task_accepts_standalone_executable() -> None:
    module = _load_check_all_module()

    commands = module.build_task_commands("python-command", ruff_executable="ruff-command")

    assert commands["ruff"][0].argv == ("ruff-command", "check", ".")


def test_main_without_tasks_runs_full_suite(monkeypatch) -> None:
    module = _load_check_all_module()
    calls: list[list[str]] = []
    monkeypatch.setattr(module, "run_checks", lambda tasks: calls.append(tasks) or 0)

    assert module.main([]) == 0
    assert calls == [[]]


def test_run_checks_executes_without_shell(monkeypatch, tmp_path) -> None:
    module = _load_check_all_module()
    calls: list[tuple[tuple[str, ...], Path, str]] = []
    monkeypatch.delenv("PYTHONPATH", raising=False)

    def _run(argv, *, cwd, env, check, stdout):
        assert check is True
        assert stdout is None
        calls.append((argv, cwd, env["PYTHONPATH"]))

    monkeypatch.setattr(module.subprocess, "run", _run)

    assert module.run_checks(["test"], root=tmp_path) == 0
    assert calls == [
        (
            (module.sys.executable, "-m", "pytest", "-q"),
            tmp_path,
            str(tmp_path / "src"),
        )
    ]
