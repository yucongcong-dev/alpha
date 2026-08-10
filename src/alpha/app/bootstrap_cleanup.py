"""Runtime artifact cleanup command implementation."""

from __future__ import annotations

from pathlib import Path
import shutil

from ..cli.constants import PROJECT_ROOT
from ..config.application import CleanConfig
from ..io.common import sanitize_dataset_id_for_filename


def _dataset_runtime_targets(project_root: Path, config: CleanConfig) -> list[Path]:
    datasets_dir = project_root / "datasets"
    if not datasets_dir.is_dir():
        return []

    if config.dataset_id:
        dataset_dirs = [datasets_dir / sanitize_dataset_id_for_filename(config.dataset_id)]
    else:
        dataset_dirs = [
            path for path in datasets_dir.iterdir() if path.is_dir() and not path.is_symlink()
        ]

    return [
        dataset_dir / runtime_dir
        for dataset_dir in dataset_dirs
        for runtime_dir in ("cache", "runs", "feedback")
    ]


def clean_runtime_artifacts(
    config: CleanConfig,
    *,
    project_root: Path = PROJECT_ROOT,
) -> int:
    """Remove local runtime artifacts while preserving encrypted credentials by default."""
    targets = _dataset_runtime_targets(project_root, config)
    if not config.dataset_id:
        targets.extend(
            [
                # Legacy runtime roots are global rather than dataset scoped.
                project_root / "cache",
                project_root / "results",
            ]
        )
    if config.include_credentials:
        targets.append(project_root / ".credentials")

    existing_targets = [target for target in targets if target.exists()]
    if not existing_targets:
        print("[clean] no runtime artifacts found")
        return 0

    for target in existing_targets:
        if config.preview_only:
            print(f"[clean] would remove {target}")
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        print(f"[clean] removed {target}")

    if config.preview_only:
        scope_hint = f"--dataset-id {config.dataset_id}" if config.dataset_id else "--all-datasets"
        print(f"[clean] preview only; add {scope_hint} --confirm-clean to remove these paths")
    if not config.include_credentials:
        print("[clean] credentials preserved (.credentials/)")
    return 0
