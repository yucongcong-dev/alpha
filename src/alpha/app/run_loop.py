"""Run loop orchestration entrypoint."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging

from ..config.application import ApplicationConfig
from ..models.domain import TemplateField
from ..models.runtime_options import RunLoopOptions
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import CheckpointIdentity
from ..runtime.state import ExecutionState, InitializedRunContext
from . import loop_future_support, run_loop_contexts, run_loop_resume, run_loop_rounds
from .run_loop_seed_phase import SeedPhaseState

logger = logging.getLogger(__name__)

INTERRUPT_METADATA_WAIT_SECONDS = 15.0


def _stop_workers_and_save_checkpoint(
    *,
    executor: ThreadPoolExecutor,
    wait_for_workers: bool,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    identity: CheckpointIdentity,
    state_file: str,
    interrupt_report_file: str,
    last_field_id: str,
    fields: list[TemplateField],
    reason: str,
) -> None:
    """Stop pending work, stabilize resumable metadata, and persist recovery state."""
    execution_state.future_queue.request_stop(abort_workers=True)
    cancelled = loop_future_support.cancel_unstarted_futures(execution_state)
    executor.shutdown(wait=wait_for_workers, cancel_futures=True)
    unresolved_metadata = 0
    if not wait_for_workers:
        unresolved_metadata = loop_future_support.wait_for_inflight_simulation_metadata(
            execution_state,
            timeout_seconds=INTERRUPT_METADATA_WAIT_SECONDS,
        )
    resumable = sum(
        1
        for pending in execution_state.future_queue.pending_futures.values()
        if pending.simulation_location
    )
    logger.warning(
        "[abort] workers stopped reason=%s cancelled=%d resumable=%d unresolved_metadata=%d",
        reason,
        cancelled,
        resumable,
        unresolved_metadata,
    )
    run_loop_resume.save_runtime_checkpoint(
        state_file=state_file,
        interrupt_report_file=interrupt_report_file,
        completed_field_index=0,
        execution_state=execution_state,
        runtime_state=runtime_state,
        identity=identity,
        last_field_id=last_field_id,
        fields=fields,
        reason=reason,
    )


def run_field_test_loop(
    args: ApplicationConfig,
    run_ctx: InitializedRunContext,
) -> None:
    """线程池中遍历字段并提交模拟任务，实时消费结果。"""
    paths = args.paths
    state_file = paths.state_file
    interrupt_report_file = paths.interrupt_report_file
    runtime_state = run_ctx.runtime_state
    execution_state = run_ctx.execution_state
    fields = list(run_ctx.fields)
    total_field_count = len(fields)
    max_workers = runtime_state.max_workers
    run_loop_options = RunLoopOptions.from_config(args)
    field_template_batch_size = run_loop_options.field_template_batch_size
    scheduler_options = run_loop_options.scheduler
    result_write_options = run_loop_options.result_write
    completion_ctx = run_loop_contexts.resolve_future_completion_context(
        run_ctx, result_write_options
    )
    checkpoint_identity = CheckpointIdentity(
        run_fingerprint=run_ctx.run_fingerprint,
    )
    execution_resources = run_loop_contexts.resolve_simulation_execution_resources(run_ctx)

    fields = run_loop_resume.restore_fields_from_state(
        fields=fields,
        state_file=state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
        identity=checkpoint_identity,
    )

    template_build_ctx = run_loop_contexts.create_template_build_context(
        options=run_loop_options.template_build,
        run_ctx=run_ctx,
        fields=fields,
        existing_results_count=len(execution_state.result_ledger.results),
    )

    executor = ThreadPoolExecutor(max_workers=max_workers)
    executor_shutdown = False
    last_field_id = ""
    try:
        schedule_context = run_loop_rounds.ScheduleRoundContext(
            simulation_config=run_loop_options.simulation_stage,
            execution_resources=execution_resources,
            execution_state=execution_state,
            runtime_state=runtime_state,
            filters=run_ctx.filters,
            historical_state=run_ctx.historical_state,
            executor=executor,
            template_build_ctx=template_build_ctx,
            fields=fields,
            completion_ctx=completion_ctx,
            state_file=state_file,
            field_template_batch_size=field_template_batch_size,
            scheduler_options=scheduler_options,
            seed_phase=SeedPhaseState.create(
                fields,
                enabled=run_loop_options.full_run,
                resolved_field_ids={
                    field_id
                    for field_id, _template, _expression, _settings in execution_state.attempted_keys
                },
            ),
        )
        if schedule_context.seed_phase.enabled:
            remaining_seed_fields = schedule_context.seed_phase.remaining_count
            logger.info(
                "[full-run] seed phase fields=%d already_resolved=%d remaining=%d",
                schedule_context.seed_phase.total_count,
                schedule_context.seed_phase.resolved_count,
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
        try:
            loop_future_support.submit_resumable_futures(
                executor=executor,
                execution_resources=execution_resources,
                execution_state=execution_state,
                simulation_config=run_loop_options.simulation_stage,
            )
            round_index = 0
            while True:
                round_index += 1
                round_result = run_loop_rounds.execute_schedule_round(
                    schedule_context,
                    round_index=round_index,
                )
                last_field_id = round_result.last_field_id or last_field_id
                if round_result.stop_requested:
                    break
                if not round_result.progressed:
                    if loop_future_support.drain_next_completion(
                        state_file=state_file,
                        total_fields=total_field_count,
                        last_field_id=last_field_id,
                        execution_state=execution_state,
                        scheduler_options=scheduler_options,
                        completion_ctx=completion_ctx,
                        runtime_state=runtime_state,
                    ):
                        logger.info(
                            "[schedule] completed pending work after round=%d; replanning",
                            round_index,
                        )
                        continue
                    logger.info(
                        "[schedule] no pending templates remain after round=%d", round_index
                    )
                    break

            loop_future_support.drain_remaining_futures(
                state_file=state_file,
                total_fields=total_field_count,
                last_field_id=last_field_id,
                execution_state=execution_state,
                runtime_state=runtime_state,
                scheduler_options=scheduler_options,
                completion_ctx=completion_ctx,
            )
        except KeyboardInterrupt:
            _stop_workers_and_save_checkpoint(
                executor=executor,
                wait_for_workers=False,
                execution_state=execution_state,
                runtime_state=runtime_state,
                identity=checkpoint_identity,
                state_file=state_file,
                interrupt_report_file=interrupt_report_file,
                last_field_id=last_field_id,
                fields=fields,
                reason="KeyboardInterrupt",
            )
            executor_shutdown = True
            raise
        except Exception:
            _stop_workers_and_save_checkpoint(
                executor=executor,
                wait_for_workers=True,
                execution_state=execution_state,
                runtime_state=runtime_state,
                identity=checkpoint_identity,
                state_file=state_file,
                interrupt_report_file=interrupt_report_file,
                last_field_id=last_field_id,
                fields=fields,
                reason="Exception",
            )
            executor_shutdown = True
            raise
    finally:
        if not executor_shutdown:
            executor.shutdown(wait=True)
