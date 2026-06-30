"""Dataset template and blacklist file lifecycle tests."""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

from alpha.core.executor import build_pending_templates_for_field
from alpha.core.scheduler import handle_completed_future
from alpha.generators import templates as template_module
from alpha.generators.expressions import _BLACKLIST_CACHE, _is_blacklisted_template
from alpha.generators.templates import ensure_dataset_template_library, load_template_library
from alpha.io.output import (
    _BLACKLIST_PATH_CACHE,
    auto_update_blacklist,
    ensure_template_blacklist_file,
)
from alpha.models.base import FieldTestResult, FutureCompletionContext, TemplateBuildContext


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


def test_load_template_library_preserves_optional_metadata(tmp_path) -> None:
    template_file = tmp_path / "library.json"
    template_file.write_text(
        json.dumps(
            {
                "default": [
                    {
                        "name": "custom",
                        "expression": "rank({field})",
                        "priority": 100,
                        "family": "custom_family",
                        "layer": "ratio",
                        "stage": "first_order",
                        "requires_partner_field": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    library = load_template_library(str(template_file))

    assert library["default"][0]["family"] == "custom_family"
    assert library["default"][0]["layer"] == "ratio"
    assert library["default"][0]["stage"] == "first_order"
    assert library["default"][0]["requires_partner_field"] is False


def test_load_template_library_infers_stage_from_layer(tmp_path) -> None:
    template_file = tmp_path / "library.json"
    template_file.write_text(
        json.dumps(
            {
                "default": [
                    {
                        "name": "group_custom",
                        "expression": "group_rank({field}, subindustry)",
                        "priority": 100,
                        "layer": "group",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    library = load_template_library(str(template_file))

    assert library["default"][0]["stage"] == "group_second_order"


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

    blacklist_file = tmp_path / "blacklists" / "custom_ds" / "blacklist.json"
    payload = json.loads(blacklist_file.read_text())
    assert path == str(blacklist_file)
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
            template_family="group_vol_scaled_delta",
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
            template_family="group_vol_scaled_delta",
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

    payload = json.loads((tmp_path / "blacklists" / "custom_ds" / "blacklist.json").read_text())
    entries = payload["blacklisted_templates"]
    assert [entry["name"] for entry in entries] == ["weak_template"]
    assert entries[0]["template_family"] == "group_vol_scaled_delta"
    assert entries[0]["fields_tested"] == ["sales", "assets"]


def test_auto_update_blacklist_is_visible_to_same_process(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    _BLACKLIST_CACHE.clear()

    assert not _is_blacklisted_template("weak_template", "rank(close)", dataset_id="custom_ds")

    results = [
        FieldTestResult(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="weak_template",
            template_family="group_vol_scaled_delta",
            template_stage="group_second_order",
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
            template_family="group_vol_scaled_delta",
            template_stage="group_second_order",
            expression="rank(assets)",
            submittable=False,
            failed_checks=[
                {"name": "LOW_SHARPE", "value": 0.2},
                {"name": "LOW_FITNESS", "value": 0.3},
            ],
        ),
    ]

    auto_update_blacklist(results, "custom_ds", data_dir=str(data_dir))

    assert _is_blacklisted_template(
        "weak_template",
        "group_rank(ts_zscore(close, 60), subindustry)",
        template_metadata={
            "stage": "group_second_order",
            "family": "group_vol_scaled_delta",
        },
        dataset_id="custom_ds",
    )


def test_scheduler_dump_results_shrinks_next_template_queue(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    results_path = tmp_path / "results.json"
    monkeypatch.chdir(tmp_path)
    _BLACKLIST_CACHE.clear()
    _BLACKLIST_PATH_CACHE.clear()
    monkeypatch.setattr("alpha.io.output.DATA_DIR", data_dir)
    monkeypatch.setattr(
        "alpha.core.executor.build_setting_variants",
        lambda *args, **kwargs: [{"neutralization": "SUBINDUSTRY", "truncation": 0.08}],
    )

    args = Namespace(
        output=str(results_path),
        dataset_id="custom_ds",
        auto_update_blacklist=True,
        template_disable_after=0,
        disable_legacy_after=0,
        max_templates_per_field=1000,
        max_templates_per_family=1000,
        legacy_similarity_penalty=0,
    )
    completion_ctx = FutureCompletionContext(
        args=args,
        settings_fingerprint="settings_fp",
        template_library_fingerprint="tpl_fp",
        run_config={"mode": "test"},
    )
    template_library = {
        "default": [
            {
                "name": "weak_template",
                "expression": "rank(ts_backfill({field}, {backfill_window}))",
                "priority": 9999,
                "family": "legacy_level",
                "stage": "first_order",
            }
        ]
    }
    build_ctx = TemplateBuildContext(
        args=args,
        all_fields=[{"id": "sales", "type": "MATRIX"}],
        template_library=template_library,
        include_templates={"weak_template"},
        use_dataset_heuristics=False,
        expression_policy=None,
    )

    before_pending, before_disabled, before_count = build_pending_templates_for_field(
        build_ctx,
        {"id": "sales", "type": "MATRIX"},
        template_stats={},
        attempted_keys=set(),
        prior_results=[],
    )
    assert before_count >= 1
    assert len(before_pending) == 1
    assert before_disabled == 0

    existing_results = [
        FieldTestResult(
            field_id="field_a",
            field_type="MATRIX",
            field_name="field_a",
            template_name="weak_template",
            template_family="legacy_level",
            template_stage="first_order",
            expression="rank(ts_backfill(field_a, 240))",
            status="simulated",
            submittable=False,
            failed_checks=[
                {"name": "LOW_SHARPE", "value": 0.1},
                {"name": "LOW_FITNESS", "value": 0.2},
            ],
        )
    ]

    class _DoneFuture:
        def result(self) -> FieldTestResult:
            return FieldTestResult(
                field_id="field_b",
                field_type="MATRIX",
                field_name="field_b",
                template_name="weak_template",
                template_family="legacy_level",
                template_stage="first_order",
                expression="rank(ts_backfill(field_b, 240))",
                status="simulated",
                submittable=False,
                failed_checks=[
                    {"name": "LOW_SHARPE", "value": 0.1},
                    {"name": "LOW_FITNESS", "value": 0.2},
                ],
            )

    future = _DoneFuture()
    handle_completed_future(
        future,
        completion_ctx=completion_ctx,
        results=existing_results,
        attempted_keys=set(),
        template_stats={},
        pending_contexts={
            future: {
                "field_id": "field_b",
                "field_name": "field_b",
                "field_type": "MATRIX",
                "template_name": "weak_template",
                "template_family": "legacy_level",
                "template_stage": "first_order",
                "expression": "rank(ts_backfill(field_b, 240))",
                "settings_fingerprint": "variant_fp",
            }
        },
    )

    after_pending, after_disabled, after_count = build_pending_templates_for_field(
        build_ctx,
        {"id": "sales", "type": "MATRIX"},
        template_stats={},
        attempted_keys=set(),
        prior_results=[],
    )
    assert after_count >= 1
    assert after_pending == []
    assert after_disabled == 0
    assert _is_blacklisted_template(
        "weak_template",
        "rank(ts_backfill(sales, 240))",
        template_metadata={"family": "legacy_level", "stage": "first_order"},
        dataset_id="custom_ds",
    )


def test_fundamental6_template_library_has_family_and_layer_metadata() -> None:
    """Common dataset template library entries should carry explicit family/layer metadata."""
    template_file = Path(__file__).resolve().parents[2] / "data" / "templates" / "fundamental6" / "library.json"
    payload = json.loads(template_file.read_text(encoding="utf-8"))

    missing = []
    for section, items in payload.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or "name" not in item or "expression" not in item:
                continue
            if "family" not in item or "layer" not in item:
                missing.append((section, item["name"]))

    assert missing == []


def test_blacklist_prefers_name_and_stage_over_name_only(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    blacklist_file = data_dir / "blacklists" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "blacklisted_templates": [
                    {
                        "name": "weak_template",
                        "template_stage": "group_second_order",
                        "template_family": "group_zscore",
                    }
                ],
                "auto_avoid_rules": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    _BLACKLIST_CACHE.clear()

    assert _is_blacklisted_template(
        "weak_template",
        "group_rank(ts_zscore(close, 60), subindustry)",
        template_metadata={"stage": "group_second_order", "family": "group_zscore"},
        dataset_id="custom_ds",
    )
    assert not _is_blacklisted_template(
        "weak_template",
        "rank(ts_zscore(close, 60))",
        template_metadata={"stage": "first_order", "family": "zscore_time"},
        dataset_id="custom_ds",
    )


def test_legacy_blacklist_name_only_only_applies_without_runtime_metadata(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    blacklist_file = data_dir / "blacklists" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "blacklisted_templates": [{"name": "legacy_template"}],
                "auto_avoid_rules": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    _BLACKLIST_CACHE.clear()

    assert _is_blacklisted_template("legacy_template", dataset_id="custom_ds")
    assert not _is_blacklisted_template(
        "legacy_template",
        "rank(close)",
        template_metadata={"stage": "first_order", "family": "legacy_level"},
        dataset_id="custom_ds",
    )


def test_blacklist_pattern_rules_support_exact_and_regex(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    blacklist_file = data_dir / "blacklists" / "custom_ds" / "blacklist.json"
    blacklist_file.parent.mkdir(parents=True)
    blacklist_file.write_text(
        json.dumps(
            {
                "dataset_id": "custom_ds",
                "blacklisted_templates": [],
                "auto_avoid_rules": [
                    {"type": "exact", "pattern": "rank(close)"},
                    {"type": "regex", "pattern": r"ts_delta\(.*?, 5\)"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    _BLACKLIST_CACHE.clear()

    assert _is_blacklisted_template("t1", "rank(close)", dataset_id="custom_ds")
    assert _is_blacklisted_template("t2", "rank(ts_delta(close, 5))", dataset_id="custom_ds")
    assert not _is_blacklisted_template("t3", "rank(close) + 1", dataset_id="custom_ds")
