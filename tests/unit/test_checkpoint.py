"""Checkpoint recovery tests."""

from __future__ import annotations

from functools import partial
import json
from unittest.mock import patch

import alpha.core.checkpoint as checkpoint_module
from alpha.core.checkpoint import (
    delete_pipeline_state,
)
from alpha.core.checkpoint import (
    load_pipeline_state as _load_pipeline_state,
)
from alpha.core.checkpoint import (
    save_interrupt_report as _save_interrupt_report,
)
from alpha.core.checkpoint import (
    save_pipeline_state as _save_pipeline_state,
)
from alpha.runtime.concurrency import RuntimeConcurrencyState
from alpha.runtime.contexts import CheckpointIdentity, PendingFutureContext
from alpha.runtime.state import ExecutionState

IDENTITY = CheckpointIdentity("settings-current", "templates-current")
load_pipeline_state = partial(_load_pipeline_state, identity=IDENTITY)
save_interrupt_report = partial(_save_interrupt_report, identity=IDENTITY)
save_pipeline_state = partial(_save_pipeline_state, identity=IDENTITY)


def _checkpoint_json(payload: dict[str, object]) -> str:
    return json.dumps(
        {
            **payload,
            "version": checkpoint_module.STATE_VERSION,
            "settings_fingerprint": IDENTITY.settings_fingerprint,
            "template_library_fingerprint": IDENTITY.template_library_fingerprint,
        }
    )


def _build_execution_state() -> ExecutionState:
    return ExecutionState.create()


def test_load_pipeline_state_ignores_invalid_completed_index(tmp_path) -> None:
    """Invalid numeric fields in state payload should fall back to fresh start."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        _checkpoint_json({"completed_field_index": "oops"}),
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
        _checkpoint_json(
            {
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


def test_load_pipeline_state_preserves_result_derived_stats_with_zero_cursor(tmp_path) -> None:
    """Breadth-first resume must not overwrite statistics rebuilt from durable results."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        _checkpoint_json(
            {
                "completed_field_index": 0,
                "field_queue_busy_counts": {"f1": 2},
                "skipped_fields_due_to_queue": ["f2"],
                "template_stats": {"stale": {"attempted": 3}},
                "pending_simulations": [
                    {
                        "field_id": "f1",
                        "field_name": "Field 1",
                        "field_type": "MATRIX",
                        "template_name": "base",
                        "expression": "rank(f1)",
                        "settings_fingerprint": "settings-v1",
                        "simulation_location": "/simulations/sim-1",
                        "simulation_id": "sim-1",
                    }
                ],
                "runtime_max_workers": 1,
                "remaining_cooldown_seconds": 30,
            }
        ),
        encoding="utf-8",
    )
    execution_state = ExecutionState.create(
        template_stats={"current": {"attempted": 4, "submittable": 1}}
    )
    runtime_state = RuntimeConcurrencyState(max_workers=4, runtime_max_workers=4)

    resumed = load_pipeline_state(
        str(state_file),
        runtime_state=runtime_state,
        execution_state=execution_state,
    )

    assert resumed == 0
    assert execution_state.queue_retry_state.retry_counts == {}
    assert execution_state.template_stats == {"current": {"attempted": 4, "submittable": 1}}
    assert execution_state.attempted_keys == set()
    assert len(execution_state.future_queue.resumable_simulations) == 1
    restored = execution_state.future_queue.resumable_simulations[0]
    assert restored.field_name == "Field 1"
    assert restored.simulation_location == "/simulations/sim-1"
    assert restored.simulation_id == "sim-1"
    assert runtime_state.runtime_max_workers == 1
    assert runtime_state.cooldown_until > 0


