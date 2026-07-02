"""
运行循环支撑模块。

承载 run_loop 中与主 while/for 编排正交的恢复、提交、排空和状态持久化辅助逻辑。
"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import logging
import time
from typing import Any

from .config import SENTINEL_UNKNOWN
from .core import (
    drain_completed_futures,
    load_pipeline_state,
    run_field_test_in_worker,
    save_checkpoint,
    save_pipeline_state,
)
from .models.base import (
    ExecutionState,
    InitializedRunContext,
    PendingFutureContext,
    RuntimeConcurrencyState,
    TemplateBuildContext,
    TemplateBuildOptions,
    ResultWriteOptions,
)
from .utils.helpers import first_non_empty

logger = logging.getLogger(__name__)


def restore_fields_from_state(
    *,
    fields: list[dict[str, Any]],
    state_file: str,
    runtime_state: RuntimeConcurrencyState,
    execution_state: ExecutionState,
    clamp_resume_index_fn,
) -> tuple[list[dict[str, Any]], int]:
    """从 pipeline state 恢复字段起点，并把字段列表旋转到恢复位置。"""
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


def create_template_build_context(
    *,
    args: argparse.Namespace,
    run_ctx: InitializedRunContext,
    fields: list[dict[str, Any]],
    existing_results_count: int,
) -> TemplateBuildContext:
    """构建运行期模板上下文，并记录初始反馈结果数缓存。"""
    template_build_ctx = TemplateBuildContext(
        options=TemplateBuildOptions.from_args(args),
        all_fields=fields,
        template_library=run_ctx.template_library,
        field_feedback=run_ctx.historical_state.field_feedback,
        global_failed_check_counts=run_ctx.historical_state.global_failed_check_counts,
        include_templates=run_ctx.filters.include_templates,
        exclude_templates=run_ctx.filters.exclude_templates,
        use_dataset_heuristics=run_ctx.use_dataset_heuristics,
        expression_policy=run_ctx.expression_policy,
    )
    template_build_ctx.feedback_result_count = existing_results_count
    return template_build_ctx


def drain_until_capacity(
    *,
    executor_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    args: argparse.Namespace,
    run_ctx: InitializedRunContext,
    field_id: str,
    result_write_options: ResultWriteOptions,
) -> bool:
    """在达到并发上限时排空已完成任务，直到恢复容量或字段被标记跳过。"""
    while len(executor_state.pending_futures) >= runtime_state.runtime_max_workers:
        done, _ = wait(
            set(executor_state.pending_futures), return_when=FIRST_COMPLETED
        )
        drain_completed_futures(
            completed_futures=list(done),
            execution_state=executor_state,
            args=args,
            result_write_options=result_write_options,
            settings_fingerprint=run_ctx.settings_fingerprint,
            template_library_fingerprint=run_ctx.template_library_fingerprint,
            run_config=run_ctx.run_config,
            runtime_state=runtime_state,
        )
        if field_id in executor_state.skipped_fields_due_to_queue:
            return False
    return True


def submit_template_future(
    *,
    executor: ThreadPoolExecutor,
    run_ctx: InitializedRunContext,
    execution_state: ExecutionState,
    args: argparse.Namespace,
    field: dict[str, Any],
    field_id: str,
    field_name: str,
    field_type: str,
    template_name: str,
    template_family: str,
    template_stage: str,
    expression: str,
    settings_variant: dict[str, Any],
    variant_fingerprint: str,
) -> None:
    """提交单个模板模拟任务，并登记 pending future 上下文。"""
    field_with_template = dict(field)
    field_with_template["template_family"] = template_family
    field_with_template["template_stage"] = template_stage
    future = executor.submit(
        run_field_test_in_worker,
        run_ctx.client_factory,
        args,
        field_with_template,
        template_name,
        expression,
        variant_fingerprint,
        run_ctx.template_library_fingerprint,
        settings_variant,
        run_ctx.create_semaphore,
    )
    execution_state.last_submission_at = time.monotonic()
    execution_state.pending_futures[future] = PendingFutureContext(
        field_id=field_id,
        field_name=field_name,
        field_type=field_type,
        template_name=template_name,
        template_family=template_family,
        template_stage=template_stage,
        expression=expression,
        settings_fingerprint=variant_fingerprint,
    )


def persist_field_progress(
    *,
    state_file: str,
    field_id: str,
    field_index: int,
    original_fields: list[dict[str, Any]],
    field_resume_positions: dict[str, int],
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
) -> None:
    """在字段完成后保存 pipeline state。"""
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


def drain_remaining_futures(
    *,
    state_file: str,
    total_fields: int,
    last_field_id: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    args: argparse.Namespace,
    run_ctx: InitializedRunContext,
    result_write_options: ResultWriteOptions,
) -> None:
    """排空剩余 future，并在需要时持续保存 state。"""
    while execution_state.pending_futures:
        done, _ = wait(set(execution_state.pending_futures), return_when=FIRST_COMPLETED)
        drain_completed_futures(
            completed_futures=list(done),
            execution_state=execution_state,
            args=args,
            result_write_options=result_write_options,
            settings_fingerprint=run_ctx.settings_fingerprint,
            template_library_fingerprint=run_ctx.template_library_fingerprint,
            run_config=run_ctx.run_config,
            runtime_state=runtime_state,
        )
        if state_file:
            save_pipeline_state(
                state_file,
                completed_field_index=max(0, total_fields),
                execution_state=execution_state,
                runtime_state=runtime_state,
                field_id=last_field_id,
            )


def save_runtime_checkpoint(
    *,
    checkpoint_file: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    last_field_id: str,
    fields: list[dict[str, Any]],
    reason: str,
) -> None:
    """在中断或异常时统一保存 checkpoint。"""
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
