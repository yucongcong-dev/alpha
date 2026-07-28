"""Low-level API transport, timing, and fallback query tests."""

from __future__ import annotations

from email.message import Message
from io import BytesIO
import sys
from typing import Any
from urllib.error import HTTPError, URLError

import pytest

from alpha.api.alphas import BrainAlphasMixin
from alpha.api.fields import BrainFieldsMixin
from alpha.api.http_backend import HttpxHttpBackend, UrllibHttpBackend, response_header
from alpha.api.timing import (
    doubled_retry_after,
    extract_retry_after,
    polling_retry_after,
    wait_seconds,
)
from alpha.exceptions import BrainAPIError, BrainStopRequested


class _Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return self.body


class _Opener:
    def __init__(self, result: Any) -> None:
        self.result = result

    def open(self, *_args: Any, **_kwargs: Any):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_urllib_backend_returns_success_response() -> None:
    backend = UrllibHttpBackend()
    backend._opener = _Opener(_Response(200, b'{"ok": true}'))  # type: ignore[assignment]

    status, headers, body = backend.request("GET", "https://example.test")

    assert status == 200
    assert headers["Content-Type"] == "application/json"
    assert body == b'{"ok": true}'


def test_urllib_backend_preserves_http_error_response() -> None:
    headers = Message()
    headers["Retry-After"] = "5"
    error = HTTPError("https://example.test", 429, "limited", headers, BytesIO(b"limited"))
    backend = UrllibHttpBackend()
    backend._opener = _Opener(error)  # type: ignore[assignment]

    status, response_headers, body = backend.request("GET", "https://example.test")

    assert status == 429
    assert response_headers["Retry-After"] == "5"
    assert body == b"limited"


def test_urllib_backend_wraps_network_errors() -> None:
    backend = UrllibHttpBackend()
    backend._opener = _Opener(URLError("offline"))  # type: ignore[assignment]

    with pytest.raises(BrainAPIError, match="offline"):
        backend.request("GET", "https://example.test")


def test_httpx_backend_explains_missing_optional_dependency(monkeypatch) -> None:
    backend = HttpxHttpBackend()
    monkeypatch.setitem(sys.modules, "httpx", None)

    with pytest.raises(ImportError, match=r"pip install -e '\.\[httpx\]'"):
        backend._get_client()


def test_httpx_backend_wraps_client_errors() -> None:
    class FakeCookies:
        jar = None

        def set(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    class FailingClient:
        cookies = FakeCookies()

        def request(self, **_kwargs: Any) -> None:
            raise RuntimeError("connection reset")

    backend = HttpxHttpBackend()
    backend._client = FailingClient()

    with pytest.raises(BrainAPIError, match="connection reset"):
        backend.request("POST", "https://example.test", data=b"{}")


def test_response_header_matches_names_case_insensitively() -> None:
    headers = {"location": "/simulations/123", "RETRY-after": "4"}

    assert response_header(headers, "Location") == "/simulations/123"
    assert response_header(headers, "Retry-After") == "4"
    assert response_header(headers, "Missing") is None


@pytest.mark.parametrize(
    ("headers", "default", "expected"),
    [
        ({"Retry-After": "2.5"}, 7.0, 2.5),
        ({"retry-after": "3.5"}, 7.0, 3.5),
        ({"Retry-After": "invalid"}, 7.0, 7.0),
        ({}, 7.0, 7.0),
    ],
)
def test_extract_retry_after(headers: dict[str, str], default: float, expected: float) -> None:
    assert extract_retry_after(headers, default) == expected


def test_retry_after_helpers_apply_backoff_and_buffer() -> None:
    headers = {"Retry-After": "4"}

    assert doubled_retry_after(headers, default=2) == 8
    assert polling_retry_after(headers, default=2, buffer_seconds=1.5) == 5.5
    assert polling_retry_after(headers, default=2, buffer_seconds=-3) == 4


def test_wait_seconds_skips_non_positive_values(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("alpha.api.timing.time.sleep", sleeps.append)

    wait_seconds(-1, "negative")
    wait_seconds(0.2, "positive", verbose=False)

    assert sleeps == [0.2]


def test_wait_seconds_aborts_before_sleep() -> None:
    with pytest.raises(BrainStopRequested, match="stop was requested"):
        wait_seconds(30, "simulation pending", should_abort=lambda: True)


class _FieldClient(BrainFieldsMixin):
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.params: list[dict[str, object]] = []

    def request(self, *_args: Any, **kwargs: Any):
        self.params.append(kwargs["params"])
        if len(self.params) <= self.failures:
            raise BrainAPIError("unsupported query")
        return 200, {}, b'{"results": [{"id": "field1"}]}'


def test_field_query_falls_back_to_supported_parameter_shape() -> None:
    client = _FieldClient(failures=2)

    payload = client._fetch_dataset_fields_page(
        "model51",
        10,
        0,
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
    )

    assert payload["results"] == [{"id": "field1"}]
    assert len(client.params) == 3
    assert "delay" not in client.params[-1]


def test_field_query_reports_failure_after_all_parameter_shapes() -> None:
    client = _FieldClient(failures=5)

    with pytest.raises(BrainAPIError, match="Unable to fetch dataset fields for model51"):
        client._fetch_dataset_fields_page(
            "model51",
            10,
            0,
            region="USA",
            universe="TOP3000",
            instrument_type="EQUITY",
            delay=1,
        )


class _AlphaClient(BrainAlphasMixin):
    def request(self, *_args: Any, **_kwargs: Any):
        return 200, {}, b'{"id": "alpha1", "status": "UNSUBMITTED"}'


def test_alpha_detail_decodes_response_payload() -> None:
    assert _AlphaClient().get_alpha_detail("alpha1") == {
        "id": "alpha1",
        "status": "UNSUBMITTED",
    }
