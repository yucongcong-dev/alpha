"""Simulation create and polling contract tests."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from alpha.api.simulations import BrainSimulationsMixin
from alpha.exceptions import BrainAPIError, BrainQueueBusyError


class FakeSimulationClient(BrainSimulationsMixin):
    def __init__(self, responses: Iterable[tuple[int, dict[str, str], bytes]]) -> None:
        self.responses = iter(responses)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any):
        self.requests.append((method, url, kwargs))
        return next(self.responses)


def test_create_simulation_returns_location() -> None:
    client = FakeSimulationClient([(201, {"Location": "/simulations/123"}, b"")])

    assert client.create_simulation({"regular": {}}) == "/simulations/123"
    assert client.requests[0][0] == "POST"


def test_create_simulation_requires_location_header() -> None:
    client = FakeSimulationClient([(201, {}, b"")])

    with pytest.raises(BrainAPIError, match="Location header is missing"):
        client.create_simulation({"regular": {}})


def test_poll_simulation_waits_for_pending_then_returns(monkeypatch) -> None:
    client = FakeSimulationClient(
        [
            (200, {"Retry-After": "2"}, b'{"status": "PENDING", "progress": 10}'),
            (200, {}, b'{"status": "COMPLETED", "alpha": "a1"}'),
        ]
    )
    waits: list[float] = []
    monkeypatch.setattr(
        "alpha.api.simulations.wait_seconds",
        lambda seconds, *_args, **_kwargs: waits.append(seconds),
    )

    payload = client.poll_simulation(
        "/simulations/123",
        max_polls=3,
        max_wait_seconds=60,
        max_pending_cycles=2,
        max_queue_seconds=60,
    )

    assert payload["status"] == "COMPLETED"
    assert waits == [3.0]
    assert client.requests[0][1].endswith("/simulations/123")


def test_poll_simulation_ignores_retry_after_for_terminal_state(monkeypatch) -> None:
    client = FakeSimulationClient(
        [(200, {"Retry-After": "20"}, b'{"status": "FAILED", "message": "bad"}')]
    )
    monkeypatch.setattr(
        "alpha.api.simulations.wait_seconds",
        lambda *_args, **_kwargs: pytest.fail("terminal response must not wait"),
    )

    payload = client.poll_simulation(
        "https://example.test/simulations/123",
        max_polls=1,
        max_wait_seconds=60,
        max_pending_cycles=1,
        max_queue_seconds=60,
    )

    assert payload["status"] == "FAILED"


def test_poll_simulation_enforces_pending_cycle_budget(monkeypatch) -> None:
    client = FakeSimulationClient(
        [
            (200, {}, b'{"status": "QUEUED"}'),
            (200, {}, b'{"status": "QUEUED"}'),
        ]
    )
    monkeypatch.setattr("alpha.api.simulations.wait_seconds", lambda *_args, **_kwargs: None)

    with pytest.raises(BrainQueueBusyError, match="queued too long"):
        client.poll_simulation(
            "/simulations/123",
            max_polls=3,
            max_wait_seconds=60,
            max_pending_cycles=1,
            max_queue_seconds=60,
        )


def test_pending_limits_enforce_elapsed_queue_budget(monkeypatch) -> None:
    monkeypatch.setattr("alpha.api.simulations.time.monotonic", lambda: 11.0)

    with pytest.raises(BrainQueueBusyError, match="queue budget"):
        BrainSimulationsMixin._check_pending_limits(1, 3, 10, 0.0, "/simulations/123")


def test_poll_simulation_enforces_max_polls(monkeypatch) -> None:
    client = FakeSimulationClient([(200, {}, b'{"status": "RUNNING"}')])
    monkeypatch.setattr("alpha.api.simulations.wait_seconds", lambda *_args, **_kwargs: None)

    with pytest.raises(BrainAPIError, match="exceeded max polls"):
        client.poll_simulation(
            "/simulations/123",
            max_polls=1,
            max_wait_seconds=60,
            max_pending_cycles=2,
            max_queue_seconds=60,
        )
