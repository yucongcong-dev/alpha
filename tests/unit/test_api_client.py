"""API client pagination and logging tests."""

from __future__ import annotations

from http.cookiejar import Cookie, CookieJar
import logging

import pytest

import alpha.api.client as client_module
from alpha.api.client import BrainClient, WorkerClientFactory
from alpha.api.http_backend import (
    HttpxHttpBackend,
    UrllibHttpBackend,
    create_http_backend,
)
from alpha.models.runtime_options import ApiClientOptions


def test_create_http_backend_accepts_supported_names() -> None:
    assert isinstance(create_http_backend(""), UrllibHttpBackend)
    assert isinstance(create_http_backend(" urllib "), UrllibHttpBackend)
    assert isinstance(create_http_backend("HTTPX"), HttpxHttpBackend)


def test_create_http_backend_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unsupported HTTP backend 'httpxx'"):
        create_http_backend("httpxx")


def test_worker_client_factory_closes_client_when_login_fails(monkeypatch) -> None:
    closed: list[bool] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def close(self) -> None:
            closed.append(True)

    def _fail_login(_client, _retries) -> None:
        raise RuntimeError("worker login failed")

    monkeypatch.setattr(client_module, "BrainClient", FakeClient)
    monkeypatch.setattr(client_module, "login_with_retry", _fail_login)
    factory = WorkerClientFactory(
        ApiClientOptions(login_retries=1),
        "user@example.com",
        "secret",
    )

    with pytest.raises(RuntimeError, match="worker login failed"):
        factory.get_client()

    assert closed == [True]


def _make_cookie(name: str, value: str, *, domain: str = "api.worldquantbrain.com") -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=bool(domain),
        domain_initial_dot=domain.startswith("."),
        path="/",
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


def test_fetch_dataset_fields_logs_progress_with_total(monkeypatch, caplog) -> None:
    """Pagination should emit cache fetch progress while building the full field cache."""
    client = BrainClient("user@example.com", "password")
    pages = [
        {"results": [{"id": "a"}, {"id": "b"}], "count": 3},
        {"results": [{"id": "c"}], "count": 3},
    ]

    def fake_fetch_page(
        dataset_id: str,
        limit: int,
        offset: int,
        *,
        region: str,
        universe: str,
        instrument_type: str,
        delay: int,
    ) -> dict[str, object]:
        return pages.pop(0)

    monkeypatch.setattr(client, "_fetch_dataset_fields_page", fake_fetch_page)

    with caplog.at_level(logging.INFO):
        rows = client.fetch_dataset_fields(
            "fundamental6",
            limit=0,
            offset=0,
            page_size=2,
            region="USA",
            universe="TOP3000",
            instrument_type="EQUITY",
            delay=1,
        )

    assert [row["id"] for row in rows] == ["a", "b", "c"]
    assert "fetched 2/3 fields" in caplog.text
    assert "fetched 3/3 fields" in caplog.text


def test_httpx_backend_syncs_cookies_in_both_directions() -> None:
    """The optional httpx backend should preserve authenticated session cookies."""

    class _FakeCookies:
        def __init__(self) -> None:
            self.jar = CookieJar()

        def set(self, name: str, value: str, *, domain: str | None = None, path: str = "/") -> None:
            self.jar.set_cookie(
                _make_cookie(name, value, domain=domain or "api.worldquantbrain.com")
            )

    class _FakeResponse:
        def __init__(self) -> None:
            self.status_code = 200
            self.headers = {"content-type": "application/json"}
            self.content = b"{}"

    class _FakeClient:
        def __init__(self) -> None:
            self.cookies = _FakeCookies()

        def request(self, **_kwargs):
            self.cookies.set("session", "newer")
            return _FakeResponse()

    backend = HttpxHttpBackend()
    backend._client = _FakeClient()
    jar = CookieJar()
    jar.set_cookie(_make_cookie("session", "old"))

    backend.load_cookies(jar)
    assert any(
        cookie.name == "session" and cookie.value == "old" for cookie in backend._client.cookies.jar
    )

    status, _headers, body = backend.request("GET", "https://api.worldquantbrain.com/ping")

    assert status == 200
    assert body == b"{}"
    assert any(cookie.name == "session" and cookie.value == "newer" for cookie in backend._cookies)
