"""
运行循环编排模块。

本模块承接主流程中的执行阶段逻辑，包括：
- 运行中反馈回灌
- 断点续跑索引处理
- 字段/模板调度循环
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
from typing import cast

from ..core import print_dry_run_plan
from ..models.io_types import RunPaths
from ..models.runtime import (
    InitializedRunContext,
    RunLoopArgs,
    TemplateBuildArgs,
)
from .loop_future_support import drain_remaining_futures
from .loop_persistence import (
    create_template_build_context,
    restore_fields_from_state,
    save_runtime_checkpoint,
)
from .run_loop_feedback import refresh_runtime_feedback  # noqa: F401 - compatibility re-export
from .run_loop_paths import resolve_result_write_options, run_path_value
from .run_loop_resume import (
    build_field_resume_positions,
    clamp_resume_index,
    normalize_resume_index,  # noqa: F401 - compatibility re-export
)
from .run_loop_rounds import execute_schedule_round

logger = logging.getLogger(__name__)


def run_field_test_loop(
    args: RunLoopArgs,
    run_ctx: InitializedRunContext,
    run_paths: RunPaths | object | None = None,
) -> None:
    """线程池中遍历字段并提交模拟任务，实时消费结果。"""
    state_file = run_path_value(run_paths, "state_file")
    checkpoint_file = run_path_value(run_paths, "checkpoint_file")
    runtime_state = run_ctx.runtime_state
    execution_state = run_ctx.execution_state
    fields = list(run_ctx.fields)
    original_fields = list(run_ctx.fields)
    max_workers = runtime_state.max_workers
    field_template_batch_size = max(0, int(getattr(args, "field_template_batch_size", 0) or 0))
    field_resume_positions = build_field_resume_positions(original_fields)
    result_write_options = resolve_result_write_options(args, run_paths)

    fields, _resumed_index = restore_fields_from_state(
        fields=fields,
        state_file=state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
        clamp_resume_index_fn=clamp_resume_index,
    )

    if args.dry_run_plan:
        print_dry_run_plan(
            args=cast("TemplateBuildArgs", args),
            fields=fields,
            filters=run_ctx.filters,
            template_library=run_ctx.template_library,
            historical_state=run_ctx.historical_state,
            execution_state=execution_state,
            use_dataset_heuristics=run_ctx.use_dataset_heuristics,
        )
        return

    template_build_ctx = create_template_build_context(
        args=cast("TemplateBuildArgs", args),
        run_ctx=run_ctx,
        fields=fields,
        existing_results_count=len(execution_state.results),
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        last_field_id = ""
        try:
            round_index = 0
            while True:
                round_index += 1
                round_result = execute_schedule_round(
                    args=args,
                    run_ctx=run_ctx,
                    executor=executor,
                    template_build_ctx=template_build_ctx,
                    fields=fields,
                    original_fields=original_fields,
                    field_resume_positions=field_resume_positions,
                    execution_state=execution_state,
                    runtime_state=runtime_state,
                    result_write_options=result_write_options,
                    state_file=state_file,
                    round_index=round_index,
                    field_template_batch_size=field_template_batch_size,
                )
                last_field_id = round_result.last_field_id or last_field_id
                if field_template_batch_size <= 0 or round_result.stop_requested:
                    break
                if not round_result.progressed:
                    logger.info("[schedule] no pending templates remain after round=%d", round_index)
                    break

            drain_remaining_futures(
                state_file=state_file,
                total_fields=len(original_fields),
                last_field_id=last_field_id,
                execution_state=execution_state,
                runtime_state=runtime_state,
                args=args,
                run_ctx=run_ctx,
                result_write_options=result_write_options,
            )
        except KeyboardInterrupt:
            save_runtime_checkpoint(
                checkpoint_file=checkpoint_file,
                execution_state=execution_state,
                runtime_state=runtime_state,
                last_field_id=last_field_id,
                fields=fields,
                reason="KeyboardInterrupt",
            )
            raise
        except Exception:
            save_runtime_checkpoint(
                checkpoint_file=checkpoint_file,
                execution_state=execution_state,
                runtime_state=runtime_state,
                last_field_id=last_field_id,
                fields=fields,
                reason="Exception",
            )
            raise
