"""Output persistence tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import multiprocessing
import shutil

import pytest

from alpha.analysis.results_loader import load_existing_results
from alpha.analysis.results_persistence import dump_results, dump_results_incremental
from alpha.io.results_store import (
    JOURNAL_CHECKSUM_FIELD,
    JOURNAL_SCHEMA_FIELD,
    _append_results_journal,
    initialize_results_journal,
    load_results_rows_from_journal,
)
from alpha.models.domain import FailedCheck, FieldTestResult


def _append_process_batch(journal_path: str, batch_index: int) -> None:
    results = [
        FieldTestResult(
            field_id=f"process_{batch_index}_{item_index}",
            field_type="MATRIX",
            field_name=f"process_{batch_index}_{item_index}",
            template_name="tpl",
            status="simulated",
            submittable=False,
            expression=f"rank(process_{batch_index}_{item_index})",
        )
        for item_index in range(5)
    ]
    _append_results_journal(journal_path, results)


def test_dump_results_is_policy_side_effect_free(tmp_path) -> None:
    """The persistence layer must not trigger policy updates."""
    dump_results(
        str(tmp_path / "results.json"),
        "fundamental6",
        [],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
    )

    assert (tmp_path / "results.json").exists()


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
    assert (tmp_path / "results_template_registry.json").exists()


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


def test_append_results_journal_ignores_empty_batch(tmp_path) -> None:
    journal_path = tmp_path / "results.jsonl"

    _append_results_journal(str(journal_path), [])

    assert not journal_path.exists()


def test_append_results_journal_retry_is_idempotent(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    initialize_results_journal(str(output_path), [])
    journal_path = tmp_path / "results_results.jsonl"
    results = [
        FieldTestResult(
            field_id="field_retry",
            field_type="MATRIX",
            field_name="field_retry",
            template_name="tpl",
            status="simulated",
            submittable=False,
            expression="rank(field_retry)",
        )
    ]

    assert _append_results_journal(str(journal_path), results, expected_row_count=0) == 1
    assert _append_results_journal(str(journal_path), results, expected_row_count=0) == 1

    rows = load_results_rows_from_journal(str(journal_path))
    assert [row["field_id"] for row in rows] == ["field_retry"]


def test_append_results_journal_uses_cached_state_for_normal_appends(
    tmp_path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "results.json"
    initialize_results_journal(str(output_path), [])
    journal_path = tmp_path / "results_results.jsonl"

    def _result(field_id: str) -> FieldTestResult:
        return FieldTestResult(
            field_id=field_id,
            field_type="MATRIX",
            field_name=field_id,
            template_name="tpl",
            status="simulated",
            submittable=False,
            expression=f"rank({field_id})",
        )

    assert (
        _append_results_journal(
            str(journal_path),
            [_result("field_1")],
            expected_row_count=0,
        )
        == 1
    )
    monkeypatch.setattr(
        "alpha.io.results_store.load_results_rows_from_journal",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected full scan")),
    )

    assert (
        _append_results_journal(
            str(journal_path),
            [_result("field_2")],
            expected_row_count=1,
        )
        == 2
    )


def test_append_results_journal_rejects_retry_with_different_rows(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    initialize_results_journal(str(output_path), [])
    journal_path = tmp_path / "results_results.jsonl"
    _append_results_journal(
        str(journal_path),
        [
            FieldTestResult(
                field_id="field_original",
                field_type="MATRIX",
                field_name="field_original",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression="rank(field_original)",
            )
        ],
        expected_row_count=0,
    )

    with pytest.raises(RuntimeError, match="advanced with different rows"):
        _append_results_journal(
            str(journal_path),
            [
                FieldTestResult(
                    field_id="field_other",
                    field_type="MATRIX",
                    field_name="field_other",
                    template_name="tpl",
                    status="simulated",
                    submittable=False,
                    expression="rank(field_other)",
                )
            ],
            expected_row_count=0,
        )


def test_append_results_journal_rejects_unexpected_row_count(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    initialize_results_journal(str(output_path), [])
    journal_path = tmp_path / "results_results.jsonl"
    result = FieldTestResult(
        field_id="field_count",
        field_type="MATRIX",
        field_name="field_count",
        template_name="tpl",
        status="simulated",
        submittable=False,
        expression="rank(field_count)",
    )
    _append_results_journal(str(journal_path), [result], expected_row_count=0)

    with pytest.raises(RuntimeError, match="does not match"):
        _append_results_journal(str(journal_path), [result], expected_row_count=5)


def test_append_results_journal_empty_batch_returns_expected_count(tmp_path) -> None:
    journal_path = tmp_path / "results.jsonl"

    assert _append_results_journal(str(journal_path), [], expected_row_count=3) == 3
    assert not journal_path.exists()


def test_journal_rows_are_versioned_and_checksums_are_validated(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    initialize_results_journal(
        str(output_path),
        [
            FieldTestResult(
                field_id="field_versioned",
                field_type="MATRIX",
                field_name="field_versioned",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression="rank(field_versioned)",
            )
        ],
    )
    journal_path = tmp_path / "results_results.jsonl"

    rows = load_results_rows_from_journal(str(journal_path))

    assert rows[0][JOURNAL_SCHEMA_FIELD] == 2
    assert rows[0][JOURNAL_CHECKSUM_FIELD]
    rows[0]["field_id"] = "tampered"
    journal_path.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_results_rows_from_journal(str(journal_path))


def test_journal_reader_rejects_unsupported_schema_version(tmp_path) -> None:
    journal_path = tmp_path / "results.jsonl"
    journal_path.write_text(
        json.dumps(
            {
                "field_id": "field_schema",
                "field_type": "MATRIX",
                "field_name": "field_schema",
                "template_name": "tpl",
                "status": "simulated",
                "submittable": False,
                JOURNAL_SCHEMA_FIELD: 99,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported results journal schema version"):
        load_results_rows_from_journal(str(journal_path))


def test_journal_reader_rejects_non_object_row(tmp_path) -> None:
    journal_path = tmp_path / "results.jsonl"
    journal_path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"results\.jsonl:1; expected object"):
        load_results_rows_from_journal(str(journal_path))


def test_journal_reader_ignores_only_an_incomplete_trailing_row(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    initialize_results_journal(
        str(output_path),
        [
            FieldTestResult(
                field_id="field_complete",
                field_type="MATRIX",
                field_name="field_complete",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression="rank(field_complete)",
            )
        ],
    )
    journal_path = tmp_path / "results_results.jsonl"
    with journal_path.open("a", encoding="utf-8") as handle:
        handle.write('{"field_id":"partial"')

    rows = load_results_rows_from_journal(str(journal_path))

    assert [row["field_id"] for row in rows] == ["field_complete"]


def test_concurrent_journal_batches_do_not_interleave(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    initialize_results_journal(str(output_path), [])
    journal_path = tmp_path / "results_results.jsonl"
    batches = [
        [
            FieldTestResult(
                field_id=f"field_{batch_index}_{item_index}",
                field_type="MATRIX",
                field_name=f"field_{batch_index}_{item_index}",
                template_name="tpl",
                status="simulated",
                submittable=False,
                expression=f"rank(field_{batch_index}_{item_index})",
            )
            for item_index in range(10)
        ]
        for batch_index in range(8)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda batch: _append_results_journal(str(journal_path), batch), batches))

    rows = load_results_rows_from_journal(str(journal_path))

    assert len(rows) == 80
    assert len({row["field_id"] for row in rows}) == 80


def test_concurrent_processes_share_the_journal_lock(tmp_path) -> None:
    output_path = tmp_path / "results.json"
    initialize_results_journal(str(output_path), [])
    journal_path = tmp_path / "results_results.jsonl"
    start_method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
    context = multiprocessing.get_context(start_method)
    processes = [
        context.Process(target=_append_process_batch, args=(str(journal_path), batch_index))
        for batch_index in range(4)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    rows = load_results_rows_from_journal(str(journal_path))
    assert len(rows) == 20
    assert len({row["field_id"] for row in rows}) == 20


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


def test_dump_results_persists_metrics_settings_and_portable_journal_reference(tmp_path) -> None:
    run_dir = tmp_path / "run-a"
    output_path = run_dir / "summary.json"
    result = FieldTestResult(
        field_id="cashflow_op",
        field_type="MATRIX",
        field_name="cashflow_op",
        template_name="group_rank",
        status="simulated",
        submittable=True,
        expression="group_rank(cashflow_op, subindustry)",
        settings={"decay": 4, "neutralization": "SUBINDUSTRY"},
        metrics={"sharpe": 1.42, "fitness": 1.11, "turnover": 0.18},
    )
    dump_results(
        str(output_path),
        "fundamental6",
        [result],
        settings_fingerprint="settings",
        template_library_fingerprint="templates",
        include_analysis=False,
    )

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["results_journal"] == "results.jsonl"

    moved_dir = tmp_path / "run-moved"
    shutil.move(str(run_dir), str(moved_dir))
    loaded = load_existing_results(str(moved_dir / "summary.json"))

    assert loaded[0].settings["neutralization"] == "SUBINDUSTRY"
    assert loaded[0].metrics["sharpe"] == 1.42


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


def test_dump_results_incremental_writes_lightweight_summary(tmp_path) -> None:
    """Incremental flushes should append new rows without embedding all results in summary."""
    output_path = tmp_path / "results.json"
    result = FieldTestResult(
        field_id="field_2",
        field_type="MATRIX",
        field_name="field_2",
        template_name="tpl",
        template_role="promoted_core",
        template_activation_scope="broad",
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
        template_registry_summary=[
            {
                "template_name": "tpl",
                "template_role": "promoted_core",
                "activation_scope": "broad",
            }
        ],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == 1
    assert payload["results_embedded"] is False
    assert "results" not in payload
    registry = json.loads((tmp_path / "results_template_registry.json").read_text(encoding="utf-8"))
    assert registry[0]["template_name"] == "tpl"
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
