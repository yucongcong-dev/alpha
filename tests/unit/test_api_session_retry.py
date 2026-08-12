"""HTTP session and operation retry contract tests."""

from __future__ import annotations

from typing import Any

import pytest

from alpha.api.client import BrainClient
from alpha.api.retry import login_with_retry, retry_operation
import alpha.api.session as session_module
from alpha.exceptions import (
    BrainAPIError,
    BrainHTTPError,
    BrainQueueBusyError,
    BrainRateLimitError,
    BrainStopRequested,
    BrainTransientError,
)


@pytest.fixture(autouse=True)
def reset_global_request_timing(monkeypatch) -> None:
    monkeypatch.setattr(session_module, "_global_last_request_at", 0.0)
    monkeypatch.setattr(session_module, "_global_rate_limit_until", 0.0)


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
        lambda *_args, **_kwargs: (429, {"retry-after": "3"}, b'{"detail": "slow"}'),
    )
    monkeypatch.setattr(
        "alpha.api.session.wait_seconds", lambda seconds, *_args: waits.append(seconds)
    )

    with pytest.raises(BrainRateLimitError) as exc_info:
        client.request("GET", "https://example.test", retries=2)

    assert exc_info.value.retry_after == 6
    assert waits == [6.0]


def test_rate_limit_deadline_is_shared_across_clients(monkeypatch) -> None:
    clock = [100.0]
    condition_waits: list[float] = []

    class FakeCondition:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def wait(self, timeout: float | None = None) -> None:
            assert timeout is not None
            condition_waits.append(timeout)
            clock[0] += timeout

        def notify_all(self) -> None:
            return None

    rate_limited_client = BrainClient("user@example.com", "secret")
    waiting_client = BrainClient("user@example.com", "secret")
    responses = iter(
        [
            (429, {"Retry-After": "3"}, b"limited"),
            (200, {}, b"ok"),
        ]
    )

    class FakeBackend:
        def request(self, **_kwargs: Any):
            return next(responses)

    rate_limited_client._http_backend = FakeBackend()  # type: ignore[assignment]
    waiting_client._http_backend = FakeBackend()  # type: ignore[assignment]
    monkeypatch.setattr(session_module, "_request_throttle_condition", FakeCondition())
    monkeypatch.setattr(session_module, "_global_last_request_at", 0.0)
    monkeypatch.setattr(session_module, "_global_rate_limit_until", 0.0)
    monkeypatch.setattr(session_module.time, "monotonic", lambda: clock[0])

    with pytest.raises(BrainRateLimitError):
        rate_limited_client.request("GET", "https://example.test", retries=1)
    status, _, content = waiting_client.raw_request("GET", "https://example.test")

    assert (status, content) == (200, b"ok")
    assert condition_waits == [6.0]
    assert clock[0] == 106.0


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


def test_request_does_not_wait_after_final_server_error(monkeypatch) -> None:
    client = BrainClient("user@example.com", "secret")
    waits: list[str] = []
    monkeypatch.setattr(
        client,
        "raw_request",
        lambda *_args, **_kwargs: (503, {}, b"busy"),
    )
    monkeypatch.setattr(
        "alpha.api.session.wait_seconds", lambda _seconds, reason: waits.append(reason)
    )

    with pytest.raises(BrainHTTPError) as exc_info:
        client.request("GET", "https://example.test", expected={200}, retries=2)

    assert exc_info.value.status == 503
    assert waits == ["server error 503"]


@pytest.mark.parametrize(
    ("status", "headers"),
    [
        (429, {"Retry-After": "30"}),
        (503, {}),
    ],
)
def test_request_retry_wait_stops_at_request_deadline(
    monkeypatch,
    status: int,
    headers: dict[str, str],
) -> None:
    clock = [100.0]
    client = BrainClient(
        "user@example.com",
        "secret",
        request_deadline=101.0,
    )
    monkeypatch.setattr(
        client,
        "raw_request",
        lambda *_args, **_kwargs: (status, headers, b"busy"),
    )
    monkeypatch.setattr(session_module.time, "monotonic", lambda: clock[0])

    def fake_wait(
        _seconds: float,
        _reason: str,
        *,
        should_abort,
    ) -> None:
        assert should_abort() is False
        clock[0] = 101.0
        assert should_abort() is True
        raise BrainStopRequested("request deadline reached")

    monkeypatch.setattr("alpha.api.session.wait_seconds", fake_wait)

    with pytest.raises(BrainStopRequested, match="deadline reached"):
        client.request("GET", "https://example.test", retries=2)


