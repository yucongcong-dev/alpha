"""Dataset template and blacklist file lifecycle tests."""

from __future__ import annotations

import json

from alpha.generators import templates as template_module
from alpha.generators.templates import ensure_dataset_template_library, load_template_library
from alpha.io.output import auto_update_blacklist, ensure_template_blacklist_file
from alpha.models.base import FieldTestResult


def test_ensure_dataset_template_library_copies_base_when_missing(monkeypatch, tmp_path) -> None:
    """Missing dataset-specific template files should be generated from the base library."""
    base = tmp_path / "worldquant_template_library.json"
    target = tmp_path / "worldquant_template_library_custom_ds.json"
    base.write_text(
        json.dumps(
            {
                "_comment": "base",
                "default": [
                    {
                        "name": "rank_backfill",
                        "expression": "rank(ts_backfill({field}, {backfill_window}))",
                        "priority": 123,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(template_module, "_BUILTIN_TEMPLATE_LIBRARY_FILE", str(base))

    resolved = ensure_dataset_template_library(str(target), "custom_ds")

    assert resolved == str(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["_dataset_id"] == "custom_ds"
    assert payload["default"][0]["name"] == "rank_backfill"
    assert payload["default"][0]["priority"] == 123

    library = load_template_library(str(target))
    assert library["default"][0]["priority"] == 123


def test_ensure_dataset_template_library_preserves_existing(monkeypatch, tmp_path) -> None:
    """Existing dataset template files should not be overwritten by the base library."""
    base = tmp_path / "worldquant_template_library.json"
    target = tmp_path / "worldquant_template_library_custom_ds.json"
    base.write_text(
        json.dumps({"default": [{"name": "base", "expression": "rank({field})"}]}),
        encoding="utf-8",
    )
    target.write_text(
        json.dumps({"default": [{"name": "custom", "expression": "zscore({field})"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(template_module, "_BUILTIN_TEMPLATE_LIBRARY_FILE", str(base))

    ensure_dataset_template_library(str(target), "custom_ds")

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["default"][0]["name"] == "custom"


def test_ensure_dataset_template_library_fills_missing_priorities(
    monkeypatch, tmp_path
) -> None:
    """Missing priorities should be filled by file order without overwriting manual values."""
    base = tmp_path / "worldquant_template_library.json"
    target = tmp_path / "worldquant_template_library_custom_ds.json"
    base.write_text(json.dumps({"default": []}), encoding="utf-8")
    target.write_text(
        json.dumps(
            {
                "default": [
                    {"name": "first", "expression": "rank({field})"},
                    {"name": "manual", "expression": "zscore({field})", "priority": 999},
                    {"name": "third", "expression": "scale({field})"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(template_module, "_BUILTIN_TEMPLATE_LIBRARY_FILE", str(base))

    ensure_dataset_template_library(str(target), "custom_ds")

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert [item["priority"] for item in payload["default"]] == [1000, 999, 998]


def test_ensure_dataset_template_library_does_not_mutate_base_template(
    monkeypatch, tmp_path
) -> None:
    """The tracked base template library should not be rewritten by priority filling."""
    base = tmp_path / "worldquant_template_library.json"
    base.write_text(
        json.dumps({"default": [{"name": "base", "expression": "rank({field})"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(template_module, "_BUILTIN_TEMPLATE_LIBRARY_FILE", str(base))

    ensure_dataset_template_library(str(base), "custom_ds")

    payload = json.loads(base.read_text(encoding="utf-8"))
    assert "priority" not in payload["default"][0]


def test_ensure_template_blacklist_file_creates_empty_dataset_file(tmp_path) -> None:
    """Missing dataset blacklist files should be created with the expected schema."""
    path = ensure_template_blacklist_file("custom_ds", data_dir=str(tmp_path))

    payload = json.loads((tmp_path / "template_blacklist_custom_ds.json").read_text())
    assert path == str(tmp_path / "template_blacklist_custom_ds.json")
    assert payload["dataset_id"] == "custom_ds"
    assert payload["blacklisted_templates"] == []
    assert payload["auto_avoid_rules"] == []


def test_auto_update_blacklist_appends_low_quality_template_once(tmp_path) -> None:
    """Low-quality templates should be appended to the dataset blacklist without duplicates."""
    results = [
        FieldTestResult(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="weak_template",
            expression="rank(sales)",
            submittable=False,
            failed_checks=[
                {"name": "LOW_SHARPE", "value": 0.1},
                {"name": "LOW_FITNESS", "value": 0.2},
            ],
        ),
        FieldTestResult(
            field_id="assets",
            field_type="MATRIX",
            field_name="assets",
            template_name="weak_template",
            expression="rank(assets)",
            submittable=False,
            failed_checks=[
                {"name": "LOW_SHARPE", "value": 0.2},
                {"name": "LOW_FITNESS", "value": 0.3},
            ],
        ),
    ]

    auto_update_blacklist(results, "custom_ds", data_dir=str(tmp_path))
    auto_update_blacklist(results, "custom_ds", data_dir=str(tmp_path))

    payload = json.loads((tmp_path / "template_blacklist_custom_ds.json").read_text())
    entries = payload["blacklisted_templates"]
    assert [entry["name"] for entry in entries] == ["weak_template"]
    assert entries[0]["fields_tested"] == ["sales", "assets"]
