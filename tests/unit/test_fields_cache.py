"""Field cache validation and fetch normalization tests."""

from __future__ import annotations

import json
import time

from alpha.generators.fields import (
    fetch_fields_with_cache,
    load_fields_cache,
    save_fields_cache,
)
from alpha.models.domain import TemplateField
from alpha.models.runtime_options import FieldFetchOptions


def _options() -> FieldFetchOptions:
    return FieldFetchOptions(
        dataset_id="model16",
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
        page_size=50,
    )


def _load(path, **overrides):
    values = {
        "dataset_id": "model16",
        "region": "USA",
        "universe": "TOP3000",
        "instrument_type": "EQUITY",
        "delay": 1,
    }
    values.update(overrides)
    return load_fields_cache(str(path), **values)


def test_cache_round_trip_returns_domain_fields(tmp_path) -> None:
    cache = tmp_path / "cache.json"
    field = TemplateField(
        field_id="f1",
        field_name="Field 1",
        field_type="MATRIX",
        metadata={"id": "f1", "name": "Field 1", "type": "MATRIX"},
    )

    save_fields_cache(
        str(cache),
        dataset_id="model16",
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
        fields=[field],
    )

    assert _load(cache) == [field]


def test_cache_rejects_expired_or_mismatched_scope(tmp_path) -> None:
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps(
            {
                "cache_key": {
                    "dataset_id": "model16",
                    "region": "USA",
                    "universe": "TOP3000",
                    "instrument_type": "EQUITY",
                    "delay": 1,
                },
                "cached_at": time.time() - 7200,
                "fields": [{"id": "f1", "type": "MATRIX"}],
            }
        ),
        encoding="utf-8",
    )

    assert _load(cache, cache_ttl_hours=1) == []
    assert _load(cache, universe="TOP1000", cache_ttl_hours=0) == []


def test_cache_ignores_malformed_and_duplicate_rows(tmp_path) -> None:
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps(
            {
                "cache_key": {
                    "dataset_id": "model16",
                    "region": "USA",
                    "universe": "TOP3000",
                    "instrument_type": "EQUITY",
                    "delay": 1,
                },
                "cached_at": time.time(),
                "fields": [
                    {"id": "f1", "type": "MATRIX"},
                    {"id": "f1", "type": "VECTOR"},
                    {"type": "MATRIX"},
                    "invalid",
                ],
            }
        ),
        encoding="utf-8",
    )

    fields = _load(cache)

    assert len(fields) == 1
    assert fields[0].field_id == "f1"
    assert fields[0].field_type == "MATRIX"


def test_invalid_nonempty_cache_falls_back_to_api_and_deduplicates(tmp_path) -> None:
    calls: list[dict[str, object]] = []

    class Client:
        def fetch_dataset_fields(self, dataset_id, **kwargs):
            calls.append({"dataset_id": dataset_id, **kwargs})
            return [
                {"id": "f1", "type": "MATRIX"},
                {"id": "f1", "type": "MATRIX"},
                {"name": "f2", "fieldType": "vector"},
            ]

    fields = fetch_fields_with_cache(
        Client(),
        _options(),
        str(tmp_path / "cache.json"),
        cached_fields=[{"type": "MATRIX"}],  # type: ignore[list-item]
    )

    assert [field.field_id for field in fields] == ["f1", "f2"]
    assert calls[0]["limit"] == 0
    assert calls[0]["page_size"] == 50
    assert [field.field_id for field in _load(tmp_path / "cache.json")] == ["f1", "f2"]


def test_valid_cache_avoids_api_call(tmp_path) -> None:
    class UnexpectedClient:
        def fetch_dataset_fields(self, *_args, **_kwargs):
            raise AssertionError("valid cache should avoid API call")

    cached = TemplateField(
        field_id="f1",
        field_name="f1",
        field_type="MATRIX",
        metadata={"id": "f1", "type": "MATRIX"},
    )

    assert fetch_fields_with_cache(
        UnexpectedClient(),
        _options(),
        str(tmp_path / "cache.json"),
        cached_fields=[cached],
    ) == [cached]
