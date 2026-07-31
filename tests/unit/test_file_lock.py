"""Filesystem lock behavior tests."""

from __future__ import annotations

from types import SimpleNamespace

from alpha.io import file_lock


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
        LK_LOCK=10,
        LK_UNLCK=11,
        locking=lambda _fd, mode, size: calls.append((mode, size)),
    )
    monkeypatch.setattr(file_lock.os, "name", "nt")
    monkeypatch.setattr(file_lock, "import_module", lambda name: fake_msvcrt)

    lock_path = tmp_path / "result.lock"
    with file_lock.exclusive_file_lock(str(lock_path)):
        assert lock_path.read_bytes() == b"\0"
        assert calls[-1] == (fake_msvcrt.LK_LOCK, 1)

    assert calls[-1] == (fake_msvcrt.LK_UNLCK, 1)
