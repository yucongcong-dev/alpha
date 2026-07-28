"""Deterministic result conflict and provenance tests."""

from __future__ import annotations

from alpha.analysis.result_identity import merge_results_by_identity, merge_results_for_update
from alpha.analysis.result_provenance import enrich_results_provenance
from alpha.models.domain import FieldTestResult


def _result(**overrides: object) -> FieldTestResult:
    values: dict[str, object] = {
        "field_id": "f1",
        "field_type": "MATRIX",
        "field_name": "f1",
        "template_name": "rank",
        "expression": "rank(f1)",
        "settings_fingerprint": "scope",
    }
    values.update(overrides)
    return FieldTestResult(**values)  # type: ignore[arg-type]


def test_merge_preserves_terminal_success_over_later_error() -> None:
    successful = _result(
        status="simulated",
        submittable=True,
        updated_at="2026-01-01T00:00:00Z",
    )
    later_error = _result(
        status="error",
        submittable=False,
        updated_at="2026-02-01T00:00:00Z",
    )

    assert merge_results_by_identity([successful], [later_error]) == [successful]


def test_merge_uses_timestamp_for_equal_terminal_states() -> None:
    older = _result(
        status="simulated",
        submittable=False,
        updated_at="2026-01-01T00:00:00Z",
    )
    newer = _result(
        status="simulated",
        submittable=False,
        updated_at="2026-02-01T00:00:00Z",
    )

    assert merge_results_by_identity([newer], [older]) == [newer]


def test_persistence_update_advances_revision() -> None:
    existing = _result(status="simulated", submittable=False, revision=3)
    update = _result(status="simulated", submittable=True, revision=1)

    merged = merge_results_for_update([existing], [update])

    assert merged[0].submittable is True
    assert merged[0].revision == 4


def test_enrich_results_provenance_fills_scope_and_portable_source() -> None:
    result = _result()

    enrich_results_provenance(
        [result],
        output_path="/tmp/datasets/model16/runs/run-7/summary.json",
        run_config={
            "run": {"name": "run-7"},
            "dataset": {
                "region": "USA",
                "universe": "TOP3000",
                "instrument_type": "EQUITY",
                "delay": 1,
            },
        },
        observed_at="2026-03-01T00:00:00Z",
    )

    assert result.run_name == "run-7"
    assert result.source_summary == "runs/run-7/summary.json"
    assert (result.region, result.universe, result.instrument_type, result.delay) == (
        "USA",
        "TOP3000",
        "EQUITY",
        1,
    )
    assert result.created_at == "2026-03-01T00:00:00Z"
