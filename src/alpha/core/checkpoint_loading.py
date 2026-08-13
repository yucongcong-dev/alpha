"""Checkpoint state loading and runtime restoration helpers."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
import math
from typing import Any

from ..config._constants_thresholds import CHECKPOINT_RESUME_SAFETY_SECONDS
from ..exceptions import CheckpointConsistencyError
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import CheckpointIdentity
from ..runtime.state import ExecutionState
from . import checkpoint_payloads as _payloads

logger = logging.getLogger(__name__)


def _load_checkpoint_payload(
    state_file: str,
    *,
    state_version: int,
    log: logging.Logger,
) -> dict[str, Any] | None:
    try:
        with open(state_file, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        log.warning("[checkpoint] failed to read state file %s: %s", state_file, exc)
        return None

    if not isinstance(payload, dict) or payload.get("version") != state_version:
        log.info("[checkpoint] state file version mismatch, starting fresh")
        return None
    return payload


def _parse_resume_scalars(
    payload: dict[str, Any],
    *,
    state_file: str,
    runtime_state: RuntimeConcurrencyState,
    log: logging.Logger,
) -> tuple[int, float, int, float] | None:
    try:
        completed_index = int(payload.get("completed_field_index", 0))
        remaining = float(payload.get("remaining_cooldown_seconds", 0))
        runtime_max_workers = int(payload.get("runtime_max_workers", runtime_state.max_workers))
        last_submission = float(payload.get("last_submission_at", 0))
    except (TypeError, ValueError) as exc:
        log.warning("[checkpoint] invalid state payload in %s: %s", state_file, exc)
        return None

    if not math.isfinite(remaining) or remaining < 0:
        log.warning(
            "[checkpoint] invalid remaining cooldown in %s: %s",
            state_file,
            remaining,
        )
        remaining = 0.0

    if completed_index < 0:
        log.warning(
            "[checkpoint] invalid negative completed index in %s: %d",
            state_file,
            completed_index,
        )
        return None

    return completed_index, remaining, runtime_max_workers, last_submission


def _restore_resumable_simulations(
    payload: dict[str, Any],
    *,
    execution_state: ExecutionState,
) -> tuple[int, int]:
    pending_payload = payload.get("pending_simulations")
    if pending_payload is None:
        pending_payload = payload.get("pending_template_keys")
    resumable_simulations, retry_from_start = _payloads.restore_pending_simulations(pending_payload)
    restored_before_dedup = len(resumable_simulations)
    resumable_simulations = [
        pending
        for pending in resumable_simulations
        if (
            pending.field_id,
            pending.template_name,
            pending.expression,
            pending.settings_fingerprint,
        )
        not in execution_state.attempted_keys
    ]
    already_completed = restored_before_dedup - len(resumable_simulations)
    execution_state.future_queue.replace_resumable_batch(resumable_simulations)
    return already_completed, retry_from_start


def _restore_runtime_cooldown(
    *,
    remaining: float,
    runtime_max_workers: int,
    runtime_state: RuntimeConcurrencyState,
    monotonic: Callable[[], float],
) -> None:
    if remaining > 0:
        runtime_state.cooldown_until = monotonic() + remaining
        runtime_state.runtime_max_workers = max(
            1,
            min(runtime_max_workers, max(1, runtime_state.max_workers)),
        )
    else:
        runtime_state.cooldown_until = 0.0
        runtime_state.runtime_max_workers = runtime_state.max_workers


def _has_compatible_result_journal(
    payload: dict[str, Any],
    *,
    execution_state: ExecutionState,
    state_file: str,
    log: logging.Logger,
) -> bool:
    """Reject a checkpoint that expects more durable rows than startup loaded."""
    persisted_result_count = _payloads.non_negative_int(payload.get("persisted_result_count"))
    if persisted_result_count is None:
        return True
    local_result_count = execution_state.result_ledger.persisted_result_count
    if local_result_count < persisted_result_count:
        message = (
            "result journal is behind checkpoint in "
            f"{state_file}; local={local_result_count} "
            f"checkpoint={persisted_result_count}"
        )
        log.error(
            "[checkpoint] result journal is behind checkpoint in %s; "
            "local=%d checkpoint=%d; refusing stale pending simulations",
            state_file,
            local_result_count,
            persisted_result_count,
        )
        raise CheckpointConsistencyError(message)
    if local_result_count > persisted_result_count:
        log.info(
            "[checkpoint] result journal is ahead of checkpoint in %s; "
            "local=%d checkpoint=%d; using local durable results",
            state_file,
            local_result_count,
            persisted_result_count,
        )
    return True


def load_pipeline_state(
    state_file: str,
    *,
    runtime_state: RuntimeConcurrencyState,
    execution_state: ExecutionState,
    identity: CheckpointIdentity,
    state_version: int,
    monotonic: Callable[[], float],
    log: logging.Logger = logger,
) -> int:
    """Load persisted checkpoint state into runtime and execution state objects."""
    payload = _load_checkpoint_payload(
        state_file,
        state_version=state_version,
        log=log,
    )
    if payload is None:
        return 0
    saved_identity = str(payload.get("run_fingerprint", "") or "")
    if saved_identity != identity.run_fingerprint:
        log.warning("[checkpoint] run identity mismatch in %s; starting fresh", state_file)
        return 0
    _has_compatible_result_journal(
        payload,
        execution_state=execution_state,
        state_file=state_file,
        log=log,
    )

    parsed = _parse_resume_scalars(
        payload,
        state_file=state_file,
        runtime_state=runtime_state,
        log=log,
    )
    if parsed is None:
        return 0
    completed_index, remaining, runtime_max_workers, last_submission = parsed

    # 平台拥塞是瞬时全局状态，不从 checkpoint 恢复字段级跳过信息。
    execution_state.reset_transient_queue_state()

    already_completed, retry_from_start = _restore_resumable_simulations(
        payload,
        execution_state=execution_state,
    )
    if retry_from_start:
        completed_index = 0
        log.warning(
            "[checkpoint] %d pending simulations had no Location; restarting field scheduling",
            retry_from_start,
        )

    _restore_runtime_cooldown(
        remaining=remaining,
        runtime_max_workers=runtime_max_workers,
        runtime_state=runtime_state,
        monotonic=monotonic,
    )

    if last_submission > 0:
        execution_state.last_submission_at = max(
            0,
            monotonic() - CHECKPOINT_RESUME_SAFETY_SECONDS,
        )

    log.info(
        "[checkpoint] resumed from state_file=%s completed=%d "
        "results=%d attempted=%d resumable=%d already_completed=%d retry_from_start=%d "
        "cooldown=%.1fs",
        state_file,
        completed_index,
        payload.get("result_count", 0),
        payload.get("attempted_keys_count", 0),
        len(execution_state.future_queue.resumable_simulations),
        already_completed,
        retry_from_start,
        remaining,
    )

    return completed_index
