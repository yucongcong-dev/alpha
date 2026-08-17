"""Run loop orchestration entrypoint."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging

from ..config.application import ApplicationConfig
from ..core.executor import build_template_build_context
from ..core.scheduler_draining import drain_completed_futures_with_context
from ..models.domain import TemplateField
from ..models.runtime_options import (
    ResultWriteOptions,
    RunLoopOptions,
    SchedulerControlOptions,
    TemplateBuildOptions,
)
from ..models.runtime_protocols import ClientFactoryLike
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import (
    CheckpointIdentity,
    FutureCompletionContext,
    SimulationExecutionResources,
    TemplateBuildContext,
)
from ..runtime.state import ExecutionState, InitializedRunContext
from . import (
    future_completion,
    future_submission,
    run_loop_resume,
    run_loop_rounds,
)
from .run_loop_seed_phase import SeedPhaseState

logger = logging.getLogger(__name__)

_ABORT_REQUEST_GRACE_SECONDS = 0.5


def resolve_simulation_execution_resources(
    run_ctx: InitializedRunContext,
) -> SimulationExecutionResources:
    """Expose only the worker resources required by scheduling and resume."""
    return SimulationExecutionResources(
        client_factory=run_ctx.client_factory,
        template_library_fingerprint=run_ctx.template_library_fingerprint,
        create_semaphore=run_ctx.create_semaphore,
    )


def resolve_future_completion_context(
    run_ctx: InitializedRunContext,
    result_write_options: ResultWriteOptions,
) -> FutureCompletionContext:
    """Build the shared completion context once for the whole run loop."""
    return FutureCompletionContext(
        result_write_options=result_write_options,
        settings_fingerprint=run_ctx.settings_fingerprint,
        template_library_fingerprint=run_ctx.template_library_fingerprint,
        run_fingerprint=run_ctx.run_fingerprint,
        run_config=run_ctx.run_config,
    )


def create_template_build_context(
    *,
    options: TemplateBuildOptions,
    run_ctx: InitializedRunContext,
    fields: list[TemplateField],
    existing_results_count: int,
) -> TemplateBuildContext:
    """Construct the template build context and seed its feedback cache count."""
    return build_template_build_context(
        options=options,
        fields=fields,
        template_library=run_ctx.template_library,
        historical_state=run_ctx.historical_state,
        filters=run_ctx.filters,
        expression_policy=run_ctx.expression_policy,
        existing_results_count=existing_results_count,
    )


def _abort_active_requests(client_factory: ClientFactoryLike) -> None:
    """Interrupt HTTP reads without taking ownership of client shutdown."""
    abort = getattr(client_factory, "abort_active_requests", None)
    if not callable(abort):
        return
    try:
        abort()
    except Exception:
        logger.warning("[abort] failed to interrupt active HTTP requests", exc_info=True)


def _stop_workers_and_save_checkpoint(
    *,
    executor: ThreadPoolExecutor,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    identity: CheckpointIdentity,
    state_file: str,
    interrupt_report_file: str,
    diagnostic_field_id: str,
    reason: str,
    scheduler_options: SchedulerControlOptions,
    completion_ctx: FutureCompletionContext,
    client_factory: ClientFactoryLike,
) -> None:
    """Stop pending work, stabilize resumable metadata, and persist recovery state."""
    completed_futures = [
        future
        for future in execution_state.future_queue.pending_futures
        if future.done() and not future.cancelled()
    ]
    if completed_futures:
        # Persist results that finished just before the interrupt.  Futures that
        # finish after abort remain pending so their remote Location can be
        # checkpointed for polling on the next run.
        drain_completed_futures_with_context(
            completed_futures=completed_futures,
            execution_state=execution_state,
            scheduler_options=scheduler_options,
            completion_ctx=completion_ctx,
            runtime_state=runtime_state,
        )
    execution_state.future_queue.request_stop(abort_workers=True)
    cancelled = future_submission.cancel_unstarted_futures(execution_state)
    future_submission.wait_for_inflight_simulation_metadata(
        execution_state,
        timeout_seconds=_ABORT_REQUEST_GRACE_SECONDS,
    )
    if any(
        future.running() and not future.done()
        for future in execution_state.future_queue.pending_futures
    ):
        # Closing response objects interrupts long-poll reads while preserving
        # client ownership until every worker has exited below.
        _abort_active_requests(client_factory)
    # A checkpoint is only safe after every worker has stopped.  In particular,
    # a create request may already have succeeded remotely while its callback
    # has not published the Location yet.  Saving before join can turn that
    # task into a duplicate submission on the next run.
    executor.shutdown(wait=True, cancel_futures=True)
    unresolved_metadata = sum(
        1
        for pending in execution_state.future_queue.pending_futures.values()
        if not pending.simulation_location
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
        execution_state=execution_state,
        runtime_state=runtime_state,
        identity=identity,
        diagnostic_field_id=diagnostic_field_id,
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
    max_workers = runtime_state.max_workers
    run_loop_options = RunLoopOptions.from_config(args)
    field_template_batch_size = run_loop_options.field_template_batch_size
    scheduler_options = run_loop_options.scheduler
    result_write_options = run_loop_options.result_write
    completion_ctx = resolve_future_completion_context(run_ctx, result_write_options)
    checkpoint_identity = CheckpointIdentity(
        run_fingerprint=run_ctx.run_fingerprint,
    )
    execution_resources = resolve_simulation_execution_resources(run_ctx)

    fields = run_loop_resume.restore_fields_from_state(
        fields=fields,
        state_file=state_file,
        runtime_state=runtime_state,
        execution_state=execution_state,
        identity=checkpoint_identity,
    )

    template_build_ctx = create_template_build_context(
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
            dependencies=run_loop_rounds.ScheduleDependencies(
                simulation_config=run_loop_options.simulation_stage,
                execution_resources=execution_resources,
                filters=run_ctx.filters,
                historical_state=run_ctx.historical_state,
                template_build_ctx=template_build_ctx,
                completion_ctx=completion_ctx,
                state_file=state_file,
                scheduler_options=scheduler_options,
            ),
            runtime=run_loop_rounds.ScheduleRuntime(
                execution_state=execution_state,
                runtime_state=runtime_state,
                executor=executor,
                field_template_batch_size=field_template_batch_size,
                seed_phase=SeedPhaseState.create(
                    fields,
                    enabled=run_loop_options.full_run,
                    resolved_field_ids={
                        field_id
                        for field_id, _template, _expression, _settings in execution_state.attempted_keys
                    },
                ),
            ),
            fields=fields,
        )
        if schedule_context.runtime.seed_phase.enabled:
            remaining_seed_fields = schedule_context.runtime.seed_phase.remaining_count
            logger.info(
                "[full-run] seed phase fields=%d already_resolved=%d remaining=%d",
                schedule_context.runtime.seed_phase.total_count,
                schedule_context.runtime.seed_phase.resolved_count,
                remaining_seed_fields,
            )
            if (
                scheduler_options.max_new_simulations > 0
                and scheduler_options.max_new_simulations < remaining_seed_fields
            ):
                logger.warning(
                    "[full-run] simulation budget=%d is below remaining seed fields=%d; "
                    "this run will provide partial seed coverage and will not enter refine",
                    scheduler_options.max_new_simulations,
                    remaining_seed_fields,
                )
        try:
            future_submission.submit_resumable_futures(
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
                    if future_completion.drain_next_completion(
                        state_file=state_file,
                        execution_state=execution_state,
                        scheduler_options=scheduler_options,
                        completion_ctx=completion_ctx,
                        runtime_state=runtime_state,
                    ):
                        run_loop_rounds.refresh_completed_feedback(schedule_context)
                        logger.info(
                            "[schedule] completed pending work after round=%d; replanning",
                            round_index,
                        )
                        continue
                    logger.info(
                        "[schedule] no pending templates remain after round=%d", round_index
                    )
                    break

            future_completion.drain_remaining_futures(
                state_file=state_file,
                execution_state=execution_state,
                runtime_state=runtime_state,
                scheduler_options=scheduler_options,
                completion_ctx=completion_ctx,
            )
        except KeyboardInterrupt:
            _stop_workers_and_save_checkpoint(
                executor=executor,
                execution_state=execution_state,
                runtime_state=runtime_state,
                identity=checkpoint_identity,
                state_file=state_file,
                interrupt_report_file=interrupt_report_file,
                diagnostic_field_id=last_field_id,
                reason="KeyboardInterrupt",
                scheduler_options=scheduler_options,
                completion_ctx=completion_ctx,
                client_factory=run_ctx.client_factory,
            )
            executor_shutdown = True
            raise
        except Exception:
            _stop_workers_and_save_checkpoint(
                executor=executor,
                execution_state=execution_state,
                runtime_state=runtime_state,
                identity=checkpoint_identity,
                state_file=state_file,
                interrupt_report_file=interrupt_report_file,
                diagnostic_field_id=last_field_id,
                reason="Exception",
                scheduler_options=scheduler_options,
                completion_ctx=completion_ctx,
                client_factory=run_ctx.client_factory,
            )
            executor_shutdown = True
            raise
    finally:
        if not executor_shutdown:
            executor.shutdown(wait=True)
