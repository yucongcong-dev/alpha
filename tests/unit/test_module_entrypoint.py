"""Installed console-script and module entrypoint tests."""

from __future__ import annotations

import alpha.__main__ as entrypoint


def test_entrypoint_runs_supported_cli(monkeypatch) -> None:
    monkeypatch.setattr(entrypoint, "_python_version_supported", lambda: True)
    monkeypatch.setattr(entrypoint, "_run_supported_cli", lambda: 7)

    assert entrypoint.main() == 7


def test_entrypoint_reports_unsupported_python(monkeypatch, capsys) -> None:
    monkeypatch.setattr(entrypoint, "_python_version_supported", lambda: False)
    monkeypatch.setattr(
        entrypoint,
        "_run_supported_cli",
        lambda: (_ for _ in ()).throw(AssertionError("application must not import")),
    )

    assert entrypoint.main() == 2
    assert "requires Python 3.10 or newer" in capsys.readouterr().err
