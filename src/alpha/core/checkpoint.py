"""
管道状态与检查点持久化模块

本模块实现可恢复状态（state_file）和中断诊断报告（interrupt_report_file），
支持断点续传：重启时跳过已完成的字段、恢复远端模拟和冷却状态。

模块内容：
    - save_pipeline_state: 在每个字段完成后保存运行进度
    - load_pipeline_state: 启动时加载上次进度
    - save_interrupt_report: 崩溃/中断时保存诊断报告（含待处理任务元数据）
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Any

from ..config._constants_thresholds import CHECKPOINT_PENDING_FUTURES_LIMIT
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import CheckpointIdentity
from ..runtime.state import ExecutionState
from . import checkpoint_files as _files
from . import checkpoint_loading as _loading
from . import checkpoint_payloads as _payloads

__all__ = [
    "_non_negative_int",
    "_restore_pending_simulations",
    "delete_pipeline_state",
    "load_pipeline_state",
    "save_interrupt_report",
    "save_pipeline_state",
]

logger = logging.getLogger(__name__)

STATE_VERSION = 3
os = _files.os

_all_pending_contexts = _payloads.all_pending_contexts
_atomic_save = _files.atomic_save
delete_pipeline_state = _files.delete_pipeline_state
_non_negative_int = _payloads.non_negative_int
_restore_pending_simulations = _payloads.restore_pending_simulations
_serialize_pending_simulations = _payloads.serialize_pending_simulations


# ============================================================================
# 状态保存
# ============================================================================


def save_pipeline_state(
    state_file: str,
    *,
    completed_field_index: int,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    identity: CheckpointIdentity,
    field_id: str = "",
) -> bool:
    """
    在每个字段完成后原子性地保存管道运行状态。

    保存当前进度和拥塞控制状态，便于重启时继续执行。

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

    result_ledger = execution_state.result_ledger
    payload: dict[str, Any] = {
        "version": STATE_VERSION,
        "run_fingerprint": identity.run_fingerprint,
        "completed_field_index": completed_field_index,
        "last_field_id": field_id,
        "pending_simulations": _serialize_pending_simulations(execution_state),
        "runtime_max_workers": runtime_state.runtime_max_workers,
        "remaining_cooldown_seconds": round(remaining_cooldown, 3),
        "last_submission_at": execution_state.last_submission_at,
        "result_count": len(result_ledger.results),
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
    identity: CheckpointIdentity,
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
    return _loading.load_pipeline_state(
        state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
        identity=identity,
        state_version=STATE_VERSION,
        monotonic=time.monotonic,
        log=logger,
    )


# ============================================================================
# 崩溃检查点
# ============================================================================


def save_interrupt_report(
    interrupt_report_file: str,
    *,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    identity: CheckpointIdentity,
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

    result_ledger = execution_state.result_ledger
    payload: dict[str, Any] = {
        "version": STATE_VERSION,
        "run_fingerprint": identity.run_fingerprint,
        "reason": reason,
        "field_id": field_id,
        "remaining_fields": remaining_fields,
        "result_count": len(result_ledger.results),
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
