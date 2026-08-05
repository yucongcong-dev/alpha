"""Run loop orchestration entrypoint."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging

from ..config.application import ApplicationConfig
from ..models.io_types import RunPaths
from ..models.runtime_options import RunLoopOptions
from ..runtime.state import InitializedRunContext
from .loop_future_support import cancel_unstarted_futures as cancel_unstarted_futures
from .loop_future_support import drain_remaining_futures as drain_remaining_futures
from .loop_future_support import submit_resumable_futures as submit_resumable_futures
from .loop_future_support import (
    wait_for_inflight_simulation_metadata as wait_for_inflight_simulation_metadata,
)
from .run_loop_feedback import refresh_runtime_feedback as refresh_runtime_feedback
from .run_loop_paths import (
    create_template_build_context as create_template_build_context,
)
from .run_loop_paths import (
    resolve_future_completion_context as resolve_future_completion_context,
)
from .run_loop_paths import (
    resolve_result_write_options as resolve_result_write_options,
)
from .run_loop_paths import run_path_value as run_path_value
from .run_loop_resume import (
    build_field_resume_positions as build_field_resume_positions,
)
from .run_loop_resume import clamp_resume_index as clamp_resume_index
from .run_loop_resume import normalize_resume_index as normalize_resume_index
from .run_loop_resume import persist_field_progress as persist_field_progress
from .run_loop_resume import restore_fields_from_state as restore_fields_from_state
from .run_loop_resume import save_runtime_checkpoint as save_runtime_checkpoint
from .run_loop_rounds import ScheduleRoundContext
from .run_loop_rounds import ScheduleRoundResult as ScheduleRoundResult
from .run_loop_rounds import execute_schedule_round as execute_schedule_round

logger = logging.getLogger(__name__)


def run_field_test_loop(
    args: ApplicationConfig,
    run_ctx: InitializedRunContext,
    run_paths: RunPaths | None = None,
) -> None:
    """线程池中遍历字段并提交模拟任务，实时消费结果。"""
    state_file = run_path_value(run_paths, "state_file")
    interrupt_report_file = run_path_value(run_paths, "interrupt_report_file") or run_path_value(
        run_paths, "checkpoint_file"
    )
    runtime_state = run_ctx.runtime_state
    execution_state = run_ctx.execution_state
    fields = list(run_ctx.fields)
    original_fields = list(run_ctx.fields)
    max_workers = runtime_state.max_workers
    run_loop_options = RunLoopOptions.from_args(args)
    field_template_batch_size = run_loop_options.field_template_batch_size
    scheduler_options = run_loop_options.scheduler
    field_resume_positions = build_field_resume_positions(original_fields)
    result_write_options = resolve_result_write_options(run_loop_options.result_write, run_paths)
    completion_ctx = resolve_future_completion_context(run_ctx, result_write_options)

    fields, _resumed_index = restore_fields_from_state(
        fields=fields,
        state_file=state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
    )

    template_build_ctx = create_template_build_context(
        args=run_loop_options.template_build,
        run_ctx=run_ctx,
        fields=fields,
        existing_results_count=len(execution_state.result_ledger.results),
    )

    executor = ThreadPoolExecutor(max_workers=max_workers)
    executor_shutdown = False
    try:
        schedule_context = ScheduleRoundContext(
            args=run_loop_options.simulation_stage,
            run_ctx=run_ctx,
            executor=executor,
            template_build_ctx=template_build_ctx,
            fields=fields,
            original_fields=original_fields,
            field_resume_positions=field_resume_positions,
            completion_ctx=completion_ctx,
            state_file=state_file,
            field_template_batch_size=field_template_batch_size,
            scheduler_options=scheduler_options,
            seed_phase_enabled=run_loop_options.full_run,
            seed_resolved_field_ids={
                field_id
                for field_id, _template, _expression, _settings in execution_state.attempted_keys
            },
        )
        if schedule_context.seed_phase_enabled:
            remaining_seed_fields = schedule_context.remaining_seed_field_count()
            logger.info(
                "[full-run] seed phase fields=%d already_resolved=%d remaining=%d",
                len(schedule_context.seed_target_field_ids),
                len(schedule_context.seed_target_field_ids) - remaining_seed_fields,
                remaining_seed_fields,
            )
            if (
                scheduler_options.max_total_simulations > 0
                and scheduler_options.max_total_simulations < remaining_seed_fields
            ):
                logger.warning(
                    "[full-run] simulation budget=%d is below remaining seed fields=%d; "
                    "this run will provide partial seed coverage and will not enter refine",
                    scheduler_options.max_total_simulations,
                    remaining_seed_fields,
                )
        last_field_id = ""
        try:
            submit_resumable_futures(
                executor=executor,
                run_ctx=run_ctx,
                execution_state=execution_state,
                args=run_loop_options.simulation_stage,
            )
            round_index = 0
            while True:
                round_index += 1
                round_result = execute_schedule_round(
                    schedule_context,
                    round_index=round_index,
                )
                last_field_id = round_result.last_field_id or last_field_id
                if round_result.stop_requested:
                    break
                if not round_result.progressed:
                    logger.info(
                        "[schedule] no pending templates remain after round=%d", round_index
                    )
                    break

            drain_remaining_futures(
                state_file=state_file,
                total_fields=len(original_fields),
                last_field_id=last_field_id,
                execution_state=execution_state,
                runtime_state=runtime_state,
                args=run_loop_options.scheduler,
                scheduler_options=scheduler_options,
                completion_ctx=completion_ctx,
            )
        except KeyboardInterrupt:
            execution_state.future_queue.stop_signal.set()
            cancelled = cancel_unstarted_futures(execution_state)
            executor.shutdown(wait=False, cancel_futures=True)
            executor_shutdown = True
            unresolved_metadata = wait_for_inflight_simulation_metadata(execution_state)
            logger.warning(
                "[abort] stopping workers cancelled=%d resumable=%d unresolved_metadata=%d",
                cancelled,
                sum(
                    1
                    for pending in execution_state.future_queue.pending_futures.values()
                    if pending.simulation_location
                ),
                unresolved_metadata,
            )
            save_runtime_checkpoint(
                state_file=state_file,
                interrupt_report_file=interrupt_report_file,
                completed_field_index=0,
                execution_state=execution_state,
                runtime_state=runtime_state,
                last_field_id=last_field_id,
                fields=fields,
                reason="KeyboardInterrupt",
            )
            raise
        except Exception:
            execution_state.future_queue.stop_signal.set()
            cancelled = cancel_unstarted_futures(execution_state)
            executor.shutdown(wait=True, cancel_futures=True)
            executor_shutdown = True
            logger.warning(
                "[abort] workers stopped after runtime exception cancelled=%d resumable=%d",
                cancelled,
                sum(
                    1
                    for pending in execution_state.future_queue.pending_futures.values()
                    if pending.simulation_location
                ),
            )
            save_runtime_checkpoint(
                state_file=state_file,
                interrupt_report_file=interrupt_report_file,
                completed_field_index=0,
                execution_state=execution_state,
                runtime_state=runtime_state,
                last_field_id=last_field_id,
                fields=fields,
                reason="Exception",
            )
            raise
    finally:
        if not executor_shutdown:
            executor.shutdown(wait=True)
