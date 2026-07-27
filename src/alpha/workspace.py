"""Workspace and packaged-resource path discovery."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

WORKSPACE_ENV = "ALPHA_WORKSPACE_ROOT"


def find_resource_root(start: Path | None = None) -> Path:
    """Locate the source/resource root without assuming a fixed package depth."""
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent
    candidates = (current, *current.parents)
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file():
            return candidate
        if (candidate / "config" / "settings.yaml").is_file():
            return candidate
    for candidate in candidates:
        if (candidate / "resources" / "config" / "settings.yaml").is_file():
            return candidate
    return Path(__file__).resolve().parent


def _looks_like_workspace(path: Path) -> bool:
    return any(
        (path / marker).exists()
        for marker in (
            "pyproject.toml",
            "config",
            "datasets",
            "templates",
            "data",
            ".alpha-workspace",
        )
    )


def discover_workspace_root(
    *,
    resource_root: Path | None = None,
    cwd: Path | None = None,
) -> Path:
    """Choose a writable runtime root independently from package installation."""
    explicit = os.environ.get(WORKSPACE_ENV, "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    resolved_resource_root = (resource_root or find_resource_root()).resolve()
    package_root = Path(__file__).resolve().parent
    if (
        resolved_resource_root != package_root
        and (resolved_resource_root / "pyproject.toml").is_file()
    ):
        return resolved_resource_root

    current_dir = (cwd or Path.cwd()).resolve()
    if _looks_like_workspace(current_dir):
        return current_dir
    return (Path.home() / ".alpha").resolve()


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    """Canonical read-only resource root and writable runtime directories."""

    root: Path
    resource_root: Path

    @classmethod
    def discover(cls) -> WorkspacePaths:
        resource_root = find_resource_root()
        return cls(
            root=discover_workspace_root(resource_root=resource_root),
            resource_root=resource_root,
        )

    @property
    def credentials_dir(self) -> Path:
        return self.root / ".credentials"

    @property
    def datasets_dir(self) -> Path:
        return self.root / "datasets"

    def dataset_dir(self, dataset_key: str) -> Path:
        """Return one dataset-owned workspace root."""
        return self.datasets_dir / dataset_key

    @property
    def config_dir(self) -> Path:
        packaged_config = self.resource_root / "config"
        if (packaged_config / "settings.yaml").is_file():
            return packaged_config
        installed_config = self.resource_root / "resources" / "config"
        if (installed_config / "settings.yaml").is_file():
            return installed_config
        return self.root / "config"


DEFAULT_WORKSPACE = WorkspacePaths.discover()
