"""Runtime cleanup command tests."""

from __future__ import annotations

from types import SimpleNamespace

from alpha.main import clean_runtime_artifacts


def test_clean_runtime_artifacts_preserves_credentials(tmp_path) -> None:
    """clean should remove runtime dirs while keeping credentials by default."""
    for dirname in ("cache", "results", ".credentials"):
        path = tmp_path / dirname
        path.mkdir()
        (path / "marker.txt").write_text("x", encoding="utf-8")

    args = SimpleNamespace(include_credentials=False, dry_run_clean=False)

    assert clean_runtime_artifacts(args, project_root=tmp_path) == 0
    assert not (tmp_path / "cache").exists()
    assert not (tmp_path / "results").exists()
    assert (tmp_path / ".credentials").exists()


def test_clean_runtime_artifacts_can_include_credentials(tmp_path) -> None:
    """--include-credentials should remove encrypted credential storage too."""
    creds = tmp_path / ".credentials"
    creds.mkdir()
    (creds / "credentials.json").write_text("{}", encoding="utf-8")

    args = SimpleNamespace(include_credentials=True, dry_run_clean=False)

    assert clean_runtime_artifacts(args, project_root=tmp_path) == 0
    assert not creds.exists()


def test_clean_runtime_artifacts_dry_run_keeps_files(tmp_path) -> None:
    """--dry-run-clean should only print targets and not delete anything."""
    cache = tmp_path / "cache"
    cache.mkdir()

    args = SimpleNamespace(include_credentials=False, dry_run_clean=True)

    assert clean_runtime_artifacts(args, project_root=tmp_path) == 0
    assert cache.exists()
