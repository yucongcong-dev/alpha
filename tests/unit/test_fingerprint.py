"""Stable identity serialization tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from alpha.generators.fingerprint import FINGERPRINT_HEX_LENGTH, stable_fingerprint
from alpha.models.domain import (
    FieldTestResult,
    SettingsVariant,
    TemplateField,
    TemplateLibraryItem,
)


def test_fingerprint_is_order_independent_and_has_persisted_width() -> None:
    first = stable_fingerprint({"region": "USA", "delay": 1})
    second = stable_fingerprint({"delay": 1, "region": "USA"})

    assert first == second
    assert len(first) == FINGERPRINT_HEX_LENGTH == 16


def test_fingerprint_serializes_domain_models() -> None:
    objects = [
        FieldTestResult("field", "MATRIX", "field", "template"),
        SettingsVariant(decay=4),
        TemplateField("field", "field", "MATRIX"),
        TemplateLibraryItem("template", "rank(field)", priority=100),
    ]

    fingerprints = [stable_fingerprint(obj) for obj in objects]

    assert len(set(fingerprints)) == len(objects)


def test_fingerprint_supports_to_dict_and_generic_dataclass() -> None:
    class _Convertible:
        def to_dict(self) -> dict[str, int]:
            return {"value": 1}

    @dataclass
    class _Record:
        value: int

    assert stable_fingerprint(_Convertible()) == stable_fingerprint({"value": 1})
    assert stable_fingerprint(_Record(1)) == stable_fingerprint({"value": 1})


def test_fingerprint_rejects_unsupported_objects() -> None:
    with pytest.raises(TypeError, match="is not JSON serializable"):
        stable_fingerprint(object())
