"""Breadth-first scheduling helpers for the run loop."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging

from ..analysis.feedback_history import should_stop_after_submittable
from ..config.constants import SENTINEL_UNKNOWN
from ..core.executor import (
    build_pending_templates_for_field,
    inflight_template_keys,
    should_skip_field,
)
from ..core.scheduler import maybe_restore_runtime_concurrency, throttle_before_submission
from ..generators.fields import choose_field_name, choose_field_type
from ..models.domain import TemplateField
from ..models.runtime_options import ResultWriteOptions
from ..models.runtime_protocols import RunLoopArgs
from ..runtime import (
    ExecutionState,
    InitializedRunContext,
    PendingTemplateEntry,
    RuntimeConcurrencyState,
    TemplateBuildContext,
)
from ..utils.helpers import first_non_empty
from .loop_future_support import drain_until_capacity, submit_template_future
from .run_loop_feedback import refresh_runtime_feedback
from .run_loop_resume import persist_field_progress

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduleRoundResult:
    """Summary of a single breadth-first scheduling round."""

    progressed: bool
    stop_requested: bool
    last_field_id: str


def execute_schedule_round(
    *,
    args: RunLoopArgs,
    run_ctx: InitializedRunContext,
    executor: ThreadPoolExecutor,
    template_build_ctx: TemplateBuildContext,
    fields: list[TemplateField],
    original_fields: list[TemplateField],
    field_resume_positions: dict[str, int],
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    result_write_options: ResultWriteOptions,
    state_file: str,
    round_index: int,
    field_template_batch_size: int,
) -> ScheduleRoundResult:
    """Execute one scheduling round across every remaining field."""
    progressed_this_round = False
    last_field_id = ""
    if field_template_batch_size > 0:
        logger.info(
            "[schedule] round=%d breadth-first batch_size=%d fields=%d",
            round_index,
            field_template_batch_size,
            len(fields),
        )

    for field_index, field in enumerate(fields, start=1):
        if should_stop_after_submittable(args, execution_state.results):
            execution_state.stop_signal.set()
            logger.info("[stop] 达到 stop-after-submittable=%d", args.stop_after_submittable)
            return ScheduleRoundResult(
                progressed=progressed_this_round,
                stop_requested=True,
                last_field_id=last_field_id,
            )

        field_result = schedule_field_round(
            args=args,
            run_ctx=run_ctx,
            executor=executor,
            template_build_ctx=template_build_ctx,
            field=field,
            field_index=field_index,
            total_fields=len(fields),
            original_fields=original_fields,
            field_resume_positions=field_resume_positions,
            execution_state=execution_state,
            runtime_state=runtime_state,
            result_write_options=result_write_options,
            state_file=state_file,
            round_index=round_index,
            field_template_batch_size=field_template_batch_size,
        )
        last_field_id = field_result.last_field_id or last_field_id
        progressed_this_round = progressed_this_round or field_result.progressed
        if field_result.stop_requested:
            return ScheduleRoundResult(
                progressed=progressed_this_round,
                stop_requested=True,
                last_field_id=last_field_id,
            )

    return ScheduleRoundResult(
        progressed=progressed_this_round,
        stop_requested=False,
        last_field_id=last_field_id,
    )


def schedule_field_round(
    *,
    args: RunLoopArgs,
    run_ctx: InitializedRunContext,
    executor: ThreadPoolExecutor,
    template_build_ctx: TemplateBuildContext,
    field: TemplateField,
    field_index: int,
    total_fields: int,
    original_fields: list[TemplateField],
    field_resume_positions: dict[str, int],
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    result_write_options: ResultWriteOptions,
    state_file: str,
    round_index: int,
    field_template_batch_size: int,
) -> ScheduleRoundResult:
    """Schedule one field for the current round and persist its progress."""
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    refresh_runtime_feedback(template_build_ctx, execution_state.results)

    if should_skip_field(
        field_id,
        field_name,
        run_ctx.filters,
        execution_state.skipped_fields_due_to_queue,
    ):
        persist_field_progress(
            state_file=state_file,
            field_id=field_id,
            field_index=field_index,
            original_fields=original_fields,
            field_resume_positions=field_resume_positions,
            execution_state=execution_state,
            runtime_state=runtime_state,
        )
        return ScheduleRoundResult(progressed=False, stop_requested=False, last_field_id=field_id)

    pending_templates, disabled_templates, template_count = build_pending_templates_for_field(
        template_build_ctx,
        field,
        template_stats=execution_state.template_stats,
        attempted_keys=execution_state.attempted_keys,
        prior_results=execution_state.results,
        reserved_keys=inflight_template_keys(execution_state.pending_futures),
    )
    logger.debug(
        "[progress] 字段 %d/%d field_id=%s templates=%d pending=%d disabled=%d",
        field_index,
        total_fields,
        field_id,
        template_count,
        len(pending_templates),
        disabled_templates,
    )

    if field_template_batch_size > 0:
        scheduled_templates = pending_templates[:field_template_batch_size]
        deferred_templates = max(0, len(pending_templates) - len(scheduled_templates))
    else:
        scheduled_templates = pending_templates
        deferred_templates = 0
    progressed = bool(scheduled_templates)
    if deferred_templates > 0:
        logger.debug(
            "[schedule] field=%s round=%d dispatch=%d deferred=%d",
            field_id,
            round_index,
            len(scheduled_templates),
            deferred_templates,
        )

    stop_requested = _dispatch_templates_for_field(
        args=args,
        run_ctx=run_ctx,
        executor=executor,
        execution_state=execution_state,
        runtime_state=runtime_state,
        result_write_options=result_write_options,
        field=field,
        field_id=field_id,
        field_name=field_name,
        field_type=field_type,
        scheduled_templates=scheduled_templates,
    )
    persist_field_progress(
        state_file=state_file,
        field_id=field_id,
        field_index=field_index,
        original_fields=original_fields,
        field_resume_positions=field_resume_positions,
        execution_state=execution_state,
        runtime_state=runtime_state,
    )
    return ScheduleRoundResult(
        progressed=progressed,
        stop_requested=stop_requested,
        last_field_id=field_id,
    )


def _dispatch_templates_for_field(
    *,
    args: RunLoopArgs,
    run_ctx: InitializedRunContext,
    executor: ThreadPoolExecutor,
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    result_write_options: ResultWriteOptions,
    field: TemplateField,
    field_id: str,
    field_name: str,
    field_type: str,
    scheduled_templates: list[PendingTemplateEntry],
) -> bool:
    """Dispatch scheduled templates for a single field; return whether a stop was requested."""
    for template_index, entry in enumerate(scheduled_templates, start=1):
        if should_stop_after_submittable(args, execution_state.results):
            execution_state.stop_signal.set()
            logger.info("[stop] 达到 stop-after-submittable=%d", args.stop_after_submittable)
            return True

        if field_id in execution_state.skipped_fields_due_to_queue:
            logger.warning("[skip] field=%s 队列拥塞后停止剩余模板", field_id)
            return False
        if execution_state.stop_signal.is_set():
            return True

        maybe_restore_runtime_concurrency(runtime_state)
        if not drain_until_capacity(
            executor_state=execution_state,
            runtime_state=runtime_state,
            args=args,
            run_ctx=run_ctx,
            field_id=field_id,
            result_write_options=result_write_options,
        ):
            return False
        if execution_state.stop_signal.is_set():
            return True

        logger.debug(
            "[progress] field=%s template %d/%d name=%s priority=%d queued=%d/%d settings=%s",
            field_id,
            template_index,
            len(scheduled_templates),
            entry.template_name,
            entry.priority,
            len(execution_state.pending_futures) + 1,
            runtime_state.runtime_max_workers,
            entry.variant_fingerprint,
        )
        throttle_before_submission(args, execution_state)
        submit_template_future(
            executor=executor,
            run_ctx=run_ctx,
            execution_state=execution_state,
            args=args,
            field=field,
            field_id=field_id,
            field_name=field_name,
            field_type=field_type,
            template_name=entry.template_name,
            template_family=entry.template_family,
            template_stage=entry.template_stage,
            template_role=entry.template_role,
            template_activation_scope=entry.template_activation_scope,
            expression=entry.expression,
            settings_variant=entry.settings_variant,
            variant_fingerprint=entry.variant_fingerprint,
        )
    return False
