"""Bootstrap API client ownership tests."""

from __future__ import annotations

import pytest

import alpha.app.bootstrap_clients as bootstrap_clients
from alpha.models.runtime_options import ApiClientOptions


def test_create_and_login_client_closes_client_when_login_fails(monkeypatch) -> None:
    closed: list[bool] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def close(self) -> None:
            closed.append(True)

    def _fail_login(_client, _retries) -> None:
        raise RuntimeError("login failed")

    monkeypatch.setattr(bootstrap_clients, "BrainClient", FakeClient)
    monkeypatch.setattr(bootstrap_clients, "login_with_retry", _fail_login)
    options = ApiClientOptions(
        min_request_interval=0.0,
        rate_limit_max_retries=1,
        login_retries=1,
    )

    with pytest.raises(RuntimeError, match="login failed"):
        bootstrap_clients.create_and_login_client(
            "user@example.com",
            "secret",
            options,
        )

    assert closed == [True]


def test_create_and_login_client_preserves_original_error_when_close_fails(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        def close(self) -> None:
            raise OSError("close failed")

    def _fail_login(_client, _retries) -> None:
        raise RuntimeError("login failed")

    monkeypatch.setattr(bootstrap_clients, "BrainClient", FakeClient)
    monkeypatch.setattr(bootstrap_clients, "login_with_retry", _fail_login)
    options = ApiClientOptions(
        min_request_interval=0.0,
        rate_limit_max_retries=1,
        login_retries=1,
    )

    with pytest.raises(RuntimeError, match="login failed"):
        bootstrap_clients.create_and_login_client(
            "user@example.com",
            "secret",
            options,
        )
