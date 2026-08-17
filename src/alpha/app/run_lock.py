"""Exclusive ownership for one live run output."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..io.file_lock import (
    FileLockUnavailableError,
    exclusive_file_lock,
    is_exclusive_file_lock_held,
)


def runtime_cleanup_lock_path(output_path: str) -> str | None:
    """Return the dataset-level cleanup gate for a standard run output."""
    output = Path(output_path).expanduser().resolve()
    for ancestor in (output.parent, *output.parents):
        if ancestor.name == "runs":
            return str(ancestor.parent / ".runtime-clean.lock")
    return None


def is_run_lock_held(output_path: str) -> bool:
    """Read an existing output lock without creating a lock file."""
    return is_exclusive_file_lock_held(f"{output_path}.run.lock")


@contextmanager
def exclusive_run_lock(output_path: str) -> Iterator[None]:
    """Fail fast when another process already owns the same run output."""
    lock_path = f"{output_path}.run.lock"
    try:
        with exclusive_file_lock(lock_path, blocking=False):
            cleanup_lock_path = runtime_cleanup_lock_path(output_path)
            if cleanup_lock_path:
                try:
                    with exclusive_file_lock(cleanup_lock_path, blocking=False):
                        pass
                except FileLockUnavailableError as exc:
                    raise RuntimeError(
                        f"runtime cleanup is already active for {output_path}; "
                        "retry after cleanup completes"
                    ) from exc
            yield
    except FileLockUnavailableError as exc:
        raise RuntimeError(
            f"run output is already active: {output_path}; use a different --run-name"
        ) from exc
