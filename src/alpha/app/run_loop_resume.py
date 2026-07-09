"""Resume and persistence helpers for the run loop."""

from __future__ import annotations

import logging
from typing import Any

from ..config.constants import SENTINEL_UNKNOWN
from ..core import load_pipeline_state, save_checkpoint, save_pipeline_state
from ..models.domain import TemplateField
from ..runtime import ExecutionState, RuntimeConcurrencyState
from ..utils.helpers import first_non_empty

logger = logging.getLogger(__name__)


def build_field_resume_positions(fields: list[TemplateField]) -> dict[str, int]:
    """Build stable original-order resume positions for each field id."""
    return {
        str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)): (index + 1)
        for index, field in enumerate(fields)
    }


def clamp_resume_index(resume_index: int, total_fields: int) -> int:
    """Clamp resume index into the current field range while preserving terminal completion."""
    if total_fields <= 0:
        return 0
    return max(0, min(resume_index, total_fields))


def normalize_resume_index(resume_index: int, total_fields: int) -> int:
    """Normalize resume index modulo current field count for legacy callers."""
    if total_fields <= 0:
        return 0
    return resume_index % total_fields


def restore_fields_from_state(
    *,
    fields: list[TemplateField],
    state_file: str,
    runtime_state: RuntimeConcurrencyState,
    execution_state: ExecutionState,
    clamp_resume_index_fn,
) -> tuple[list[TemplateField], int]:
    """Restore field start position from pipeline state and rotate field order accordingly."""
    resumed_index = 0
    if not state_file:
        return fields, resumed_index
    resumed_index = load_pipeline_state(
        state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
    )
    if resumed_index <= 0:
        return fields, resumed_index
    resumed_index = clamp_resume_index_fn(resumed_index, len(fields))
    if resumed_index >= len(fields):
        logger.info(
            "[resume] state_file 记录的字段进度已覆盖全部 %d 个字段，直接进入收尾阶段",
            len(fields),
        )
        return [], resumed_index
    logger.info(
        "[resume] 从字段索引 %d/%d 附近继续 (优先从该位置恢复，但不会丢掉更早字段)",
        resumed_index + 1,
        len(fields),
    )
    return fields[resumed_index:] + fields[:resumed_index], resumed_index


def persist_field_progress(
    *,
    state_file: str,
    field_id: str,
    field_index: int,
    original_fields: list[TemplateField],
    field_resume_positions: dict[str, int],
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
) -> None:
    """Persist pipeline state after completing one field."""
    if not state_file:
        return
    completed_index = field_resume_positions.get(field_id, field_index)
    completed_index = max(0, min(completed_index, len(original_fields)))
    save_pipeline_state(
        state_file,
        completed_field_index=completed_index,
        execution_state=execution_state,
        runtime_state=runtime_state,
        field_id=field_id,
    )


def save_runtime_checkpoint(
    *,
    checkpoint_file: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    last_field_id: str,
    fields: list[TemplateField],
    reason: str,
) -> None:
    """Persist a checkpoint on interrupt or exception."""
    if not checkpoint_file:
        return
    save_checkpoint(
        checkpoint_file,
        execution_state=execution_state,
        runtime_state=runtime_state,
        field_id=last_field_id or "",
        remaining_fields=max(0, len(fields)),
        reason=reason,
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
    save_pipeline_state(
        state_file,
        completed_field_index=max(0, total_fields),
        execution_state=execution_state,
        runtime_state=runtime_state,
        field_id=last_field_id,
    )


ResumeIndexClamp = Any
