"""Resume and persistence helpers for the run loop."""

from __future__ import annotations

import logging

from ..core.checkpoint import load_pipeline_state, save_interrupt_report, save_pipeline_state
from ..models.domain import TemplateField
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import CheckpointIdentity
from ..runtime.state import ExecutionState

logger = logging.getLogger(__name__)


def restore_fields_from_state(
    *,
    fields: list[TemplateField],
    state_file: str,
    runtime_state: RuntimeConcurrencyState,
    execution_state: ExecutionState,
    identity: CheckpointIdentity,
) -> list[TemplateField]:
    """Restore runtime state while keeping breadth-first field order stable.

    The scheduler always replans every field from durable results and resumable
    simulations, so legacy field cursors never remove fields from a new round.
    """
    if not state_file:
        return fields
    load_pipeline_state(
        state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
        identity=identity,
    )
    return fields


def persist_replanning_checkpoint(
    *,
    state_file: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    identity: CheckpointIdentity,
) -> None:
    """Persist an in-progress breadth-first checkpoint for recovery."""
    if not state_file:
        return
    saved = save_pipeline_state(
        state_file,
        execution_state=execution_state,
        runtime_state=runtime_state,
        identity=identity,
    )
    if not saved:
        raise RuntimeError(f"failed to save pipeline state: {state_file}")


def save_runtime_checkpoint(
    *,
    state_file: str,
    interrupt_report_file: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    identity: CheckpointIdentity,
    diagnostic_field_id: str,
    reason: str,
) -> None:
    """Persist resumable pipeline state and a diagnostic interrupt report."""
    if state_file:
        state_saved = save_pipeline_state(
            state_file,
            execution_state=execution_state,
            runtime_state=runtime_state,
            identity=identity,
        )
        if not state_saved:
            logger.error("[checkpoint] runtime state was not saved: %s", state_file)
    if interrupt_report_file:
        report_saved = save_interrupt_report(
            interrupt_report_file,
            execution_state=execution_state,
            runtime_state=runtime_state,
            identity=identity,
            field_id=diagnostic_field_id or "",
            reason=reason,
        )
        if not report_saved:
            logger.error(
                "[checkpoint] interrupt report was not saved: %s",
                interrupt_report_file,
            )
