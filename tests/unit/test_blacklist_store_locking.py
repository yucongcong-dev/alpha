"""Cross-thread blacklist transaction locking tests."""

from __future__ import annotations

from threading import Event, Thread

from alpha.policy.blacklist_store import exclusive_blacklist_transaction


def test_blacklist_transaction_serializes_same_dataset(tmp_path) -> None:
    datasets_root = str(tmp_path / "datasets")
    first_entered = Event()
    release_first = Event()
    second_attempting = Event()
    second_entered = Event()

    def hold_first() -> None:
        with exclusive_blacklist_transaction("custom_ds", datasets_root=datasets_root):
            first_entered.set()
            assert release_first.wait(timeout=2)

    def enter_second() -> None:
        second_attempting.set()
        with exclusive_blacklist_transaction("custom_ds", datasets_root=datasets_root):
            second_entered.set()

    first = Thread(target=hold_first)
    second = Thread(target=enter_second)
    first.start()
    assert first_entered.wait(timeout=2)
    second.start()
    assert second_attempting.wait(timeout=2)
    assert not second_entered.wait(timeout=0.05)
    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert second_entered.is_set()


def test_blacklist_transactions_do_not_block_other_datasets(tmp_path) -> None:
    datasets_root = str(tmp_path / "datasets")
    with exclusive_blacklist_transaction("first", datasets_root=datasets_root):
        entered = Event()

        def enter_other_dataset() -> None:
            with exclusive_blacklist_transaction("second", datasets_root=datasets_root):
                entered.set()

        thread = Thread(target=enter_other_dataset)
        thread.start()
        assert entered.wait(timeout=2)
        thread.join(timeout=2)

    assert not thread.is_alive()
