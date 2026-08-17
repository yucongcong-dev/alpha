"""Incremental dataset feedback run-index tests."""

from __future__ import annotations

from alpha.analysis.feedback_history import (
    _load_dataset_run_results,
    build_historical_run_state,
)
from alpha.analysis.feedback_run_index import (
    feedback_run_index_is_current,
    load_feedback_run_index,
    persist_feedback_run_index,
)
from alpha.analysis.results_persistence import ResultPersistenceContext, persist_results
from alpha.models.domain import FieldTestResult


def _result(field_id: str) -> FieldTestResult:
    return FieldTestResult(
        field_id=field_id,
        field_type="MATRIX",
        field_name=field_id,
        template_name="rank",
        status="simulated",
        submittable=False,
        expression=f"rank({field_id})",
        settings_fingerprint="settings",
    )


def _run_config(run_name: str) -> dict[str, object]:
    return {
        "run": {"name": run_name},
        "dataset": {
            "region": "USA",
            "universe": "TOP3000",
            "instrument_type": "EQUITY",
            "delay": 1,
        },
    }


def _dump(path, result: FieldTestResult, run_name: str) -> None:
    persist_results(
        ResultPersistenceContext(
            output_path=str(path),
            dataset_id="model16",
            settings_fingerprint="settings",
            template_library_fingerprint="templates",
            run_config=_run_config(run_name),
        ),
        [result],
        include_analysis=False,
    )


def test_feedback_index_loads_only_new_runs_after_snapshot(tmp_path) -> None:
    run1 = tmp_path / "runs" / "run1" / "summary.json"
    run2 = tmp_path / "runs" / "run2" / "summary.json"
    feedback = tmp_path / "feedback" / "usa_top3000_equity_d1" / "summary.json"
    first = _result("f1")
    second = _result("f2")
    _dump(run1, first, "run1")
    _dump(feedback, first, "feedback")
    persist_feedback_run_index(str(feedback))

    assert set(load_feedback_run_index(str(feedback))) == {"run1/summary.json"}

    _dump(run2, second, "run2")
    state = build_historical_run_state(
        str(tmp_path / "runs" / "current" / "summary.json"),
        str(feedback),
    )

    assert {result.field_id for result in state.feedback_results} == {"f1", "f2"}


def test_feedback_index_reuses_unchanged_entry(tmp_path, monkeypatch) -> None:
    run1 = tmp_path / "runs" / "run1" / "summary.json"
    feedback = tmp_path / "feedback" / "usa_top3000_equity_d1" / "summary.json"
    _dump(run1, _result("f1"), "run1")
    persist_feedback_run_index(str(feedback))

    assert feedback_run_index_is_current(str(feedback), tmp_path / "runs")

    def unexpected_read(_path):
        raise AssertionError("unchanged run summary should not be reparsed")

    monkeypatch.setattr(
        "alpha.analysis.feedback_run_index.load_summary_run_config",
        unexpected_read,
    )

    persist_feedback_run_index(str(feedback))


def test_current_feedback_index_checks_signatures_without_parsing_summaries(
    tmp_path, monkeypatch
) -> None:
    run1 = tmp_path / "runs" / "run1" / "summary.json"
    feedback = tmp_path / "feedback" / "usa_top3000_equity_d1" / "summary.json"
    _dump(run1, _result("f1"), "run1")
    _dump(feedback, _result("f1"), "feedback")
    persist_feedback_run_index(str(feedback))

    def unexpected_load(*_args, **_kwargs):
        raise AssertionError("stable feedback index should not parse run summaries")

    monkeypatch.setattr("alpha.analysis.feedback_history.load_existing_results", unexpected_load)

    assert (
        _load_dataset_run_results(
            str(feedback),
            current_output_path=str(tmp_path / "runs" / "current" / "summary.json"),
        )
        == []
    )


def test_changed_summary_invalidates_feedback_index(tmp_path) -> None:
    run1 = tmp_path / "runs" / "run1" / "summary.json"
    feedback = tmp_path / "feedback" / "usa_top3000_equity_d1" / "summary.json"
    _dump(run1, _result("f1"), "run1")
    _dump(feedback, _result("f1"), "feedback")
    persist_feedback_run_index(str(feedback))
    assert feedback_run_index_is_current(str(feedback), tmp_path / "runs")

    _dump(run1, _result("f2"), "run1")

    assert not feedback_run_index_is_current(str(feedback), tmp_path / "runs")
    state = build_historical_run_state(
        str(tmp_path / "runs" / "current" / "summary.json"),
        str(feedback),
    )

    assert {result.field_id for result in state.feedback_results} == {"f1", "f2"}


def test_missing_feedback_journal_ignores_index_and_rebuilds_from_runs(tmp_path) -> None:
    run1 = tmp_path / "runs" / "run1" / "summary.json"
    feedback = tmp_path / "feedback" / "usa_top3000_equity_d1" / "summary.json"
    first = _result("f1")
    _dump(run1, first, "run1")
    _dump(feedback, first, "feedback")
    persist_feedback_run_index(str(feedback))
    (feedback.parent / "results.jsonl").unlink()

    state = build_historical_run_state(
        str(tmp_path / "runs" / "current" / "summary.json"),
        str(feedback),
    )

    assert [result.field_id for result in state.feedback_results] == ["f1"]
