"""Runtime artifact cleanup command implementation."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
import shutil

from ..cli.constants import PROJECT_ROOT
from ..config.application import CleanConfig
from ..io.common import sanitize_dataset_id_for_filename
from ..io.file_lock import (
    FileLockUnavailableError,
    exclusive_file_lock,
    is_exclusive_file_lock_held,
)


def _selected_dataset_dirs(project_root: Path, config: CleanConfig) -> list[Path]:
    datasets_dir = project_root / "datasets"
    if not datasets_dir.is_dir():
        return []
    if config.dataset_id:
        dataset_dir = datasets_dir / sanitize_dataset_id_for_filename(config.dataset_id)
        return [dataset_dir] if dataset_dir.is_dir() else []
    return [
        path for path in datasets_dir.iterdir() if path.is_dir() and not path.is_symlink()
    ]


def _dataset_runtime_targets(project_root: Path, config: CleanConfig) -> list[Path]:
    dataset_dirs = _selected_dataset_dirs(project_root, config)

    return [
        dataset_dir / runtime_dir
        for dataset_dir in dataset_dirs
        for runtime_dir in ("cache", "runs", "feedback")
    ]


def _dataset_lock_files(project_root: Path, config: CleanConfig) -> list[Path]:
    """Return advisory lock files left at dataset roots by file transactions."""
    dataset_dirs = _selected_dataset_dirs(project_root, config)

    return [
        lock_file
        for dataset_dir in dataset_dirs
        for lock_file in dataset_dir.glob("*.lock")
        if lock_file.is_file() and lock_file.name != ".runtime-clean.lock"
    ]


def _active_run_locks(dataset_dirs: list[Path]) -> list[Path]:
    """Return run locks that are currently held by another process."""
    active: list[Path] = []
    for dataset_dir in dataset_dirs:
        runs_dir = dataset_dir / "runs"
        if not runs_dir.is_dir():
            continue
        for lock_path in runs_dir.rglob("*.run.lock"):
            if not lock_path.is_file():
                continue
            try:
                if is_exclusive_file_lock_held(str(lock_path)):
                    active.append(lock_path)
            except OSError:
                active.append(lock_path)
    return active


@contextmanager
def _exclusive_cleanup_gates(dataset_dirs: list[Path]) -> Iterator[None]:
    """Block new standard runs while a confirmed cleanup is in progress."""
    with ExitStack() as stack:
        try:
            for dataset_dir in dataset_dirs:
                stack.enter_context(
                    exclusive_file_lock(
                        str(dataset_dir / ".runtime-clean.lock"),
                        blocking=False,
                    )
                )
        except FileLockUnavailableError as exc:
            raise RuntimeError("runtime cleanup is already active; retry after it completes") from exc
        yield


def clean_runtime_artifacts(
    config: CleanConfig,
    *,
    project_root: Path = PROJECT_ROOT,
) -> int:
    """Remove local runtime artifacts while preserving encrypted credentials by default."""
    targets = _dataset_runtime_targets(project_root, config) + _dataset_lock_files(
        project_root, config
    )
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

    if config.preview_only:
        for target in existing_targets:
            print(f"[clean] would remove {target}")
    else:
        dataset_dirs = _selected_dataset_dirs(project_root, config)
        with _exclusive_cleanup_gates(dataset_dirs):
            active_locks = _active_run_locks(dataset_dirs)
            if active_locks:
                active = ", ".join(str(path) for path in active_locks[:3])
                suffix = "..." if len(active_locks) > 3 else ""
                raise RuntimeError(
                    "refusing to clean active runtime; running outputs hold locks: "
                    f"{active}{suffix}"
                )
            for target in existing_targets:
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
