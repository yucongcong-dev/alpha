"""Tests for the development Python version guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_check_python_version_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_python_version.py"
    spec = importlib.util.spec_from_file_location("check_python_version", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_python_version = _load_check_python_version_module()


def test_python_version_guard_accepts_supported_interpreter(monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_python_version.sys, "version_info", (3, 10, 0))

    assert check_python_version.main() == 0
    assert capsys.readouterr().err == ""


def test_python_version_guard_rejects_unsupported_interpreter(monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_python_version.sys, "version_info", (3, 9, 6))
    monkeypatch.setattr(check_python_version.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        check_python_version,
        "platform",
        SimpleNamespace(python_version=lambda: "3.9.6"),
    )

    assert check_python_version.main() == 1
    error = capsys.readouterr().err
    assert "alpha requires Python 3.10+" in error
    assert "py -3.10" in error
