"""Cross-thread result transaction locking tests."""

from __future__ import annotations

from threading import Event, Thread

from alpha.io.results_store import exclusive_results_transaction


def test_results_transaction_serializes_same_feedback_path(tmp_path) -> None:
    output_path = str(tmp_path / "feedback" / "summary.json")
    first_entered = Event()
    release_first = Event()
    second_attempting = Event()
    second_entered = Event()

    def hold_first() -> None:
        with exclusive_results_transaction(output_path):
            first_entered.set()
            assert release_first.wait(timeout=2)

    def enter_second() -> None:
        second_attempting.set()
        with exclusive_results_transaction(output_path):
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
