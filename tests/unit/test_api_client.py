"""API client pagination and logging tests."""

from __future__ import annotations

import logging

import pytest

import alpha.api.client as client_module
from alpha.api.client import BrainClient, WorkerClientFactory
from alpha.exceptions import BrainHTTPError
from alpha.models.runtime_options import ApiClientOptions


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


def test_fetch_dataset_fields_reduces_page_size_after_transient_failure(monkeypatch) -> None:
    client = BrainClient("user@example.com", "password")
    requested_page_sizes: list[int] = []

    def fake_fetch_page(
        _dataset_id: str,
        limit: int,
        _offset: int,
        **_kwargs: object,
    ) -> dict[str, object]:
        requested_page_sizes.append(limit)
        if limit == 50:
            raise BrainHTTPError("field page failed", status=500)
        return {"results": [{"id": "a"}], "count": 1}

    monkeypatch.setattr(client, "_fetch_dataset_fields_page", fake_fetch_page)

    rows = client.fetch_dataset_fields(
        "analyst4",
        limit=0,
        offset=950,
        page_size=50,
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
    )

    assert [row["id"] for row in rows] == ["a"]
    assert requested_page_sizes == [50, 20]
