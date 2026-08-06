"""Resume and persistence helpers for the run loop."""

from __future__ import annotations

import logging

from ..core.checkpoint import load_pipeline_state, save_interrupt_report, save_pipeline_state
from ..models.domain import TemplateField
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.state import ExecutionState

logger = logging.getLogger(__name__)


def restore_fields_from_state(
    *,
    fields: list[TemplateField],
    state_file: str,
    runtime_state: RuntimeConcurrencyState,
    execution_state: ExecutionState,
) -> list[TemplateField]:
    """Restore runtime state while keeping breadth-first field order stable."""
    if not state_file:
        return fields
    legacy_completed_index = load_pipeline_state(
        state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
    )
    if fields and legacy_completed_index >= len(fields):
        logger.info(
            "[resume] state_file 记录的字段进度已覆盖全部 %d 个字段，直接进入收尾阶段",
            len(fields),
        )
        return []
    if legacy_completed_index > 0:
        logger.info(
            "[resume] 忽略旧字段游标 %d；breadth-first 调度由历史结果和待恢复 simulation 去重",
            legacy_completed_index,
        )
    return fields


def persist_replanning_checkpoint(
    *,
    state_file: str,
    field_id: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
) -> None:
    """Persist an in-progress breadth-first checkpoint without advancing a field cursor."""
    if not state_file:
        return
    saved = save_pipeline_state(
        state_file,
        completed_field_index=0,
        execution_state=execution_state,
        runtime_state=runtime_state,
        field_id=field_id,
    )
    if not saved:
        raise RuntimeError(f"failed to save pipeline state: {state_file}")


def save_runtime_checkpoint(
    *,
    state_file: str,
    interrupt_report_file: str,
    completed_field_index: int,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    last_field_id: str,
    fields: list[TemplateField],
    reason: str,
) -> None:
    """Persist resumable pipeline state and a diagnostic interrupt report."""
    if state_file:
        state_saved = save_pipeline_state(
            state_file,
            completed_field_index=max(0, completed_field_index),
            execution_state=execution_state,
            runtime_state=runtime_state,
            field_id=last_field_id or "",
        )
        if not state_saved:
            logger.error("[checkpoint] runtime state was not saved: %s", state_file)
    if interrupt_report_file:
        report_saved = save_interrupt_report(
            interrupt_report_file,
            execution_state=execution_state,
            runtime_state=runtime_state,
            field_id=last_field_id or "",
            remaining_fields=max(0, len(fields)),
            reason=reason,
        )
        if not report_saved:
            logger.error(
                "[checkpoint] interrupt report was not saved: %s",
                interrupt_report_file,
            )


def save_terminal_pipeline_state(
    *,
    state_file: str,
    total_fields: int,
    last_field_id: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
) -> None:
    """Persist the terminal completed-field cursor after draining all futures."""
    if not state_file:
        return
    saved = save_pipeline_state(
        state_file,
        completed_field_index=max(0, total_fields),
        execution_state=execution_state,
        runtime_state=runtime_state,
        field_id=last_field_id,
    )
    if not saved:
        raise RuntimeError(f"failed to save terminal pipeline state: {state_file}")
