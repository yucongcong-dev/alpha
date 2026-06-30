"""API client pagination and logging tests."""

from __future__ import annotations

import logging

from alpha.api.client import BrainClient


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
