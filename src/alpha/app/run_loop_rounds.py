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
from ..models.runtime_options import SchedulerControlOptions
from ..models.runtime_protocols import RunLoopArgs
from ..runtime.contexts import (
    FutureCompletionContext,
    PendingTemplateEntry,
    TemplateBuildContext,
)
from ..runtime.state import InitializedRunContext
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


@dataclass
class ScheduleRoundContext:
    """Stable dependencies shared by every breadth-first scheduling round."""

    args: RunLoopArgs
    run_ctx: InitializedRunContext
    executor: ThreadPoolExecutor
    template_build_ctx: TemplateBuildContext
    fields: list[TemplateField]
    original_fields: list[TemplateField]
    field_resume_positions: dict[str, int]
    completion_ctx: FutureCompletionContext
    state_file: str
    field_template_batch_size: int


def execute_schedule_round(
    context: ScheduleRoundContext,
    *,
    round_index: int,
) -> ScheduleRoundResult:
    """Execute one scheduling round across every remaining field."""
    args = context.args
    execution_state = context.run_ctx.execution_state
    progressed_this_round = False
    last_field_id = ""
    if execution_state.stop_signal.is_set():
        return ScheduleRoundResult(
            progressed=False,
            stop_requested=True,
            last_field_id="",
        )
    if context.field_template_batch_size > 0:
        logger.info(
            "[schedule] round=%d breadth-first batch_size=%d fields=%d",
            round_index,
            context.field_template_batch_size,
            len(context.fields),
        )

    for field_index, field in enumerate(context.fields, start=1):
        if should_stop_after_submittable(
            args.stop_after_submittable,
            execution_state.results,
            baseline_count=execution_state.submittable_baseline_count,
        ):
            execution_state.stop_signal.set()
            logger.info("[stop] 达到 stop-after-submittable=%d", args.stop_after_submittable)
            return ScheduleRoundResult(
                progressed=progressed_this_round,
                stop_requested=True,
                last_field_id=last_field_id,
            )

        field_result = schedule_field_round(
            context=context,
            field=field,
            field_index=field_index,
            total_fields=len(context.fields),
            round_index=round_index,
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
    context: ScheduleRoundContext,
    field: TemplateField,
    field_index: int,
    total_fields: int,
    round_index: int,
) -> ScheduleRoundResult:
    """Schedule one field for the current round and persist its progress."""
    run_ctx = context.run_ctx
    execution_state = run_ctx.execution_state
    runtime_state = run_ctx.runtime_state
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    refresh_runtime_feedback(context.template_build_ctx, execution_state.results)

    if should_skip_field(
        field_id,
        field_name,
        run_ctx.filters,
        execution_state.skipped_fields_due_to_queue,
    ):
        persist_field_progress(
            state_file=context.state_file,
            field_id=field_id,
            field_index=field_index,
            original_fields=context.original_fields,
            field_resume_positions=context.field_resume_positions,
            execution_state=execution_state,
            runtime_state=runtime_state,
            completed_field_index_override=(0 if context.field_template_batch_size > 0 else None),
        )
        return ScheduleRoundResult(progressed=False, stop_requested=False, last_field_id=field_id)

    pending_templates, filtered_templates, template_count = build_pending_templates_for_field(
        context.template_build_ctx,
        field,
        attempted_keys=execution_state.attempted_keys | execution_state.queue_exhausted_keys,
        prior_results=[
            *run_ctx.historical_state.feedback_results,
            *execution_state.results,
        ],
        reserved_keys=inflight_template_keys(execution_state.pending_futures),
    )
    logger.debug(
        "[progress] 字段 %d/%d field_id=%s templates=%d pending=%d filtered=%d",
        field_index,
        total_fields,
        field_id,
        template_count,
        len(pending_templates),
        filtered_templates,
    )

    if context.field_template_batch_size > 0:
        scheduled_templates = pending_templates[: context.field_template_batch_size]
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
        context=context,
        field=field,
        field_id=field_id,
        field_name=field_name,
        field_type=field_type,
        scheduled_templates=scheduled_templates,
    )
    persist_field_progress(
        state_file=context.state_file,
        field_id=field_id,
        field_index=field_index,
        original_fields=context.original_fields,
        field_resume_positions=context.field_resume_positions,
        execution_state=execution_state,
        runtime_state=runtime_state,
        completed_field_index_override=(0 if context.field_template_batch_size > 0 else None),
    )
    return ScheduleRoundResult(
        progressed=progressed,
        stop_requested=stop_requested,
        last_field_id=field_id,
    )


def _dispatch_templates_for_field(
    *,
    context: ScheduleRoundContext,
    field: TemplateField,
    field_id: str,
    field_name: str,
    field_type: str,
    scheduled_templates: list[PendingTemplateEntry],
) -> bool:
    """Dispatch scheduled templates for a single field; return whether a stop was requested."""
    args = context.args
    run_ctx = context.run_ctx
    execution_state = run_ctx.execution_state
    runtime_state = run_ctx.runtime_state
    for template_index, entry in enumerate(scheduled_templates, start=1):
        if should_stop_after_submittable(
            args.stop_after_submittable,
            execution_state.results,
            baseline_count=execution_state.submittable_baseline_count,
        ):
            execution_state.stop_signal.set()
            logger.info("[stop] 达到 stop-after-submittable=%d", args.stop_after_submittable)
            return True

        if execution_state.stop_signal.is_set():
            return True

        maybe_restore_runtime_concurrency(runtime_state)
        if not drain_until_capacity(
            executor_state=execution_state,
            runtime_state=runtime_state,
            scheduler_options=SchedulerControlOptions.from_args(args),
            completion_ctx=context.completion_ctx,
            field_id=field_id,
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
        throttle_before_submission(SchedulerControlOptions.from_args(args), execution_state)
        submit_template_future(
            executor=context.executor,
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
            policy_version=entry.policy_version,
            expression=entry.expression,
            settings_variant=entry.settings_variant,
            variant_fingerprint=entry.variant_fingerprint,
        )
    return False
