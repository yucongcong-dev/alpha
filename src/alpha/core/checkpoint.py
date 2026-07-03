"""
管道状态与检查点持久化模块

本模块实现中间状态缓存（state_file）和崩溃检查点（checkpoint_file），
支持断点续传：重启时跳过已完成的字段、恢复拥塞控制状态和模板统计数据。

模块内容：
    - save_pipeline_state: 在每个字段完成后保存运行进度
    - load_pipeline_state: 启动时加载上次进度
    - save_checkpoint: 崩溃/中断时保存详细检查点（含待处理任务元数据）
"""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any

from ..config.constants import CHECKPOINT_PENDING_FUTURES_LIMIT, CHECKPOINT_RESUME_SAFETY_SECONDS
from ..models.runtime import ExecutionState, RuntimeConcurrencyState

logger = logging.getLogger(__name__)

STATE_VERSION = 1


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
        "field_queue_busy_counts": dict(execution_state.field_queue_busy_counts),
        "skipped_fields_due_to_queue": sorted(execution_state.skipped_fields_due_to_queue),
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

    if completed_index <= 0:
        return 0

    # 恢复拥塞状态
    queue_busy = payload.get("field_queue_busy_counts", {})
    if isinstance(queue_busy, dict):
        execution_state.field_queue_busy_counts = queue_busy

    skipped = payload.get("skipped_fields_due_to_queue", [])
    if isinstance(skipped, list):
        execution_state.skipped_fields_due_to_queue = set(skipped)

    # 恢复模板统计
    template_stats = payload.get("template_stats", {})
    if isinstance(template_stats, dict):
        execution_state.template_stats = template_stats

    # 恢复冷却状态（用剩余秒数重建绝对单调钟）
    if remaining > 0:
        runtime_state.cooldown_until = time.monotonic() + remaining
        runtime_state.runtime_max_workers = runtime_max_workers
    else:
        runtime_state.cooldown_until = 0.0
        runtime_state.runtime_max_workers = runtime_state.max_workers

    # 恢复上次提交时间（需注意单调钟在进程重启后不连续）
    if last_submission > 0:
        # 保守估计：减去一个安全余量，避免立即节流
        execution_state.last_submission_at = max(0, time.monotonic() - CHECKPOINT_RESUME_SAFETY_SECONDS)

    logger.info(
        "[checkpoint] resumed from state_file=%s completed=%d "
        "results=%d attempted=%d skipped_fields=%d cooldown=%.1fs",
        state_file,
        completed_index,
        payload.get("result_count", 0),
        payload.get("attempted_keys_count", 0),
        len(execution_state.skipped_fields_due_to_queue),
        remaining,
    )

    return completed_index


# ============================================================================
# 崩溃检查点
# ============================================================================


def save_checkpoint(
    checkpoint_file: str,
    *,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    field_id: str = "",
    remaining_fields: int = 0,
    reason: str = "",
) -> bool:
    """
    崩溃/中断时保存详细检查点，包含待处理任务元数据。

    与 state_file 不同，checkpoint_file 还会记录当前正在执行的
    任务信息，便于排查崩溃原因。

    Args:
        checkpoint_file: 检查点文件的绝对路径。
        execution_state: 当前 ExecutionState 实例。
        runtime_state: 当前 RuntimeConcurrencyState 实例。
        field_id: 当前字段 ID。
        remaining_fields: 尚未处理的字段数。
        reason: 保存原因（如 "KeyboardInterrupt"、"Exception"）。

    Returns:
        bool: 保存成功返回 True，失败返回 False。
    """
    if not checkpoint_file:
        return False

    # 收集待处理任务摘要
    pending_summary: list[dict[str, str]] = [
        {
            "field_id": str(meta.field_id),
            "template_name": str(meta.template_name),
            "expression": str(meta.expression),
        }
        for meta in list(execution_state.pending_futures.values())[-CHECKPOINT_PENDING_FUTURES_LIMIT:]
    ]

    payload: dict[str, Any] = {
        "version": STATE_VERSION,
        "reason": reason,
        "field_id": field_id,
        "remaining_fields": remaining_fields,
        "result_count": len(execution_state.results),
        "attempted_keys_count": len(execution_state.attempted_keys),
        "pending_count": len(execution_state.pending_futures),
        "pending_summary": pending_summary,
        "field_queue_busy_counts": dict(execution_state.field_queue_busy_counts),
        "skipped_fields_due_to_queue": sorted(execution_state.skipped_fields_due_to_queue),
        "template_stats": dict(execution_state.template_stats),
        "runtime_max_workers": runtime_state.runtime_max_workers,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    success = _atomic_save(checkpoint_file, payload)
    if success:
        logger.info(
            "[checkpoint] saved crash checkpoint to %s (pending=%d, reason=%s)",
            checkpoint_file,
            len(execution_state.pending_futures),
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
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_state_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as exc:
        logger.debug("[checkpoint] failed to save %s: %s", path, exc)
        return False
    finally:
        with suppress(OSError):
            if os.path.exists(tmp):
                os.remove(tmp)
