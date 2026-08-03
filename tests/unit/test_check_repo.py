"""Tests for cross-platform repository policy checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_check_repo_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_repo.py"
    spec = importlib.util.spec_from_file_location("check_repo", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_repo = _load_check_repo_module()


def test_repo_boundary_rejects_root_tmp_files(tmp_path: Path) -> None:
    (tmp_path / "tmp_notes.txt").write_text("scratch\n", encoding="utf-8")

    errors = check_repo.repo_boundary_check(tmp_path)

    assert any("root tmp_* files" in error for error in errors)
    assert any("tmp_notes.txt" in error for error in errors)


def test_removed_compat_file_check_rejects_root_app_facade(tmp_path: Path) -> None:
    alpha_dir = tmp_path / "src" / "alpha"
    app_dir = alpha_dir / "app"
    app_dir.mkdir(parents=True)
    (alpha_dir / "run_loop.py").write_text("", encoding="utf-8")

    errors = check_repo.removed_compat_file_check(tmp_path)

    assert any("compatibility aggregate files" in error for error in errors)
    assert any("src/alpha/run_loop.py" in error for error in errors)


def test_compat_import_check_rejects_package_facade_import(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_legacy.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        "from alpha." + "run_loop import run_field_test_loop\n",
        encoding="utf-8",
    )

    errors = check_repo.compat_import_check(tmp_path)

    assert any("canonical modules" in error for error in errors)
    assert any("tests/test_legacy.py:1" in error for error in errors)


def test_arch_boundary_check_rejects_lower_level_app_import(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "alpha" / "core" / "worker.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("from alpha.app.run_loop import run_field_test_loop\n", encoding="utf-8")

    errors = check_repo.arch_boundary_check(tmp_path)

    assert any("lower-level modules" in error for error in errors)
    assert any("src/alpha/core/worker.py:1" in error for error in errors)


def test_scan_secrets_skips_ignored_runtime_dirs(tmp_path: Path) -> None:
    feedback_file = tmp_path / "datasets" / "fundamental6" / "runs" / "default" / "run.log"
    feedback_file.parent.mkdir(parents=True)
    feedback_file.write_text(
        "Authorization: " + "Basic local-run-output\n",
        encoding="utf-8",
    )

    assert check_repo.scan_secrets(tmp_path) == []
