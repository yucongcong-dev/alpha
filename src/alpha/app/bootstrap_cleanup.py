"""Runtime artifact cleanup command implementation."""

from __future__ import annotations

from pathlib import Path
import shutil

from ..cli.constants import PROJECT_ROOT
from ..models.runtime_protocols import CleanRuntimeArgs


def clean_runtime_artifacts(
    args: CleanRuntimeArgs,
    *,
    project_root: Path = PROJECT_ROOT,
) -> int:
    """Remove local runtime artifacts while preserving encrypted credentials by default."""
    dataset_runtime_targets: list[Path] = []
    datasets_dir = project_root / "datasets"
    if datasets_dir.is_dir():
        for dataset_dir in datasets_dir.iterdir():
            if not dataset_dir.is_dir():
                continue
            dataset_runtime_targets.extend(
                [
                    dataset_dir / "cache",
                    dataset_dir / "runs",
                ]
            )
    targets: list[Path] = [
        *dataset_runtime_targets,
        # Legacy runtime roots remain cleanable during the layout transition.
        project_root / "cache",
        project_root / "results",
    ]
    if args.include_credentials:
        targets.append(project_root / ".credentials")

    existing_targets = [target for target in targets if target.exists()]
    if not existing_targets:
        print("[clean] no runtime artifacts found")
        return 0

    for target in existing_targets:
        if args.dry_run_clean:
            print(f"[clean] would remove {target}")
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        print(f"[clean] removed {target}")

    if not args.include_credentials:
        print("[clean] credentials preserved (.credentials/)")
    return 0
