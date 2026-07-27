"""Workspace discovery tests."""

from __future__ import annotations

from pathlib import Path

from alpha.workspace import (
    WORKSPACE_ENV,
    WorkspacePaths,
    discover_workspace_root,
    find_resource_root,
)


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
    (resource_root / "config" / "settings.yaml").write_text("global: {}\n", encoding="utf-8")
    workspace = WorkspacePaths(root=runtime_root, resource_root=resource_root)

    assert workspace.results_dir == runtime_root / "results"
    assert workspace.cache_dir == runtime_root / "cache"
    assert workspace.config_dir == resource_root / "config"


def test_installed_resource_layout_is_discovered(tmp_path) -> None:
    package_root = tmp_path / "site-packages" / "alpha"
    config_dir = package_root / "resources" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.yaml").write_text("global: {}\n", encoding="utf-8")
    module_path = package_root / "workspace.py"
    module_path.write_text("", encoding="utf-8")

    assert find_resource_root(module_path) == package_root
    workspace = WorkspacePaths(root=tmp_path / "runtime", resource_root=package_root)
    assert workspace.config_dir == config_dir


def test_packaged_default_configs_match_source_configs() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    source_config_dir = repository_root / "config"
    packaged_config_dir = repository_root / "src" / "alpha" / "resources" / "config"

    for source_path in sorted(source_config_dir.glob("*.yaml")):
        packaged_path = packaged_config_dir / source_path.name
        assert packaged_path.read_bytes() == source_path.read_bytes()
