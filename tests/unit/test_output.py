"""Output persistence tests."""

from __future__ import annotations

import json
from pathlib import Path

from alpha.analysis.stats import load_existing_results
from alpha.models.base import FieldTestResult
from alpha.io.output import (
    auto_update_blacklist_incremental,
    build_blacklist_runtime_stats,
    build_dataset_scoped_paths,
    dump_results,
    dump_results_incremental,
    initialize_results_journal,
    load_blacklisted_template_names,
    resolve_cli_path,
)


def test_dump_results_does_not_update_blacklist_by_default(monkeypatch, tmp_path) -> None:
    """Runtime result writes must not mutate tracked blacklist files unless requested."""
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("alpha.io.output.auto_update_blacklist", lambda *args, **kwargs: calls.append(args))

    dump_results(
        str(tmp_path / "results.json"),
        "fundamental6",
        [],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
    )

    assert calls == []


def test_dump_results_updates_blacklist_when_enabled(monkeypatch, tmp_path) -> None:
    """The explicit opt-in flag should preserve the previous auto-update capability."""
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("alpha.io.output.auto_update_blacklist", lambda *args, **kwargs: calls.append(args))

    dump_results(
        str(tmp_path / "results.json"),
        "fundamental6",
        [],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        auto_update_template_blacklist=True,
    )

    assert len(calls) == 1


def test_dump_results_can_skip_analysis_sidecar_for_intermediate_flushes(tmp_path) -> None:
    """Intermediate flushes should be able to persist raw results without full analysis rebuild."""
    output_path = tmp_path / "results.json"

    dump_results(
        str(output_path),
        "fundamental6",
        [],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        include_analysis=False,
    )

    assert output_path.exists()
    assert not (tmp_path / "results_analysis.json").exists()


def test_initialize_results_journal_and_load_existing_results(tmp_path) -> None:
    """Journal-backed summaries should remain readable by load_existing_results."""
    output_path = tmp_path / "results.json"
    results = [
        FieldTestResult(
            field_id="field_1",
            field_type="MATRIX",
            field_name="field_1",
            template_name="tpl",
            status="simulated",
            submittable=False,
            expression="rank(field_1)",
        )
    ]

    initialize_results_journal(str(output_path), results)
    payload = {
        "dataset_id": "fundamental6",
        "tested": 1,
        "submittable": 0,
        "submitted": 0,
        "errors": 0,
        "queue_timeouts": 0,
        "results_embedded": False,
        "results_journal": str(tmp_path / "results_results.jsonl"),
    }
    output_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_existing_results(str(output_path))

    assert len(loaded) == 1
    assert loaded[0].field_id == "field_1"


