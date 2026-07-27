"""Derived execution-state metric tests."""

from __future__ import annotations

from alpha.config.application_sections import QualityConfig
from alpha.models.domain import FieldTestResult
from alpha.runtime.state import ExecutionState


def _state() -> ExecutionState:
    return ExecutionState(
        results=[],
        attempted_keys=set(),
        template_stats={},
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )


def test_execution_metrics_follow_results_without_manual_refresh() -> None:
    state = _state()
    state.results.append(
        FieldTestResult(
            field_id="field_1",
            field_type="MATRIX",
            field_name="field_1",
            template_name="tpl",
            status="simulated",
            submittable=True,
            submitted=True,
            expression="rank(field_1)",
        )
    )

    assert state.unique_field_ids == {"field_1"}
    assert state.submittable_count == 1
    assert state.submitted_count == 1
    assert state.error_count == 0

    state.results.clear()
    assert state.unique_field_ids == set()
    assert state.submittable_count == 0
    assert state.submitted_count == 0


def test_quality_config_rejects_inverted_turnover_range() -> None:
    try:
        QualityConfig(
            min_sharpe=1.0,
            min_fitness=1.0,
            min_turnover=0.8,
            max_turnover=0.2,
            max_weight=0.1,
        )
    except ValueError as exc:
        assert "min_turnover" in str(exc)
    else:
        raise AssertionError("inverted turnover bounds must be rejected")
