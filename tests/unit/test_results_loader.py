"""Result summary and journal recovery tests."""

from __future__ import annotations

import json
import shutil

import pytest

from alpha.analysis.results_loader import load_existing_results
from alpha.analysis.results_persistence import dump_results
from alpha.io.results_store import initialize_results_journal
from alpha.models.domain import FailedCheck, FieldTestResult


def test_load_existing_results_prefers_journal_over_embedded_summary(tmp_path) -> None:
    """The append-only journal is authoritative when legacy embedded rows disagree."""
    output_path = tmp_path / "results.json"
    initialize_results_journal(
        str(output_path),
        [
            FieldTestResult(
                field_id="journal_field",
                field_type="MATRIX",
                field_name="journal_field",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression="rank(journal_field)",
            )
        ],
    )
    output_path.write_text(
        json.dumps(
            {
                "results_embedded": True,
                "results_journal": str(tmp_path / "results_results.jsonl"),
                "results": [
                    {
                        "field_id": "stale_embedded_field",
                        "field_type": "MATRIX",
                        "field_name": "stale_embedded_field",
                        "template_name": "tpl",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_existing_results(str(output_path))

    assert [result.field_id for result in loaded] == ["journal_field"]


def test_load_existing_results_falls_back_when_journal_row_is_invalid(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    journal_path = tmp_path / "results_results.jsonl"
    journal_path.write_text(
        json.dumps({"field_id": "broken", "delay": "not-an-int"}) + "\n",
        encoding="utf-8",
    )
    output_path.write_text(
        json.dumps(
            {
                "results_journal": journal_path.name,
                "results_embedded": True,
                "results": [
                    {
                        "field_id": "embedded_field",
                        "field_type": "MATRIX",
                        "field_name": "embedded_field",
                        "template_name": "tpl",
                        "status": "simulated",
                        "submittable": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_existing_results(str(output_path))

    assert [result.field_id for result in loaded] == ["embedded_field"]


def test_load_existing_results_rejects_invalid_embedded_row(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    output_path.write_text(
        json.dumps(
            {
                "results_embedded": True,
                "results": [{"field_id": "broken", "revision": "not-an-int"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"results\.json:results:1"):
        load_existing_results(str(output_path))


def test_load_existing_results_preserves_template_role_metadata(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    results = [
        FieldTestResult(
            field_id="field_role",
            field_type="MATRIX",
            field_name="field_role",
            template_name="tpl",
            template_role="promoted_core",
            template_activation_scope="broad",
            status="simulated",
            submittable=False,
            expression="rank(field_role)",
        )
    ]

    dump_results(
        str(output_path),
        "fundamental6",
        results,
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        include_analysis=False,
    )

    loaded = load_existing_results(str(output_path))

    assert loaded[0].template_role == "promoted_core"
    assert loaded[0].template_activation_scope == "broad"


def test_load_existing_results_recovers_moved_legacy_absolute_journal(tmp_path) -> None:
    run_dir = tmp_path / "legacy-run"
    output_path = run_dir / "summary.json"
    dump_results(
        str(output_path),
        "fundamental6",
        [
            FieldTestResult(
                field_id="field_legacy",
                field_type="MATRIX",
                field_name="field_legacy",
                template_name="tpl",
                status="simulated",
                expression="rank(field_legacy)",
            )
        ],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        include_analysis=False,
    )
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    summary["results_journal"] = str(run_dir / "results.jsonl")
    output_path.write_text(json.dumps(summary), encoding="utf-8")

    moved_dir = tmp_path / "legacy-moved"
    shutil.move(str(run_dir), str(moved_dir))

    assert load_existing_results(str(moved_dir / "summary.json"))[0].field_id == "field_legacy"


def test_load_existing_results_preserves_self_correlation_pending_metadata(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    result = FieldTestResult(
        field_id="field_pending",
        field_type="MATRIX",
        field_name="field_pending",
        template_name="tpl",
        status="simulated",
        submittable=None,
        expression="rank(field_pending)",
        failed_checks=[
            FailedCheck(name="SELF_CORRELATION", result="PENDING", value=None, limit=None)
        ],
    )

    dump_results(
        str(output_path),
        "fundamental6",
        [result],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        include_analysis=False,
    )

    loaded = load_existing_results(str(output_path))

    assert len(loaded) == 1
    assert loaded[0].status == "simulated"
    assert loaded[0].submittable is None
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["pending_checks"] == 1


def test_load_existing_results_falls_back_to_orphaned_journal_when_summary_missing(
    tmp_path,
) -> None:
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


def test_read_only_result_load_does_not_rename_corrupted_summary(tmp_path) -> None:
    """Planning may recover from journal but must leave a corrupt summary untouched."""
    output_path = tmp_path / "results.json"
    initialize_results_journal(
        str(output_path),
        [
            FieldTestResult(
                field_id="field_read_only",
                field_type="MATRIX",
                field_name="field_read_only",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression="rank(field_read_only)",
            )
        ],
    )
    output_path.write_text("{not-json", encoding="utf-8")

    loaded = load_existing_results(str(output_path), repair_corrupt_summary=False)

    assert len(loaded) == 1
    assert loaded[0].field_id == "field_read_only"
    assert output_path.read_text(encoding="utf-8") == "{not-json"
    assert not list(tmp_path.glob("results.json.corrupted.*"))


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
