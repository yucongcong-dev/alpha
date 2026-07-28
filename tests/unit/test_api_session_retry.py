"""HTTP session and operation retry contract tests."""

from __future__ import annotations

from typing import Any

import pytest

from alpha.api.client import BrainClient
from alpha.api.retry import login_with_retry, retry_operation
from alpha.exceptions import (
    BrainAPIError,
    BrainQueueBusyError,
    BrainRateLimitError,
    BrainStopRequested,
)


def test_login_sends_basic_authorization_header(monkeypatch) -> None:
    client = BrainClient("user@example.com", "secret")
    captured: dict[str, Any] = {}

    def fake_raw_request(method: str, url: str, **kwargs: Any):
        captured.update(method=method, url=url, **kwargs)
        return 201, {}, b"{}"

    monkeypatch.setattr(client, "raw_request", fake_raw_request)

    client.login()

    assert captured["method"] == "POST"
    assert captured["headers"]["Authorization"] == "Basic dXNlckBleGFtcGxlLmNvbTpzZWNyZXQ="


def test_login_surfaces_rejected_credentials(monkeypatch) -> None:
    client = BrainClient("user@example.com", "wrong")
    monkeypatch.setattr(client, "raw_request", lambda *_args, **_kwargs: (401, {}, b'{"x": 1}'))

    with pytest.raises(BrainAPIError, match="Login failed: 401"):
        client.login()


def test_request_reauthenticates_after_401(monkeypatch) -> None:
    client = BrainClient("user@example.com", "secret")
    responses = iter([(401, {}, b"expired"), (200, {}, b"ok")])
    login_calls: list[bool] = []
    monkeypatch.setattr(client, "raw_request", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(client, "login", lambda: login_calls.append(True))

    status, _, content = client.request("GET", "https://example.test", expected={200}, retries=2)

    assert status == 200
    assert content == b"ok"
    assert login_calls == [True]


def test_request_raises_rate_limit_error_after_retry_budget(monkeypatch) -> None:
    client = BrainClient("user@example.com", "secret")
    waits: list[float] = []
    monkeypatch.setattr(
        client,
        "raw_request",
        lambda *_args, **_kwargs: (429, {"Retry-After": "3"}, b'{"detail": "slow"}'),
    )
    monkeypatch.setattr(
        "alpha.api.session.wait_seconds", lambda seconds, *_args: waits.append(seconds)
    )

    with pytest.raises(BrainRateLimitError) as exc_info:
        client.request("GET", "https://example.test", retries=2)

    assert exc_info.value.retry_after == 6
    assert waits == [6.0, 6.0]


def test_request_retries_server_error_then_returns(monkeypatch) -> None:
    client = BrainClient("user@example.com", "secret")
    responses = iter([(503, {}, b"busy"), (200, {}, b"ok")])
    waits: list[str] = []
    monkeypatch.setattr(client, "raw_request", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(
        "alpha.api.session.wait_seconds", lambda _seconds, reason: waits.append(reason)
    )

    status, _, content = client.request("GET", "https://example.test", expected={200}, retries=2)

    assert (status, content) == (200, b"ok")
    assert waits == ["server error 503"]


def test_raw_request_encodes_query_and_non_byte_data() -> None:
    client = BrainClient("user@example.com", "secret")
    captured: dict[str, Any] = {}

    class FakeBackend:
        def request(self, **kwargs: Any):
            captured.update(kwargs)
            return 200, {}, b"ok"

    client._http_backend = FakeBackend()  # type: ignore[assignment]

    client.raw_request(
        "POST",
        "https://example.test/path?existing=1",
        params={"field": "a b"},
        data="payload",
    )

    assert captured["url"] == "https://example.test/path?existing=1&field=a+b"
    assert captured["data"] == b"payload"


def test_retry_operation_retries_regular_exception(monkeypatch) -> None:
    attempts = 0
    waits: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("temporary")
        return "ok"

    monkeypatch.setattr(
        "alpha.api.retry.wait_seconds", lambda seconds, *_args: waits.append(seconds)
    )

    assert retry_operation("operation", 3, operation, retry_wait_seconds=0.25) == "ok"
    assert attempts == 3
    assert waits == [0.25, 0.25]


@pytest.mark.parametrize(
    "error",
    [
        BrainAPIError("api"),
        BrainQueueBusyError("queue"),
        BrainRateLimitError("rate"),
    ],
)
def test_retry_operation_does_not_repeat_terminal_api_errors(error: BrainAPIError) -> None:
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise error

    with pytest.raises(BrainAPIError, match="failed after 4 attempts"):
        retry_operation("operation", 4, operation, retry_wait_seconds=0)

    assert attempts == 1


def test_retry_operation_honors_abort_before_first_attempt() -> None:
    with pytest.raises(BrainStopRequested, match="aborted"):
        retry_operation("operation", 2, lambda: None, should_abort=lambda: True)


def test_login_with_retry_distinguishes_invalid_credentials(monkeypatch) -> None:
    class FakeClient:
        def login(self) -> None:
            raise BrainAPIError("401 INVALID_CREDENTIALS")

    monkeypatch.setattr("alpha.api.retry.wait_seconds", lambda *_args, **_kwargs: None)

    with pytest.raises(BrainAPIError, match="账号或密码无效"):
        login_with_retry(FakeClient(), 2)  # type: ignore[arg-type]


def test_login_with_retry_preserves_operational_context(monkeypatch) -> None:
    class FakeClient:
        def login(self) -> None:
            raise RuntimeError("network unavailable")

    monkeypatch.setattr("alpha.api.retry.wait_seconds", lambda *_args, **_kwargs: None)

    with pytest.raises(BrainAPIError, match="最后一次错误"):
        login_with_retry(FakeClient(), 1)  # type: ignore[arg-type]
