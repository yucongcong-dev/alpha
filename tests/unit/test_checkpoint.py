"""Checkpoint recovery tests."""

from __future__ import annotations

import json

from alpha.core.checkpoint import load_pipeline_state
from alpha.models.runtime import ExecutionState, RuntimeConcurrencyState


def _build_execution_state() -> ExecutionState:
    return ExecutionState(
        results=[],
        attempted_keys=set(),
        template_stats={},
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )


def test_load_pipeline_state_ignores_invalid_completed_index(tmp_path) -> None:
    """Invalid numeric fields in state payload should fall back to fresh start."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({"version": 1, "completed_field_index": "oops"}),
        encoding="utf-8",
    )

    resumed = load_pipeline_state(
        str(state_file),
        runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        execution_state=_build_execution_state(),
    )

    assert resumed == 0


def test_load_pipeline_state_ignores_invalid_cooldown_shape(tmp_path) -> None:
    """Invalid cooldown fields should not crash resume logic."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "version": 1,
                "completed_field_index": 1,
                "remaining_cooldown_seconds": "oops",
            }
        ),
        encoding="utf-8",
    )

    resumed = load_pipeline_state(
        str(state_file),
        runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        execution_state=_build_execution_state(),
    )

    assert resumed == 0


def test_load_pipeline_state_restores_runtime_data_with_zero_cursor(tmp_path) -> None:
    """Breadth-first runs resume all fields while retaining persisted runtime state."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "version": 1,
                "completed_field_index": 0,
                "field_queue_busy_counts": {"f1": 2},
                "skipped_fields_due_to_queue": ["f2"],
                "template_stats": {"base": {"attempted": 3}},
                "pending_template_keys": [
                    {
                        "field_id": "f1",
                        "template_name": "base",
                        "expression": "rank(f1)",
                        "settings_fingerprint": "settings-v1",
                    }
                ],
                "runtime_max_workers": 1,
                "remaining_cooldown_seconds": 30,
            }
        ),
        encoding="utf-8",
    )
    execution_state = _build_execution_state()
    runtime_state = RuntimeConcurrencyState(max_workers=4, runtime_max_workers=4)

    resumed = load_pipeline_state(
        str(state_file),
        runtime_state=runtime_state,
        execution_state=execution_state,
    )

    assert resumed == 0
    assert execution_state.field_queue_busy_counts == {"f1": 2}
    assert execution_state.skipped_fields_due_to_queue == {"f2"}
    assert execution_state.template_stats["base"]["attempted"] == 3
    assert execution_state.template_stats["base"]["submittable"] == 0
    assert execution_state.attempted_keys == {("f1", "base", "rank(f1)", "settings-v1")}
    assert runtime_state.runtime_max_workers == 1
    assert runtime_state.cooldown_until > 0


def test_load_pipeline_state_sanitizes_corrupt_runtime_collections(tmp_path) -> None:
    """Invalid persisted counters must not poison scheduling after restart."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "version": 1,
                "completed_field_index": 0,
                "field_queue_busy_counts": {
                    "f1": "3",
                    "f2": -1,
                    "": 4,
                    "f3": True,
                },
                "skipped_fields_due_to_queue": ["f1", "", 2],
                "template_stats": {
                    "base": {
                        "attempted": "2",
                        "submittable": "invalid",
                    },
                    "broken": [],
                },
                "runtime_max_workers": 0,
                "remaining_cooldown_seconds": 30,
            }
        ),
        encoding="utf-8",
    )
    execution_state = _build_execution_state()
    runtime_state = RuntimeConcurrencyState(max_workers=4, runtime_max_workers=4)

    resumed = load_pipeline_state(
        str(state_file),
        runtime_state=runtime_state,
        execution_state=execution_state,
    )

    assert resumed == 0
    assert execution_state.field_queue_busy_counts == {"f1": 3}
    assert execution_state.skipped_fields_due_to_queue == {"f1"}
    assert set(execution_state.template_stats) == {"base"}
    assert execution_state.template_stats["base"]["attempted"] == 2
    assert execution_state.template_stats["base"]["submittable"] == 0
    assert execution_state.template_stats["base"]["simulated"] == 0
    assert runtime_state.runtime_max_workers == 1


def test_load_pipeline_state_caps_restored_concurrency_at_configured_maximum(tmp_path) -> None:
    """A state file cannot silently expand the configured worker pool."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "version": 1,
                "completed_field_index": 0,
                "runtime_max_workers": 99,
                "remaining_cooldown_seconds": 30,
            }
        ),
        encoding="utf-8",
    )
    runtime_state = RuntimeConcurrencyState(max_workers=4, runtime_max_workers=4)

    load_pipeline_state(
        str(state_file),
        runtime_state=runtime_state,
        execution_state=_build_execution_state(),
    )

    assert runtime_state.runtime_max_workers == 4


def test_load_pipeline_state_discards_non_finite_cooldown_and_counters(tmp_path) -> None:
    """Infinity from a damaged JSON file must not create a permanent cooldown."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "version": 1,
                "completed_field_index": 0,
                "field_queue_busy_counts": {"f1": float("inf")},
                "runtime_max_workers": 1,
                "remaining_cooldown_seconds": float("inf"),
            }
        ),
        encoding="utf-8",
    )
    execution_state = _build_execution_state()
    runtime_state = RuntimeConcurrencyState(max_workers=4, runtime_max_workers=4)

    load_pipeline_state(
        str(state_file),
        runtime_state=runtime_state,
        execution_state=execution_state,
    )

    assert execution_state.field_queue_busy_counts == {}
    assert runtime_state.runtime_max_workers == 4
    assert runtime_state.cooldown_until == 0