def test_load_pipeline_state_ignores_legacy_template_stats(tmp_path) -> None:
    """Legacy checkpoint statistics must not replace the result-derived source of truth."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        _checkpoint_json(
            {
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
    execution_state = ExecutionState.create(
        template_stats={"current": {"attempted": 5, "simulated": 4}}
    )
    runtime_state = RuntimeConcurrencyState(max_workers=4, runtime_max_workers=4)

    resumed = load_pipeline_state(
        str(state_file),
        runtime_state=runtime_state,
        execution_state=execution_state,
    )

    assert resumed == 0
    assert execution_state.queue_retry_state.retry_counts == {}
    assert execution_state.template_stats == {"current": {"attempted": 5, "simulated": 4}}
    assert runtime_state.runtime_max_workers == 1


def test_load_pipeline_state_caps_restored_concurrency_at_configured_maximum(tmp_path) -> None:
    """A state file cannot silently expand the configured worker pool."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        _checkpoint_json(
            {
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
        _checkpoint_json(
            {
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

    assert execution_state.queue_retry_state.retry_counts == {}
    assert runtime_state.runtime_max_workers == 4
    assert runtime_state.cooldown_until == 0


def test_load_pipeline_state_retries_legacy_pending_entries_without_location(tmp_path) -> None:
    """Legacy pending keys cannot be resumed and must remain eligible for recreation."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        _checkpoint_json(
            {
                "completed_field_index": 2,
                "pending_template_keys": [
                    {
                        "field_id": "f1",
                        "template_name": "base",
                        "expression": "rank(f1)",
                        "settings_fingerprint": "settings-v1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    execution_state = _build_execution_state()

    resumed = load_pipeline_state(
        str(state_file),
        runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        execution_state=execution_state,
    )

    assert resumed == 0
    assert execution_state.attempted_keys == set()
    assert execution_state.future_queue.resumable_simulations == []


def test_save_pipeline_state_persists_remote_simulation_location(tmp_path) -> None:
    """A created remote simulation carries enough metadata for restart polling."""
    state_file = tmp_path / "state.json"
    execution_state = _build_execution_state()
    future = object()
    execution_state.future_queue.pending_futures[future] = PendingFutureContext(  # type: ignore[index]
        field_id="f1",
        field_name="Field 1",
        field_type="MATRIX",
        template_name="base",
        expression="rank(f1)",
        settings_fingerprint="settings-v1",
        simulation_location="/simulations/sim-1",
        simulation_id="sim-1",
    )

    saved = save_pipeline_state(
        str(state_file),
        completed_field_index=1,
        execution_state=execution_state,
        runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        field_id="f1",
    )

    payload = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved is True
    assert "template_stats" not in payload
    assert payload["pending_simulations"][0]["simulation_location"] == "/simulations/sim-1"


def test_load_pipeline_state_skips_resumable_simulation_already_in_results(tmp_path) -> None:
    """A stale state file must not append a duplicate for an already persisted result."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        _checkpoint_json(
            {
                "completed_field_index": 1,
                "pending_simulations": [
                    {
                        "field_id": "f1",
                        "template_name": "base",
                        "expression": "rank(f1)",
                        "settings_fingerprint": "settings-v1",
                        "simulation_location": "/simulations/sim-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    execution_state = _build_execution_state()
    execution_state.attempted_keys.add(("f1", "base", "rank(f1)", "settings-v1"))

    resumed = load_pipeline_state(
        str(state_file),
        runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        execution_state=execution_state,
    )

    assert resumed == 1
    assert execution_state.future_queue.resumable_simulations == []


def test_load_pipeline_state_rejects_different_run_identity(tmp_path, caplog) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        _checkpoint_json(
            {
                "completed_field_index": 1,
                "pending_simulations": [
                    {
                        "field_id": "f1",
                        "template_name": "base",
                        "expression": "rank(f1)",
                        "settings_fingerprint": "settings-v1",
                        "simulation_location": "/simulations/sim-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    execution_state = _build_execution_state()

    resumed = _load_pipeline_state(
        str(state_file),
        runtime_state=RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2),
        execution_state=execution_state,
        identity=CheckpointIdentity("settings-other", "templates-current"),
    )

    assert resumed == 0
    assert execution_state.future_queue.resumable_simulations == []
    assert "run identity mismatch" in caplog.text


def test_non_negative_int_rejects_untrusted_values() -> None:
    assert checkpoint_module._non_negative_int(True) is None
    assert checkpoint_module._non_negative_int(object()) is None
    assert checkpoint_module._non_negative_int("invalid") is None
    assert checkpoint_module._non_negative_int(-1) is None
    assert checkpoint_module._non_negative_int("3") == 3


def test_load_pipeline_state_handles_missing_invalid_and_version_mismatch(tmp_path) -> None:
    runtime_state = RuntimeConcurrencyState(max_workers=2, runtime_max_workers=2)

    assert (
        load_pipeline_state(
            "",
            runtime_state=runtime_state,
            execution_state=_build_execution_state(),
        )
        == 0
    )
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{", encoding="utf-8")
    assert (
        load_pipeline_state(
            str(invalid_json),
            runtime_state=runtime_state,
            execution_state=_build_execution_state(),
        )
        == 0
    )
    wrong_version = tmp_path / "wrong-version.json"
    wrong_version.write_text(json.dumps({"version": 99}), encoding="utf-8")
    assert (
        load_pipeline_state(
            str(wrong_version),
            runtime_state=runtime_state,
            execution_state=_build_execution_state(),
        )
        == 0
    )


def test_load_pipeline_state_rejects_negative_cursor_and_restores_idle_runtime(tmp_path) -> None:
    negative = tmp_path / "negative.json"
    negative.write_text(
        _checkpoint_json({"completed_field_index": -1}),
        encoding="utf-8",
    )
    runtime_state = RuntimeConcurrencyState(max_workers=3, runtime_max_workers=1)
    assert (
        load_pipeline_state(
            str(negative),
            runtime_state=runtime_state,
            execution_state=_build_execution_state(),
        )
        == 0
    )

    idle = tmp_path / "idle.json"
    idle.write_text(
        _checkpoint_json(
            {
                "completed_field_index": 2,
                "remaining_cooldown_seconds": 0,
                "runtime_max_workers": 1,
                "last_submission_at": 10,
            }
        ),
        encoding="utf-8",
    )
    execution_state = _build_execution_state()
    with patch("alpha.core.checkpoint.time.monotonic", return_value=100.0):
        resumed = load_pipeline_state(
            str(idle),
            runtime_state=runtime_state,
            execution_state=execution_state,
        )

    assert resumed == 2
    assert runtime_state.runtime_max_workers == 3
    assert runtime_state.cooldown_until == 0
    assert execution_state.last_submission_at >= 0


def test_restore_pending_simulations_sanitizes_rows_and_derives_simulation_id() -> None:
    restored, retry_from_start = checkpoint_module._restore_pending_simulations(
        [
            "invalid",
            {"field_id": "missing-required"},
            {
                "field_id": "retry",
                "template_name": "template",
                "expression": "rank(retry)",
                "settings_fingerprint": "settings",
            },
            {
                "field_id": "f1",
                "template_name": "template",
                "expression": "rank(f1)",
                "settings_fingerprint": "settings",
                "simulation_location": "/simulations/sim-derived",
                "settings": "invalid",
            },
        ]
    )

    assert retry_from_start == 1
    assert len(restored) == 1
    assert restored[0].field_name == "f1"
    assert restored[0].field_type == "UNKNOWN"
    assert restored[0].simulation_id == "sim-derived"
    assert restored[0].settings == {}


def test_save_pipeline_state_handles_empty_path_and_persists_cooldown(tmp_path) -> None:
    execution_state = _build_execution_state()
    execution_state.future_queue.replace_resumable_batch(
        [
            PendingFutureContext(
                field_id="f1",
                template_name="template",
                expression="rank(f1)",
                settings_fingerprint="settings",
                simulation_location="/simulations/sim-1",
            )
        ]
    )
    runtime_state = RuntimeConcurrencyState(max_workers=4, runtime_max_workers=1)
    runtime_state.cooldown_until = 130.0

    assert not save_pipeline_state(
        "",
        completed_field_index=0,
        execution_state=execution_state,
        runtime_state=runtime_state,
    )
    state_file = tmp_path / "nested" / "state.json"
    with patch("alpha.core.checkpoint.time.monotonic", return_value=100.0):
        assert save_pipeline_state(
            str(state_file),
            completed_field_index=1,
            execution_state=execution_state,
            runtime_state=runtime_state,
            field_id="f1",
        )

    payload = json.loads(state_file.read_text(encoding="utf-8"))
    assert payload["remaining_cooldown_seconds"] == 30.0
    assert payload["pending_simulations"][0]["simulation_location"] == "/simulations/sim-1"


def test_interrupt_report_and_delete_pipeline_state(tmp_path) -> None:
    execution_state = _build_execution_state()
    execution_state.future_queue.replace_resumable_batch(
        [
            PendingFutureContext(
                field_id="f1",
                template_name="template",
                expression="rank(f1)",
                settings_fingerprint="settings",
                simulation_location="/simulations/sim-1",
                simulation_id="sim-1",
            )
        ]
    )
    runtime_state = RuntimeConcurrencyState(max_workers=2, runtime_max_workers=1)
    report = tmp_path / "interrupt.json"

    assert not save_interrupt_report(
        "",
        execution_state=execution_state,
        runtime_state=runtime_state,
    )
    assert save_interrupt_report(
        str(report),
        execution_state=execution_state,
        runtime_state=runtime_state,
        field_id="f1",
        remaining_fields=3,
        reason="KeyboardInterrupt",
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["reason"] == "KeyboardInterrupt"
    assert payload["pending_count"] == 1
    assert payload["pending_summary"][0]["simulation_id"] == "sim-1"

    delete_pipeline_state(str(report))
    assert not report.exists()
    delete_pipeline_state(str(report))


def test_atomic_save_reports_directory_creation_failure(tmp_path, caplog) -> None:
    with patch("alpha.core.checkpoint.os.makedirs", side_effect=OSError("read only")):
        assert not checkpoint_module._atomic_save(
            str(tmp_path / "state.json"),
            {"version": 1},
        )

    assert "failed to save" in caplog.text
    assert "read only" in caplog.text
