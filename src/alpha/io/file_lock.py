"""Small cross-thread and POSIX cross-process filesystem locks."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
import os
import threading
from typing import Any, cast

_FILE_LOCKS_GUARD = threading.Lock()
_FILE_LOCKS: dict[str, threading.RLock] = {}


def _thread_lock(lock_path: str) -> threading.RLock:
    canonical_path = os.path.abspath(lock_path)
    with _FILE_LOCKS_GUARD:
        return _FILE_LOCKS.setdefault(canonical_path, threading.RLock())


@contextmanager
def exclusive_file_lock(lock_path: str) -> Iterator[None]:
    """Serialize a filesystem transaction across threads and processes."""
    directory = os.path.dirname(os.path.abspath(lock_path)) or "."
    os.makedirs(directory, exist_ok=True)
    with _thread_lock(lock_path), open(lock_path, "a+b") as lock_handle:
        if os.name == "nt":
            # msvcrt locks a byte range from the current file position. Keep one
            # byte in the lock file so independent processes contend on byte zero.
            lock_handle.seek(0, os.SEEK_END)
            if lock_handle.tell() == 0:
                lock_handle.write(b"\0")
                lock_handle.flush()
            lock_handle.seek(0)
            msvcrt = cast(Any, import_module("msvcrt"))
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_LOCK, 1)
            def unlock() -> None:
                msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl = cast(Any, import_module("fcntl"))
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            def unlock() -> None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        try:
            yield
        finally:
            unlock()
