"""
管道状态与检查点持久化模块

本模块实现可恢复状态（state_file）和中断诊断报告（interrupt_report_file），
支持断点续传：重启时跳过已完成的字段、恢复远端模拟、冷却状态和模板统计数据。

模块内容：
    - save_pipeline_state: 在每个字段完成后保存运行进度
    - load_pipeline_state: 启动时加载上次进度
    - save_interrupt_report: 崩溃/中断时保存诊断报告（含待处理任务元数据）
"""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone
import json
import logging
import math
import os
import time
from typing import Any

from ..config.constants import CHECKPOINT_PENDING_FUTURES_LIMIT, CHECKPOINT_RESUME_SAFETY_SECONDS
from ..runtime.contexts import PendingFutureContext
from ..runtime.state import ExecutionState, RuntimeConcurrencyState

logger = logging.getLogger(__name__)

STATE_VERSION = 1
_TEMPLATE_STAT_COUNT_FIELDS = (
    "attempted",
    "submittable",
    "submitted",
    "errors",
    "simulated",
    "queue_timeouts",
    "low_sharpe",
    "low_fitness",
    "concentrated_weight",
    "low_sub_universe_sharpe",
)


def _non_negative_int(value: object) -> int | None:
    """Return a safe non-negative integer or None for unusable persisted values."""
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = int(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _restore_template_stats(payload: object) -> dict[str, dict[str, Any]]:
    """Restore template statistics with safe numeric counters."""
    if not isinstance(payload, dict):
        return {}
    restored: dict[str, dict[str, Any]] = {}
    for template_name, raw_stat in payload.items():
        normalized_name = str(template_name or "").strip()
        if not normalized_name or not isinstance(raw_stat, dict):
            continue
        stat = dict(raw_stat)
        for field_name in _TEMPLATE_STAT_COUNT_FIELDS:
            stat[field_name] = _non_negative_int(stat.get(field_name)) or 0
        restored[normalized_name] = stat
    return restored


def _all_pending_contexts(execution_state: ExecutionState) -> list[PendingFutureContext]:
    """Return submitted and not-yet-resubmitted simulation contexts."""
    return [
        *execution_state.pending_futures.values(),
        *execution_state.resumable_simulations,
    ]


def _serialize_pending_simulations(
    execution_state: ExecutionState,
) -> list[dict[str, Any]]:
    """Serialize inflight metadata required to resume remote simulation polling."""
    return [
        {
            "field_id": str(getattr(meta, "field_id", "") or ""),
            "field_name": str(getattr(meta, "field_name", "") or ""),
            "field_type": str(getattr(meta, "field_type", "") or ""),
            "template_name": str(getattr(meta, "template_name", "") or ""),
            "template_family": str(getattr(meta, "template_family", "") or ""),
            "template_stage": str(getattr(meta, "template_stage", "") or ""),
            "template_role": str(getattr(meta, "template_role", "") or ""),
            "template_activation_scope": str(getattr(meta, "template_activation_scope", "") or ""),
            "policy_version": str(getattr(meta, "policy_version", "") or ""),
            "expression": str(getattr(meta, "expression", "") or ""),
            "settings_fingerprint": str(getattr(meta, "settings_fingerprint", "") or ""),
            "settings": dict(getattr(meta, "settings", {}) or {}),
            "simulation_location": str(getattr(meta, "simulation_location", "") or ""),
            "simulation_id": str(getattr(meta, "simulation_id", "") or ""),
        }
        for meta in _all_pending_contexts(execution_state)
    ]


def _restore_pending_simulations(
    payload: object,
) -> tuple[list[PendingFutureContext], int]:
    """Restore resumable simulations and count entries that require recreation."""
    restored: list[PendingFutureContext] = []
    retry_from_start = 0
    if not isinstance(payload, list):
        return restored, retry_from_start
    for item in payload:
        if not isinstance(item, dict):
            continue
        field_id = str(item.get("field_id", "") or "").strip()
        template_name = str(item.get("template_name", "") or "").strip()
        expression = str(item.get("expression", "") or "").strip()
        settings_fingerprint = str(item.get("settings_fingerprint", "") or "").strip()
        if not field_id or not template_name or not expression or not settings_fingerprint:
            continue
        simulation_location = str(item.get("simulation_location", "") or "").strip()
        if not simulation_location:
            retry_from_start += 1
            continue
        simulation_id = str(item.get("simulation_id", "") or "").strip()
        if not simulation_id:
            simulation_id = simulation_location.rstrip("/").rsplit("/", 1)[-1]
        restored.append(
            PendingFutureContext(
                field_id=field_id,
                field_name=str(item.get("field_name", "") or field_id),
                field_type=str(item.get("field_type", "") or "UNKNOWN"),
                template_name=template_name,
                template_family=str(item.get("template_family", "") or ""),
                template_stage=str(item.get("template_stage", "") or ""),
                template_role=str(item.get("template_role", "") or ""),
                template_activation_scope=str(item.get("template_activation_scope", "") or ""),
                policy_version=str(item.get("policy_version", "") or ""),
                expression=expression,
                settings_fingerprint=settings_fingerprint,
                settings=dict(item.get("settings", {}))
                if isinstance(item.get("settings"), dict)
                else {},
                simulation_location=simulation_location,
                simulation_id=simulation_id,
            )
        )
    return restored, retry_from_start


# ============================================================================
# 状态保存
# ============================================================================


def save_pipeline_state(
    state_file: str,
    *,
    completed_field_index: int,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    field_id: str = "",
) -> bool:
    """
    在每个字段完成后原子性地保存管道运行状态。

    保存当前进度、拥塞控制状态和模板统计，便于重启时继续执行。

    Args:
        state_file: 状态文件的绝对路径。
        completed_field_index: 已完成字段的 0-based 索引（即下一个字段索引）。
        execution_state: 当前 ExecutionState 实例。
        runtime_state: 当前 RuntimeConcurrencyState 实例。
        field_id: 当前正在处理的字段 ID（用于验证）。

    Returns:
        bool: 保存成功返回 True，失败返回 False。
    """
    if not state_file:
        return False

    # 计算剩余冷却时间（用时间差，而非绝对单调钟）
    remaining_cooldown = 0.0
    now_mono = time.monotonic()
    if runtime_state.cooldown_until > 0 and now_mono < runtime_state.cooldown_until:
        remaining_cooldown = runtime_state.cooldown_until - now_mono

    payload: dict[str, Any] = {
        "version": STATE_VERSION,
        "completed_field_index": completed_field_index,
        "last_field_id": field_id,
        "pending_simulations": _serialize_pending_simulations(execution_state),
        "runtime_max_workers": runtime_state.runtime_max_workers,
        "remaining_cooldown_seconds": round(remaining_cooldown, 3),
        "template_stats": dict(execution_state.template_stats),
        "last_submission_at": execution_state.last_submission_at,
        "result_count": len(execution_state.results),
        "attempted_keys_count": len(execution_state.attempted_keys),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    return _atomic_save(state_file, payload)


# ============================================================================
# 状态加载
# ============================================================================


def load_pipeline_state(
    state_file: str,
    *,
    runtime_state: RuntimeConcurrencyState,
    execution_state: ExecutionState,
) -> int:
    """
    启动时加载上次管道运行状态，恢复进度和拥塞控制信息。

    将持久化的状态合并到 execution_state 和 runtime_state 中，
    返回已完成字段索引，调用方据此跳过已处理的字段。

    Args:
        state_file: 状态文件的绝对路径。
        runtime_state: RuntimeConcurrencyState 实例（会被修改）。
        execution_state: ExecutionState 实例（会被修改）。

    Returns:
        int: 已完成字段的 0-based 索引。0 表示从头开始。
    """
    if not state_file or not os.path.exists(state_file):
        return 0

    try:
        with open(state_file, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        logger.warning("[checkpoint] failed to read state file %s: %s", state_file, exc)
        return 0

    if not isinstance(payload, dict) or payload.get("version") != STATE_VERSION:
        logger.info("[checkpoint] state file version mismatch, starting fresh")
        return 0

    try:
        completed_index = int(payload.get("completed_field_index", 0))
        remaining = float(payload.get("remaining_cooldown_seconds", 0))
        runtime_max_workers = int(payload.get("runtime_max_workers", runtime_state.max_workers))
        last_submission = float(payload.get("last_submission_at", 0))
    except (TypeError, ValueError) as exc:
        logger.warning("[checkpoint] invalid state payload in %s: %s", state_file, exc)
        return 0

    if not math.isfinite(remaining) or remaining < 0:
        logger.warning(
            "[checkpoint] invalid remaining cooldown in %s: %s",
            state_file,
            remaining,
        )
        remaining = 0.0

    if completed_index < 0:
        logger.warning(
            "[checkpoint] invalid negative completed index in %s: %d",
            state_file,
            completed_index,
        )
        return 0

    # 平台拥塞是瞬时全局状态，不从 checkpoint 恢复字段级跳过信息。
    execution_state.reset_transient_queue_state()

    pending_payload = payload.get("pending_simulations")
    if pending_payload is None:
        pending_payload = payload.get("pending_template_keys")
    resumable_simulations, retry_from_start = _restore_pending_simulations(pending_payload)
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
    execution_state.resumable_simulations = resumable_simulations
    if retry_from_start:
        completed_index = 0
        logger.warning(
            "[checkpoint] %d pending simulations had no Location; restarting field scheduling",
            retry_from_start,
        )

    # 恢复模板统计
    execution_state.template_stats = _restore_template_stats(payload.get("template_stats"))

    # 恢复冷却状态（用剩余秒数重建绝对单调钟）
    if remaining > 0:
        runtime_state.cooldown_until = time.monotonic() + remaining
        runtime_state.runtime_max_workers = max(
            1,
            min(runtime_max_workers, max(1, runtime_state.max_workers)),
        )
    else:
        runtime_state.cooldown_until = 0.0
        runtime_state.runtime_max_workers = runtime_state.max_workers

    # 恢复上次提交时间（需注意单调钟在进程重启后不连续）
    if last_submission > 0:
        # 保守估计：减去一个安全余量，避免立即节流
        execution_state.last_submission_at = max(
            0, time.monotonic() - CHECKPOINT_RESUME_SAFETY_SECONDS
        )

    logger.info(
        "[checkpoint] resumed from state_file=%s completed=%d "
        "results=%d attempted=%d resumable=%d already_completed=%d retry_from_start=%d "
        "cooldown=%.1fs",
        state_file,
        completed_index,
        payload.get("result_count", 0),
        payload.get("attempted_keys_count", 0),
        len(resumable_simulations),
        already_completed,
        retry_from_start,
        remaining,
    )

    return completed_index


# ============================================================================
# 崩溃检查点
# ============================================================================


def save_interrupt_report(
    interrupt_report_file: str,
    *,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    field_id: str = "",
    remaining_fields: int = 0,
    reason: str = "",
) -> bool:
    """
    崩溃/中断时保存详细检查点，包含待处理任务元数据。

    与 state_file 不同，该文件只用于诊断中断现场，不参与恢复；它会记录当前正在执行的
    任务信息，便于排查崩溃原因。

    Args:
        interrupt_report_file: 中断诊断报告的绝对路径。
        execution_state: 当前 ExecutionState 实例。
        runtime_state: 当前 RuntimeConcurrencyState 实例。
        field_id: 当前字段 ID。
        remaining_fields: 尚未处理的字段数。
        reason: 保存原因（如 "KeyboardInterrupt"、"Exception"）。

    Returns:
        bool: 保存成功返回 True，失败返回 False。
    """
    if not interrupt_report_file:
        return False

    # 收集待处理任务摘要
    pending_contexts = _all_pending_contexts(execution_state)
    pending_summary: list[dict[str, str]] = [
        {
            "field_id": str(meta.field_id),
            "template_name": str(meta.template_name),
            "expression": str(meta.expression),
            "settings_fingerprint": str(meta.settings_fingerprint),
            "simulation_location": str(meta.simulation_location),
            "simulation_id": str(meta.simulation_id),
        }
        for meta in pending_contexts[-CHECKPOINT_PENDING_FUTURES_LIMIT:]
    ]

    payload: dict[str, Any] = {
        "version": STATE_VERSION,
        "reason": reason,
        "field_id": field_id,
        "remaining_fields": remaining_fields,
        "result_count": len(execution_state.results),
        "attempted_keys_count": len(execution_state.attempted_keys),
        "pending_count": len(pending_contexts),
        "pending_summary": pending_summary,
        "pending_simulations": _serialize_pending_simulations(execution_state),
        "template_stats": dict(execution_state.template_stats),
        "runtime_max_workers": runtime_state.runtime_max_workers,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    success = _atomic_save(interrupt_report_file, payload)
    if success:
        logger.info(
            "[checkpoint] saved interrupt report to %s (pending=%d, reason=%s)",
            interrupt_report_file,
            len(pending_contexts),
            reason,
        )
    return success


def delete_pipeline_state(state_file: str) -> None:
    """运行完成后删除状态文件（表示一次完整运行结束）。"""
    if state_file and os.path.exists(state_file):
        with suppress(OSError):
            os.remove(state_file)
            logger.debug("[checkpoint] removed completed state file %s", state_file)


# ============================================================================
# 内部辅助
# ============================================================================


def _atomic_save(path: str, payload: dict[str, Any]) -> bool:
    """原子性保存 JSON 到文件（先写临时文件，再替换）。"""
    import tempfile

    if not path:
        return False
    fd: int | None = None
    tmp = ""
    try:
        directory = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp_state_", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as exc:
        logger.debug("[checkpoint] failed to save %s: %s", path, exc)
        return False
    finally:
        if fd is not None:
            with suppress(OSError):
                os.close(fd)
        with suppress(OSError):
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
