"""
管道状态与检查点持久化模块

本模块实现可恢复状态（state_file）和中断诊断报告（interrupt_report_file），
支持断点续传：重启时恢复远端模拟和冷却状态。

模块内容：
    - save_pipeline_state: 保存恢复远端模拟所需的运行状态
    - load_pipeline_state: 启动时加载上次进度
    - save_interrupt_report: 崩溃/中断时保存诊断报告（含待处理任务元数据）
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
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
    "load_pipeline_state",
    "save_interrupt_report",
    "save_pipeline_state",
]

logger = logging.getLogger(__name__)

STATE_VERSION = 3


# ============================================================================
# 状态保存
# ============================================================================


def save_pipeline_state(
    state_file: str,
    *,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    identity: CheckpointIdentity,
) -> bool:
    """
    原子性地保存恢复远端模拟所需的管道运行状态。

    breadth-first 调度会从持久化结果和可恢复 simulation 重新规划；因此不
    保存字段游标或最近字段等与恢复无关的调度诊断信息。

    Args:
        state_file: 状态文件的绝对路径。
        execution_state: 当前 ExecutionState 实例。
        runtime_state: 当前 RuntimeConcurrencyState 实例。

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
        "pending_simulations": _payloads.serialize_pending_simulations(execution_state),
        "runtime_max_workers": runtime_state.runtime_max_workers,
        "remaining_cooldown_seconds": round(remaining_cooldown, 3),
        "last_submission_at": execution_state.last_submission_at,
        "persisted_result_count": result_ledger.persisted_result_count,
    }

    return _files.atomic_save(state_file, payload)


# ============================================================================
# 状态加载
# ============================================================================


def load_pipeline_state(
    state_file: str,
    *,
    runtime_state: RuntimeConcurrencyState,
    execution_state: ExecutionState,
    identity: CheckpointIdentity,
) -> None:
    """
    启动时加载上次管道运行状态，恢复进度和拥塞控制信息。

    将持久化的状态合并到 execution_state 和 runtime_state 中。旧 checkpoint
    中的字段游标会被安全忽略，因为当前 breadth-first 调度由结果和可恢复
    simulation 重新规划。

    Args:
        state_file: 状态文件的绝对路径。
        runtime_state: RuntimeConcurrencyState 实例（会被修改）。
        execution_state: ExecutionState 实例（会被修改）。

    """
    if not state_file or not os.path.exists(state_file):
        return
    _loading.load_pipeline_state(
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
        reason: 保存原因（如 "KeyboardInterrupt"、"Exception"）。

    Returns:
        bool: 保存成功返回 True，失败返回 False。
    """
    if not interrupt_report_file:
        return False

    # 收集待处理任务摘要
    pending_contexts = _payloads.all_pending_contexts(execution_state)
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
        "result_count": len(result_ledger.results),
        "attempted_keys_count": len(execution_state.attempted_keys),
        "pending_count": len(pending_contexts),
        "pending_summary": pending_summary,
        "pending_simulations": _payloads.serialize_pending_simulations(execution_state),
        "template_stats": dict(execution_state.template_stats),
        "runtime_max_workers": runtime_state.runtime_max_workers,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    success = _files.atomic_save(interrupt_report_file, payload)
    if success:
        logger.info(
            "[checkpoint] saved interrupt report to %s (pending=%d, reason=%s)",
            interrupt_report_file,
            len(pending_contexts),
            reason,
        )
    return success
