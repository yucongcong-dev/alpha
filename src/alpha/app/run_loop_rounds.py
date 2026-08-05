"""Breadth-first scheduling helpers for the run loop."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from dataclasses import field as dataclass_field
import logging

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
from ..models.runtime_protocols import SimulationStageArgs
from ..runtime.contexts import (
    FutureCompletionContext,
    PendingTemplateEntry,
    TemplateBuildContext,
)
from ..runtime.field_template_queue import FieldTemplateQueue
from ..runtime.state import InitializedRunContext
from ..utils.helpers import first_non_empty
from .loop_future_support import drain_until_capacity, submit_template_future
from .run_loop_feedback import RuntimeFeedbackRefresh, refresh_runtime_feedback
from .run_loop_resume import persist_field_progress
from .run_loop_seed_phase import SeedPhaseState

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

    args: SimulationStageArgs
    run_ctx: InitializedRunContext
    executor: ThreadPoolExecutor
    template_build_ctx: TemplateBuildContext
    fields: list[TemplateField]
    original_fields: list[TemplateField]
    field_resume_positions: dict[str, int]
    completion_ctx: FutureCompletionContext
    state_file: str
    field_template_batch_size: int
    scheduler_options: SchedulerControlOptions = dataclass_field(
        default_factory=SchedulerControlOptions
    )
    scheduled_simulations: int = 0
    field_template_queues: dict[str, FieldTemplateQueue] = dataclass_field(default_factory=dict)
    seed_phase: SeedPhaseState = dataclass_field(default_factory=SeedPhaseState)

    def __post_init__(self) -> None:
        self.field_template_batch_size = max(1, int(self.field_template_batch_size or 0))
        self.seed_phase.sync(self.run_ctx.execution_state)

    def reached_simulation_budget(self) -> bool:
        """Return whether this process has dispatched its configured simulation budget."""
        budget = self.scheduler_options.max_total_simulations
        return budget > 0 and self.scheduled_simulations >= budget


def _apply_feedback_refresh(
    context: ScheduleRoundContext,
    feedback_refresh: RuntimeFeedbackRefresh,
) -> None:
    """Invalidate cached field queues affected by newly consumed runtime feedback."""
    if feedback_refresh.feedback_changed:
        context.field_template_queues.clear()
        return
    for retry_field_id in feedback_refresh.retry_field_ids:
        context.field_template_queues.pop(retry_field_id, None)


def execute_schedule_round(
    context: ScheduleRoundContext,
    *,
    round_index: int,
) -> ScheduleRoundResult:
    """Execute one scheduling round across every remaining field."""
    scheduler_options = context.scheduler_options
    execution_state = context.run_ctx.execution_state
    result_ledger = execution_state.result_ledger
    progressed_this_round = False
    last_field_id = ""
    context.seed_phase.sync(execution_state)
    if execution_state.future_queue.should_stop_scheduling():
        return ScheduleRoundResult(
            progressed=False,
            stop_requested=True,
            last_field_id="",
        )
    logger.info(
        "[schedule] round=%d phase=%s breadth-first batch_size=%d fields=%d",
        round_index,
        context.seed_phase.phase_name,
        context.field_template_batch_size,
        len(context.fields),
    )

    for field_index, field in enumerate(context.fields, start=1):
        if context.reached_simulation_budget():
            logger.info(
                "[stop] 达到 max-total-simulations=%d seed_fields_unresolved=%d "
                "seed_fields_inflight=%d",
                scheduler_options.max_total_simulations,
                context.seed_phase.remaining_count,
                len(context.seed_phase.inflight_field_ids),
            )
            return ScheduleRoundResult(
                progressed=progressed_this_round,
                stop_requested=True,
                last_field_id=last_field_id,
            )
        if result_ledger.reached_submittable_stop_threshold(
            scheduler_options.stop_after_submittable
        ):
            execution_state.future_queue.scheduling_stop_signal.set()
            logger.info(
                "[stop] 达到 stop-after-submittable=%d",
                scheduler_options.stop_after_submittable,
            )
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
    result_ledger = execution_state.result_ledger
    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    seed_phase_active = context.seed_phase.active
    if context.seed_phase.should_wait_or_skip(field_id):
        return ScheduleRoundResult(progressed=False, stop_requested=False, last_field_id=field_id)
    feedback_refresh = refresh_runtime_feedback(context.template_build_ctx, result_ledger.results)
    _apply_feedback_refresh(context, feedback_refresh)

    if should_skip_field(
        field_id,
        field_name,
        run_ctx.filters,
    ):
        seed_resolution_progressed = (
            context.seed_phase.resolve(field_id) if seed_phase_active else False
        )
        persist_field_progress(
            state_file=context.state_file,
            field_id=field_id,
            field_index=field_index,
            original_fields=context.original_fields,
            field_resume_positions=context.field_resume_positions,
            execution_state=execution_state,
            runtime_state=runtime_state,
            completed_field_index_override=0,
        )
        return ScheduleRoundResult(
            progressed=seed_resolution_progressed,
            stop_requested=False,
            last_field_id=field_id,
        )

    template_queue = context.field_template_queues.get(field_id)
    if template_queue is None:
        pending_templates, filtered_templates, template_count = build_pending_templates_for_field(
            context.template_build_ctx,
            field,
            attempted_keys=(
                execution_state.attempted_keys | execution_state.queue_retry_state.exhausted_keys
            ),
            prior_results=[
                *run_ctx.historical_state.feedback_results,
                *result_ledger.results,
            ],
            reserved_keys=inflight_template_keys(execution_state.future_queue.pending_futures),
        )
        template_queue = FieldTemplateQueue.create(
            pending_templates,
            filtered_templates=filtered_templates,
            template_count=template_count,
        )
        context.field_template_queues[field_id] = template_queue
    pending_count = len(template_queue.entries)
    seed_resolution_progressed = False
    if seed_phase_active and pending_count == 0:
        seed_resolution_progressed = context.seed_phase.resolve(field_id)
    logger.debug(
        "[progress] 字段 %d/%d field_id=%s templates=%d pending=%d filtered=%d",
        field_index,
        total_fields,
        field_id,
        template_queue.template_count,
        pending_count,
        template_queue.filtered_templates,
    )

    scheduled_templates = (
        template_queue.peek_seed()
        if seed_phase_active
        else template_queue.peek(context.field_template_batch_size)
    )
    deferred_templates = max(0, pending_count - len(scheduled_templates))
    progressed = bool(scheduled_templates) or seed_resolution_progressed
    if deferred_templates > 0:
        logger.debug(
            "[schedule] field=%s round=%d dispatch=%d deferred=%d",
            field_id,
            round_index,
            len(scheduled_templates),
            deferred_templates,
        )

    queue_count_before_dispatch = len(template_queue.entries)
    stop_requested = _dispatch_templates_for_field(
        context=context,
        field=field,
        field_id=field_id,
        field_name=field_name,
        field_type=field_type,
        scheduled_templates=scheduled_templates,
        template_queue=template_queue,
    )
    if seed_phase_active and len(template_queue.entries) < queue_count_before_dispatch:
        context.seed_phase.mark_inflight(field_id)
    persist_field_progress(
        state_file=context.state_file,
        field_id=field_id,
        field_index=field_index,
        original_fields=context.original_fields,
        field_resume_positions=context.field_resume_positions,
        execution_state=execution_state,
        runtime_state=runtime_state,
        completed_field_index_override=0,
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
    template_queue: FieldTemplateQueue | None = None,
) -> bool:
    """Dispatch scheduled templates for a single field; return whether a stop was requested."""
    args = context.args
    scheduler_options = context.scheduler_options
    run_ctx = context.run_ctx
    execution_state = run_ctx.execution_state
    result_ledger = execution_state.result_ledger
    runtime_state = run_ctx.runtime_state
    for template_index, entry in enumerate(scheduled_templates, start=1):
        if context.reached_simulation_budget():
            logger.info(
                "[stop] 达到 max-total-simulations=%d",
                scheduler_options.max_total_simulations,
            )
            return True
        if result_ledger.reached_submittable_stop_threshold(
            scheduler_options.stop_after_submittable
        ):
            execution_state.future_queue.scheduling_stop_signal.set()
            logger.info(
                "[stop] 达到 stop-after-submittable=%d",
                scheduler_options.stop_after_submittable,
            )
            return True

        if execution_state.future_queue.should_stop_scheduling():
            return True

        maybe_restore_runtime_concurrency(runtime_state)
        result_count_before_drain = len(result_ledger.results)
        if not drain_until_capacity(
            executor_state=execution_state,
            runtime_state=runtime_state,
            scheduler_options=scheduler_options,
            completion_ctx=context.completion_ctx,
            field_id=field_id,
        ):
            return False
        if execution_state.future_queue.should_stop_scheduling():
            return True
        if len(result_ledger.results) != result_count_before_drain:
            feedback_refresh = refresh_runtime_feedback(
                context.template_build_ctx,
                result_ledger.results,
            )
            _apply_feedback_refresh(context, feedback_refresh)
            if feedback_refresh.feedback_changed or field_id in feedback_refresh.retry_field_ids:
                logger.debug(
                    "[schedule] field=%s queue invalidated after completed results; replanning",
                    field_id,
                )
                return False

        logger.debug(
            "[progress] field=%s template %d/%d name=%s priority=%d queued=%d/%d settings=%s",
            field_id,
            template_index,
            len(scheduled_templates),
            entry.template_name,
            entry.priority,
            len(execution_state.future_queue.pending_futures) + 1,
            runtime_state.runtime_max_workers,
            entry.variant_fingerprint,
        )
        throttle_before_submission(scheduler_options, execution_state)
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
        if template_queue is not None:
            template_queue.consume(entry)
        context.scheduled_simulations += 1
    return False