@pytest.mark.parametrize(
    ("status", "headers"),
    [
        (429, {"Retry-After": "30"}),
        (503, {}),
    ],
)
def test_request_retry_wait_stops_when_worker_stop_is_requested(
    monkeypatch,
    status: int,
    headers: dict[str, str],
) -> None:
    stopped = False
    client = BrainClient(
        "user@example.com",
        "secret",
        request_abort=lambda: stopped,
    )
    monkeypatch.setattr(
        client,
        "raw_request",
        lambda *_args, **_kwargs: (status, headers, b"busy"),
    )

    def fake_wait(
        _seconds: float,
        _reason: str,
        *,
        should_abort,
    ) -> None:
        nonlocal stopped
        assert should_abort() is False
        stopped = True
        assert should_abort() is True
        raise BrainStopRequested("worker stop requested")

    monkeypatch.setattr("alpha.api.session.wait_seconds", fake_wait)

    with pytest.raises(BrainStopRequested, match="worker stop requested"):
        client.request("GET", "https://example.test", retries=2)


def test_request_preserves_unexpected_http_status(monkeypatch) -> None:
    client = BrainClient("user@example.com", "secret")
    monkeypatch.setattr(
        client,
        "raw_request",
        lambda *_args, **_kwargs: (404, {}, b'{"detail": "missing"}'),
    )

    with pytest.raises(BrainHTTPError) as exc_info:
        client.request("GET", "https://example.test", expected={200}, retries=1)

    assert exc_info.value.status == 404
    assert exc_info.value.is_permanent_client_error is True


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


def test_raw_request_caps_transport_timeout_to_request_deadline(monkeypatch) -> None:
    client = BrainClient("user@example.com", "secret", request_deadline=105.0)
    captured: dict[str, Any] = {}

    class FakeBackend:
        def request(self, **kwargs: Any):
            captured.update(kwargs)
            return 200, {}, b"ok"

    client._http_backend = FakeBackend()  # type: ignore[assignment]
    monkeypatch.setattr(session_module.time, "monotonic", lambda: 100.0)

    client.raw_request("GET", "https://example.test")

    assert captured["timeout"] == 5.0


def test_raw_request_stops_before_expired_request_deadline(monkeypatch) -> None:
    client = BrainClient("user@example.com", "secret", request_deadline=100.0)
    monkeypatch.setattr(session_module.time, "monotonic", lambda: 100.0)

    with pytest.raises(BrainStopRequested, match="deadline reached"):
        client.raw_request("GET", "https://example.test")


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
        BrainRateLimitError("rate", retry_after=12),
    ],
)
def test_retry_operation_preserves_terminal_api_error_type(error: BrainAPIError) -> None:
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise error

    with pytest.raises(BrainAPIError) as exc_info:
        retry_operation("operation", 4, operation, retry_wait_seconds=0)

    assert attempts == 1
    assert exc_info.value is error


def test_retry_operation_wraps_exhausted_generic_exception(monkeypatch) -> None:
    monkeypatch.setattr("alpha.api.retry.wait_seconds", lambda *_args, **_kwargs: None)

    def operation() -> None:
        raise ValueError("boom")

    with pytest.raises(BrainAPIError, match="failed after 3 attempts"):
        retry_operation("operation", 3, operation, retry_wait_seconds=0)


def test_retry_operation_preserves_http_error_status() -> None:
    error = BrainHTTPError("missing", status=404)

    def operation() -> None:
        raise error

    with pytest.raises(BrainHTTPError) as exc_info:
        retry_operation("operation", 3, operation, retry_wait_seconds=0)

    assert exc_info.value is error
    assert exc_info.value.status == 404


def test_retry_operation_retries_transient_api_errors(monkeypatch) -> None:
    attempts = 0
    waits: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise BrainTransientError("network unavailable")
        return "ok"

    monkeypatch.setattr(
        "alpha.api.retry.wait_seconds", lambda seconds, *_args: waits.append(seconds)
    )

    assert retry_operation("operation", 3, operation, retry_wait_seconds=0.25) == "ok"
    assert attempts == 3
    assert waits == [0.25, 0.25]


def test_retry_operation_honors_abort_before_first_attempt() -> None:
    with pytest.raises(BrainStopRequested, match="aborted"):
        retry_operation("operation", 2, lambda: None, should_abort=lambda: True)


def test_retry_operation_preserves_stop_requested_from_operation() -> None:
    def operation() -> None:
        raise BrainStopRequested("polling stopped")

    with pytest.raises(BrainStopRequested, match="polling stopped"):
        retry_operation("operation", 2, operation)


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


def test_login_with_retry_preserves_deadline_stop() -> None:
    class FakeClient:
        def login(self) -> None:
            raise BrainStopRequested("deadline reached")

    with pytest.raises(BrainStopRequested, match="deadline reached"):
        login_with_retry(FakeClient(), 2)  # type: ignore[arg-type]
