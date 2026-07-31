"""Tests for risk-weighted critical coverage checks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_check_critical_coverage_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_critical_coverage.py"
    spec = importlib.util.spec_from_file_location("check_critical_coverage", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_critical_coverage = _load_check_critical_coverage_module()


def test_main_accepts_windows_coverage_paths(tmp_path: Path, monkeypatch, capsys) -> None:
    files = {
        file_path.replace("/", "\\"): {"summary": {"percent_covered": 100.0}}
        for file_path in check_critical_coverage.CRITICAL_COVERAGE_FLOORS
    }
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"files": files}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["check_critical_coverage.py", str(report_path)])

    assert check_critical_coverage.main() == 0
    assert "validated 21 critical module floors" in capsys.readouterr().out
