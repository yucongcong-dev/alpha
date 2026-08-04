"""Bootstrap API client ownership tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import alpha.app.bootstrap_clients as bootstrap_clients


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
    services = SimpleNamespace(
        get_runtime_config=lambda: SimpleNamespace(http=SimpleNamespace(backend="urllib")),
        login_with_retry=_fail_login,
    )
    args = SimpleNamespace(
        min_request_interval=0.0,
        rate_limit_max_retries=1,
        login_retries=1,
    )

    with pytest.raises(RuntimeError, match="login failed"):
        bootstrap_clients.create_and_login_client(
            "user@example.com",
            "secret",
            args,
            services=services,
        )

    assert closed == [True]
