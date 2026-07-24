"""Future queue helpers for the run loop."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import dataclasses
import time

from ..core.scheduler import drain_completed_futures_with_context
from ..core.simulation import run_field_test_in_worker
from ..models.domain import FieldTestResult, SettingsVariant, TemplateField
from ..models.runtime_protocols import ClientFactoryLike, SchedulerRuntimeArgs, SimulationStageArgs
from ..runtime import (
    ExecutionState,
    FutureCompletionContext,
    InitializedRunContext,
    PendingFutureContext,
    RuntimeConcurrencyState,
)
from .run_loop_resume import save_terminal_pipeline_state


def _drain_completed_cycle(
    *,
    pending_futures: dict[Future[FieldTestResult], PendingFutureContext],
    execution_state: ExecutionState,
    args: SchedulerRuntimeArgs,
    completion_ctx: FutureCompletionContext,
    runtime_state: RuntimeConcurrencyState,
) -> None:
    """Wait for one completion cycle and drain all finished futures."""
    done, _ = wait(
        set(pending_futures),
        return_when=FIRST_COMPLETED,
    )
    drain_completed_futures_with_context(
        completed_futures=list(done),
        execution_state=execution_state,
        args=args,
        completion_ctx=completion_ctx,
        runtime_state=runtime_state,
    )


def drain_until_capacity(
    *,
    executor_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    args: SchedulerRuntimeArgs,
    completion_ctx: FutureCompletionContext,
    field_id: str,
) -> bool:
    """Drain completed futures until runtime concurrency has available capacity."""
    while len(executor_state.pending_futures) >= runtime_state.runtime_max_workers:
        _drain_completed_cycle(
            pending_futures=executor_state.pending_futures,
            execution_state=executor_state,
            args=args,
            completion_ctx=completion_ctx,
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
    args: SimulationStageArgs,
    field: TemplateField,
    field_id: str,
    field_name: str,
    field_type: str,
    template_name: str,
    template_family: str,
    template_stage: str,
    template_role: str,
    template_activation_scope: str,
    expression: str,
    settings_variant: SettingsVariant,
    variant_fingerprint: str,
) -> None:
    """Submit one simulation future and register its pending metadata."""
    field_with_template = dataclasses.replace(
        field,
        metadata={
            **field.metadata,
            "template_family": template_family,
            "template_stage": template_stage,
            "template_role": template_role,
            "template_activation_scope": template_activation_scope,
        },
    )
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
        execution_state.stop_signal.is_set,
    )
    execution_state.last_submission_at = time.monotonic()
    typed_future: Future[FieldTestResult] = future
    execution_state.pending_futures[typed_future] = PendingFutureContext(
        field_id=field_id,
        field_name=field_name,
        field_type=field_type,
        template_name=template_name,
        template_family=template_family,
        template_stage=template_stage,
        template_role=template_role,
        template_activation_scope=template_activation_scope,
        expression=expression,
        settings_fingerprint=variant_fingerprint,
    )


def drain_remaining_futures(
    *,
    state_file: str,
    total_fields: int,
    last_field_id: str,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    args: SchedulerRuntimeArgs,
    completion_ctx: FutureCompletionContext,
) -> None:
    """Drain all remaining futures and persist terminal pipeline state when needed."""
    while execution_state.pending_futures:
        _drain_completed_cycle(
            pending_futures=execution_state.pending_futures,
            execution_state=execution_state,
            args=args,
            completion_ctx=completion_ctx,
            runtime_state=runtime_state,
        )
        save_terminal_pipeline_state(
            state_file=state_file,
            total_fields=total_fields,
            last_field_id=last_field_id,
            execution_state=execution_state,
            runtime_state=runtime_state,
        )
