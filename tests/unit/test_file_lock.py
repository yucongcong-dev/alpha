"""Filesystem lock behavior tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import errno
from types import SimpleNamespace

import pytest

import alpha.app.run_lock as run_lock
import alpha.io.file_lock as file_lock


def test_thread_lock_reuses_canonical_lock_object(tmp_path) -> None:
    lock_path = tmp_path / "result.lock"

    first = file_lock._thread_lock(str(lock_path))
    second = file_lock._thread_lock(str(lock_path))

    assert first is second


def test_exclusive_file_lock_uses_posix_flock_and_unlocks(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(file_lock.os, "name", "posix")
    calls: list[tuple[int, int]] = []
    fake_fcntl = SimpleNamespace(
        LOCK_EX=1,
        LOCK_UN=2,
        flock=lambda fd, operation: calls.append((fd, operation)),
    )
    monkeypatch.setattr(file_lock, "import_module", lambda name: fake_fcntl)

    lock_path = tmp_path / "nested" / "result.lock"
    with file_lock.exclusive_file_lock(str(lock_path)):
        assert lock_path.exists()
        assert calls[-1][1] == fake_fcntl.LOCK_EX

    assert calls[-1][1] == fake_fcntl.LOCK_UN


def test_exclusive_file_lock_unlocks_after_body_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(file_lock.os, "name", "posix")
    calls: list[int] = []
    fake_fcntl = SimpleNamespace(
        LOCK_EX=1,
        LOCK_UN=2,
        flock=lambda _fd, operation: calls.append(operation),
    )
    monkeypatch.setattr(file_lock, "import_module", lambda name: fake_fcntl)

    try:
        with file_lock.exclusive_file_lock(str(tmp_path / "result.lock")):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert calls == [fake_fcntl.LOCK_EX, fake_fcntl.LOCK_UN]


def test_exclusive_file_lock_uses_windows_byte_lock(monkeypatch, tmp_path) -> None:
    calls: list[tuple[int, int]] = []
    fake_msvcrt = SimpleNamespace(
        LK_UNLCK=11,
        LK_NBLCK=12,
        locking=lambda _fd, mode, size: calls.append((mode, size)),
    )
    monkeypatch.setattr(file_lock.os, "name", "nt")
    monkeypatch.setattr(file_lock, "import_module", lambda name: fake_msvcrt)

    lock_path = tmp_path / "result.lock"
    with file_lock.exclusive_file_lock(str(lock_path)):
        assert lock_path.read_bytes() == b"\0"
        assert calls[-1] == (fake_msvcrt.LK_NBLCK, 1)

    assert calls[-1] == (fake_msvcrt.LK_UNLCK, 1)


def test_exclusive_file_lock_uses_nonblocking_posix_mode(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(file_lock.os, "name", "posix")
    calls: list[int] = []
    fake_fcntl = SimpleNamespace(
        LOCK_EX=1,
        LOCK_NB=4,
        LOCK_UN=2,
        flock=lambda _fd, operation: calls.append(operation),
    )
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_fcntl)

    with file_lock.exclusive_file_lock(str(tmp_path / "result.lock"), blocking=False):
        pass

    assert calls == [fake_fcntl.LOCK_EX | fake_fcntl.LOCK_NB, fake_fcntl.LOCK_UN]


def test_exclusive_file_lock_reports_nonblocking_contention(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(file_lock.os, "name", "posix")

    def fail_to_lock(_fd: int, _operation: int) -> None:
        raise BlockingIOError("busy")

    fake_fcntl = SimpleNamespace(
        LOCK_EX=1,
        LOCK_NB=4,
        LOCK_UN=2,
        flock=fail_to_lock,
    )
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_fcntl)

    with (
        pytest.raises(file_lock.FileLockUnavailableError, match="already held"),
        file_lock.exclusive_file_lock(str(tmp_path / "result.lock"), blocking=False),
    ):
        pass


def test_exclusive_file_lock_reports_thread_contention(monkeypatch, tmp_path) -> None:
    fake_thread_lock = SimpleNamespace(acquire=lambda **_kwargs: False)
    monkeypatch.setattr(file_lock, "_thread_lock", lambda _path: fake_thread_lock)

    with (
        pytest.raises(file_lock.FileLockUnavailableError, match="already held"),
        file_lock.exclusive_file_lock(str(tmp_path / "result.lock"), blocking=False),
    ):
        pass


def test_lock_probe_does_not_create_missing_lock_file(tmp_path) -> None:
    lock_path = tmp_path / "missing.lock"

    assert file_lock.is_exclusive_file_lock_held(str(lock_path)) is False
    assert not lock_path.exists()


def test_lock_probe_uses_and_releases_windows_byte_lock(monkeypatch, tmp_path) -> None:
    calls: list[tuple[int, int]] = []
    fake_msvcrt = SimpleNamespace(
        LK_NBLCK=12,
        LK_UNLCK=11,
        locking=lambda _fd, mode, size: calls.append((mode, size)),
    )
    lock_path = tmp_path / "result.lock"
    monkeypatch.setattr(file_lock.os, "name", "nt")
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_msvcrt)

    lock_path.touch()
    assert file_lock.is_exclusive_file_lock_held(str(lock_path)) is False
    assert calls == []

    lock_path.write_bytes(b"x")
    assert file_lock.is_exclusive_file_lock_held(str(lock_path)) is False
    assert calls == [(fake_msvcrt.LK_NBLCK, 1), (fake_msvcrt.LK_UNLCK, 1)]


def test_lock_probe_detects_windows_byte_lock_contention(monkeypatch, tmp_path) -> None:
    def fail_to_lock(_fd: int, _mode: int, _size: int) -> None:
        raise OSError(errno.EACCES, "busy")

    fake_msvcrt = SimpleNamespace(LK_NBLCK=12, LK_UNLCK=11, locking=fail_to_lock)
    lock_path = tmp_path / "result.lock"
    lock_path.write_bytes(b"x")
    monkeypatch.setattr(file_lock.os, "name", "nt")
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_msvcrt)

    assert file_lock.is_exclusive_file_lock_held(str(lock_path)) is True


def test_lock_probe_uses_and_releases_posix_flock(monkeypatch, tmp_path) -> None:
    calls: list[int] = []
    fake_fcntl = SimpleNamespace(
        LOCK_EX=1,
        LOCK_NB=4,
        LOCK_UN=2,
        flock=lambda _fd, operation: calls.append(operation),
    )
    lock_path = tmp_path / "result.lock"
    lock_path.write_bytes(b"x")
    monkeypatch.setattr(file_lock.os, "name", "posix")
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_fcntl)

    assert file_lock.is_exclusive_file_lock_held(str(lock_path)) is False
    assert calls == [fake_fcntl.LOCK_EX | fake_fcntl.LOCK_NB, fake_fcntl.LOCK_UN]


@pytest.mark.parametrize("platform_name", ["nt", "posix"])
def test_lock_probe_preserves_unexpected_os_error(monkeypatch, tmp_path, platform_name) -> None:
    def fail_to_lock(*_args: object) -> None:
        raise OSError(errno.EIO, "filesystem lock failed")

    fake_lock_module = SimpleNamespace(
        LK_NBLCK=12,
        LK_UNLCK=11,
        LOCK_EX=1,
        LOCK_NB=4,
        LOCK_UN=2,
        locking=fail_to_lock,
        flock=fail_to_lock,
    )
    lock_path = tmp_path / "result.lock"
    lock_path.write_bytes(b"x")
    monkeypatch.setattr(file_lock.os, "name", platform_name)
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_lock_module)

    with pytest.raises(OSError, match="filesystem lock failed"):
        file_lock.is_exclusive_file_lock_held(str(lock_path))


def test_lock_probe_handles_lock_file_removed_after_existence_check(monkeypatch, tmp_path) -> None:
    lock_path = tmp_path / "result.lock"
    lock_path.write_bytes(b"x")

    def removed_file(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(file_lock.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(file_lock, "open", removed_file, raising=False)

    assert file_lock.is_exclusive_file_lock_held(str(lock_path)) is False


def test_exclusive_file_lock_uses_nonblocking_windows_mode(monkeypatch, tmp_path) -> None:
    calls: list[tuple[int, int]] = []
    fake_msvcrt = SimpleNamespace(
        LK_NBLCK=12,
        LK_UNLCK=11,
        locking=lambda _fd, mode, size: calls.append((mode, size)),
    )
    monkeypatch.setattr(file_lock.os, "name", "nt")
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_msvcrt)
    lock_path = tmp_path / "result.lock"
    lock_path.write_bytes(b"x")

    with file_lock.exclusive_file_lock(str(lock_path), blocking=False):
        pass

    assert calls == [(fake_msvcrt.LK_NBLCK, 1), (fake_msvcrt.LK_UNLCK, 1)]


def test_exclusive_file_lock_maps_nonblocking_windows_contention(monkeypatch, tmp_path) -> None:
    def fail_to_lock(_fd: int, _mode: int, _size: int) -> None:
        raise OSError("busy")

    fake_msvcrt = SimpleNamespace(
        LK_NBLCK=12,
        LK_UNLCK=11,
        locking=fail_to_lock,
    )
    monkeypatch.setattr(file_lock.os, "name", "nt")
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_msvcrt)

    with (
        pytest.raises(file_lock.FileLockUnavailableError, match="already held"),
        file_lock.exclusive_file_lock(str(tmp_path / "result.lock"), blocking=False),
    ):
        pass


@pytest.mark.parametrize("platform_name", ["nt", "posix"])
def test_exclusive_file_lock_preserves_blocking_os_error(
    monkeypatch, tmp_path, platform_name
) -> None:
    def fail_to_lock(*_args: object) -> None:
        raise OSError("filesystem lock failed")

    fake_lock_module = SimpleNamespace(
        LK_NBLCK=12,
        LK_UNLCK=11,
        LOCK_EX=1,
        LOCK_NB=4,
        LOCK_UN=2,
        locking=fail_to_lock,
        flock=fail_to_lock,
    )
    monkeypatch.setattr(file_lock.os, "name", platform_name)
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_lock_module)

    with (
        pytest.raises(OSError, match="filesystem lock failed"),
        file_lock.exclusive_file_lock(str(tmp_path / "result.lock")),
    ):
        pass


def test_exclusive_file_lock_retries_windows_contention_when_blocking(
    monkeypatch, tmp_path
) -> None:
    calls: list[tuple[int, int]] = []
    sleeps: list[float] = []

    def lock(_fd: int, mode: int, size: int) -> None:
        calls.append((mode, size))
        if len(calls) < 3:
            raise OSError(errno.EACCES, "busy")

    fake_msvcrt = SimpleNamespace(LK_NBLCK=12, LK_UNLCK=11, locking=lock)
    monkeypatch.setattr(file_lock.os, "name", "nt")
    monkeypatch.setattr(file_lock, "import_module", lambda _name: fake_msvcrt)
    monkeypatch.setattr(file_lock.time, "sleep", sleeps.append)

    with file_lock.exclusive_file_lock(str(tmp_path / "result.lock")):
        pass

    assert calls == [(12, 1), (12, 1), (12, 1), (11, 1)]
    assert sleeps == [file_lock._WINDOWS_LOCK_RETRY_SECONDS] * 2


def test_exclusive_run_lock_uses_output_scoped_nonblocking_lock(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    @contextmanager
    def fake_lock(path: str, *, blocking: bool) -> Iterator[None]:
        captured.update(path=path, blocking=blocking)
        yield

    monkeypatch.setattr(run_lock, "exclusive_file_lock", fake_lock)
    output_path = str(tmp_path / "summary.json")

    with run_lock.exclusive_run_lock(output_path):
        pass

    assert captured == {"path": f"{output_path}.run.lock", "blocking": False}


def test_exclusive_run_lock_explains_contention(monkeypatch, tmp_path) -> None:
    def fail_to_lock(*_args: object, **_kwargs: object) -> None:
        raise file_lock.FileLockUnavailableError("busy")

    monkeypatch.setattr(run_lock, "exclusive_file_lock", fail_to_lock)

    with (
        pytest.raises(RuntimeError, match="different --run-name"),
        run_lock.exclusive_run_lock(str(tmp_path / "summary.json")),
    ):
        pass


def test_exclusive_run_lock_rejects_runtime_cleanup_gate(tmp_path) -> None:
    output_path = tmp_path / "datasets" / "demo" / "runs" / "nightly" / "summary.json"
    cleanup_lock = output_path.parents[2] / ".runtime-clean.lock"

    with (
        file_lock.exclusive_file_lock(str(cleanup_lock)),
        pytest.raises(RuntimeError, match="runtime cleanup"),
        run_lock.exclusive_run_lock(str(output_path)),
    ):
        pass


def test_run_lock_probe_detects_an_active_output_lock(tmp_path) -> None:
    output_path = tmp_path / "summary.json"
    lock_path = f"{output_path}.run.lock"

    with file_lock.exclusive_file_lock(lock_path):
        assert run_lock.is_run_lock_held(str(output_path)) is True
