"""Small cross-thread and POSIX cross-process filesystem locks."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
import threading

_FILE_LOCKS_GUARD = threading.Lock()
_FILE_LOCKS: dict[str, threading.RLock] = {}


def _thread_lock(lock_path: str) -> threading.RLock:
    canonical_path = os.path.abspath(lock_path)
    with _FILE_LOCKS_GUARD:
        return _FILE_LOCKS.setdefault(canonical_path, threading.RLock())


@contextmanager
def exclusive_file_lock(lock_path: str) -> Iterator[None]:
    """Serialize a filesystem transaction across threads and POSIX processes."""
    directory = os.path.dirname(os.path.abspath(lock_path)) or "."
    os.makedirs(directory, exist_ok=True)
    with _thread_lock(lock_path), open(lock_path, "a+b") as lock_handle:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - Windows fallback uses the thread lock.
            yield
            return
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
