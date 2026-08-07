"""Exclusive ownership for one live run output."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from ..io.file_lock import FileLockUnavailableError, exclusive_file_lock


@contextmanager
def exclusive_run_lock(output_path: str) -> Iterator[None]:
    """Fail fast when another process already owns the same run output."""
    lock_path = f"{output_path}.run.lock"
    try:
        with exclusive_file_lock(lock_path, blocking=False):
            yield
    except FileLockUnavailableError as exc:
        raise RuntimeError(
            f"run output is already active: {output_path}; use a different --run-name"
        ) from exc