def test_dump_results_incremental_writes_lightweight_summary(tmp_path) -> None:
    """Incremental flushes should append new rows without embedding all results in summary."""
    output_path = tmp_path / "results.json"
    result = FieldTestResult(
        field_id="field_2",
        field_type="MATRIX",
        field_name="field_2",
        template_name="tpl",
        status="simulated",
        submittable=True,
        expression="rank(field_2)",
    )

    persisted = dump_results_incremental(
        str(output_path),
        "fundamental6",
        [result],
        persisted_result_count=0,
        tested=1,
        unique_fields_tested=1,
        submittable_count=1,
        submitted_count=0,
        error_count=0,
        queue_timeout_count=0,
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        run_config={"mode": "incremental"},
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == 1
    assert payload["results_embedded"] is False
    assert "results" not in payload
    assert load_existing_results(str(output_path))[0].field_id == "field_2"


def test_dump_results_incremental_can_flip_existing_summary_to_journal_mode(tmp_path) -> None:
    """Bootstrapping a run should switch the main summary to journal mode before new results arrive."""
    output_path = tmp_path / "results.json"
    result = FieldTestResult(
        field_id="field_3",
        field_type="MATRIX",
        field_name="field_3",
        template_name="tpl",
        status="simulated",
        submittable=False,
        expression="rank(field_3)",
    )

    dump_results(
        str(output_path),
        "fundamental6",
        [result],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        include_analysis=False,
    )
    persisted = initialize_results_journal(str(output_path), [result])
    persisted = dump_results_incremental(
        str(output_path),
        "fundamental6",
        [],
        persisted_result_count=persisted,
        tested=1,
        unique_fields_tested=1,
        submittable_count=0,
        submitted_count=0,
        error_count=0,
        queue_timeout_count=0,
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == 1
    assert payload["results_embedded"] is False
    assert "results" not in payload
    assert load_existing_results(str(output_path))[0].field_id == "field_3"


def test_load_existing_results_falls_back_to_orphaned_journal_when_summary_missing(tmp_path) -> None:
    """Journal should still be recoverable even if the lightweight summary is gone."""
    output_path = tmp_path / "results.json"
    initialize_results_journal(
        str(output_path),
        [
            FieldTestResult(
                field_id="field_4",
                field_type="MATRIX",
                field_name="field_4",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression="rank(field_4)",
            )
        ],
    )

    loaded = load_existing_results(str(output_path))

    assert len(loaded) == 1
    assert loaded[0].field_id == "field_4"


def test_load_existing_results_falls_back_to_journal_when_summary_corrupted(tmp_path) -> None:
    """A corrupted summary file should not discard a healthy results journal."""
    output_path = tmp_path / "results.json"
    initialize_results_journal(
        str(output_path),
        [
            FieldTestResult(
                field_id="field_5",
                field_type="MATRIX",
                field_name="field_5",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression="rank(field_5)",
            )
        ],
    )
    output_path.write_text("{not-json", encoding="utf-8")

    loaded = load_existing_results(str(output_path))

    assert len(loaded) == 1
    assert loaded[0].field_id == "field_5"
    assert not output_path.exists()


def test_load_existing_results_falls_back_to_journal_when_summary_has_invalid_json_shape(
    tmp_path,
) -> None:
    """A valid JSON file with the wrong top-level type should still recover from journal."""
    output_path = tmp_path / "results.json"
    initialize_results_journal(
        str(output_path),
        [
            FieldTestResult(
                field_id="field_6",
                field_type="MATRIX",
                field_name="field_6",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression="rank(field_6)",
            )
        ],
    )
    output_path.write_text("[]", encoding="utf-8")

    loaded = load_existing_results(str(output_path))

    assert len(loaded) == 1
    assert loaded[0].field_id == "field_6"
    assert not output_path.exists()


def test_auto_update_blacklist_incremental_blacklists_only_changed_template(tmp_path) -> None:
    """Incremental blacklist updates should blacklist qualifying templates without full rescans."""
    runtime_stats = build_blacklist_runtime_stats([])
    blacklisted_names = load_blacklisted_template_names("custom_ds", data_dir=str(tmp_path))
    first = FieldTestResult(
        field_id="f1",
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
    )
    second = FieldTestResult(
        field_id="f2",
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
    )

    added_after_first = auto_update_blacklist_incremental(
        runtime_stats,
        blacklisted_names,
        first,
        "custom_ds",
        data_dir=str(tmp_path),
    )
    added_after_second = auto_update_blacklist_incremental(
        runtime_stats,
        blacklisted_names,
        second,
        "custom_ds",
        data_dir=str(tmp_path),
    )

    payload = json.loads((tmp_path / "blacklists" / "custom_ds" / "blacklist.json").read_text())
    assert added_after_first is False
    assert added_after_second is True
    assert [entry["name"] for entry in payload["blacklisted_templates"]] == ["weak_template"]


def test_resolve_cli_path_uses_cwd_for_relative_paths(monkeypatch, tmp_path) -> None:
    """Relative CLI paths should resolve from the current working directory."""
    monkeypatch.chdir(tmp_path)

    resolved = resolve_cli_path("nested/config.json")

    assert resolved == str((tmp_path / "nested" / "config.json").resolve())


def test_build_dataset_scoped_paths_includes_runtime_context_in_cache_path() -> None:
    """Cache paths should distinguish region/universe/instrument/delay contexts."""
    paths = build_dataset_scoped_paths(
        "fundamental6",
        region="USA",
        universe="TOP3000",
        instrument_type="EQUITY",
        delay=1,
    )

    template_path = Path(paths["template_library_file"])
    assert template_path.parts[-4:] == ("data", "templates", "fundamental6", "library.json")
    cache_path = Path(paths["fields_cache_file"])
    assert cache_path.parent.parts[-7:] == (
        "cache",
        "fields",
        "fundamental6",
        "USA",
        "TOP3000",
        "EQUITY",
        "delay1",
    )
    assert cache_path.name == "fields.json"
    assert Path(paths["output"]).name == "test_results.json"
