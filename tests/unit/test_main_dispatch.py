"""Top-level command dispatch tests."""

from __future__ import annotations

from types import SimpleNamespace

import alpha.main as main_module


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
