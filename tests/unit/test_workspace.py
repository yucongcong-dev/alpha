"""Workspace discovery tests."""

from __future__ import annotations

from pathlib import Path

from alpha.workspace import WORKSPACE_ENV, WorkspacePaths, discover_workspace_root


def test_explicit_workspace_environment_wins(monkeypatch, tmp_path) -> None:
    workspace_root = tmp_path / "runtime"
    monkeypatch.setenv(WORKSPACE_ENV, str(workspace_root))

    resolved = discover_workspace_root(resource_root=tmp_path / "package", cwd=tmp_path)

    assert resolved == workspace_root.resolve()


def test_installed_package_falls_back_to_user_workspace(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(WORKSPACE_ENV, raising=False)
    package_root = tmp_path / "site-packages" / "alpha"
    empty_cwd = tmp_path / "empty"
    package_root.mkdir(parents=True)
    empty_cwd.mkdir()

    resolved = discover_workspace_root(resource_root=package_root, cwd=empty_cwd)

    assert resolved == (Path.home() / ".alpha").resolve()
    assert package_root not in resolved.parents


def test_workspace_separates_runtime_and_resource_paths(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    resource_root = tmp_path / "resources"
    (resource_root / "config").mkdir(parents=True)
    workspace = WorkspacePaths(root=runtime_root, resource_root=resource_root)

    assert workspace.results_dir == runtime_root / "results"
    assert workspace.cache_dir == runtime_root / "cache"
    assert workspace.config_dir == resource_root / "config"
