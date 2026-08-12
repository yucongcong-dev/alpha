"""Breadth-first scheduling helpers for the run loop."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from dataclasses import field as dataclass_field
import logging

from ..config._constants_strings import SENTINEL_UNKNOWN
from ..core.executor import (
    build_pending_templates_for_field,
    inflight_template_keys,
    should_skip_field,
)
from ..generators.fields import choose_field_name, choose_field_type
from ..models.domain import TemplateField
from ..models.io_types import RunFilters
from ..models.runtime_config import SimulationStageConfig
from ..models.runtime_options import SchedulerControlOptions
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import (
    CheckpointIdentity,
    FutureCompletionContext,
    HistoricalRunState,
    SimulationExecutionResources,
    TemplateBuildContext,
)
from ..runtime.field_template_queue import FieldTemplateQueue
from ..runtime.state import ExecutionState
from ..utils.helpers import first_non_empty
from .run_loop_dispatch import apply_feedback_refresh, dispatch_templates_for_field
from .run_loop_feedback import refresh_runtime_feedback
from .run_loop_resume import persist_replanning_checkpoint
from .run_loop_seed_phase import SeedPhaseState

logger = logging.getLogger(__name__)


def _checkpoint_identity(context: ScheduleRoundContext) -> CheckpointIdentity:
    return CheckpointIdentity(run_fingerprint=context.completion_ctx.run_fingerprint)


@dataclass(frozen=True)
class ScheduleRoundResult:
    """Summary of a single breadth-first scheduling round."""

    progressed: bool
    stop_requested: bool
    last_field_id: str


@dataclass
class ScheduleRoundContext:
    """Stable dependencies shared by every breadth-first scheduling round."""

    simulation_config: SimulationStageConfig
    execution_resources: SimulationExecutionResources
    execution_state: ExecutionState
    runtime_state: RuntimeConcurrencyState
    filters: RunFilters
    historical_state: HistoricalRunState
    executor: ThreadPoolExecutor
    template_build_ctx: TemplateBuildContext
    fields: list[TemplateField]
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
        self.seed_phase.sync(self.execution_state)

    def reached_simulation_budget(self) -> bool:
        """Return whether this process has dispatched its configured simulation budget."""
        budget = self.scheduler_options.max_total_simulations
        return budget > 0 and self.scheduled_simulations >= budget


def execute_schedule_round(
    context: ScheduleRoundContext,
    *,
    round_index: int,
) -> ScheduleRoundResult:
    """Execute one scheduling round across every remaining field."""
    scheduler_options = context.scheduler_options
    execution_state = context.execution_state
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
    execution_state = context.execution_state
    runtime_state = context.runtime_state
    result_ledger = execution_state.result_ledger
    field_id = str(first_non_empty(field.field_id, SENTINEL_UNKNOWN))
    field_name = choose_field_name(field)
    field_type = choose_field_type(field)
    seed_phase_active = context.seed_phase.active
    if context.seed_phase.should_wait_or_skip(field_id):
        return ScheduleRoundResult(progressed=False, stop_requested=False, last_field_id=field_id)
    feedback_refresh = refresh_runtime_feedback(context.template_build_ctx, result_ledger.results)
    apply_feedback_refresh(context, feedback_refresh)

    if should_skip_field(
        field_id,
        field_name,
        context.filters,
    ):
        seed_resolution_progressed = (
            context.seed_phase.resolve(field_id) if seed_phase_active else False
        )
        persist_replanning_checkpoint(
            state_file=context.state_file,
            field_id=field_id,
            execution_state=execution_state,
            runtime_state=runtime_state,
            identity=_checkpoint_identity(context),
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
                *context.historical_state.feedback_results,
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
    stop_requested = dispatch_templates_for_field(
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
    persist_replanning_checkpoint(
        state_file=context.state_file,
        field_id=field_id,
        execution_state=execution_state,
        runtime_state=runtime_state,
        identity=_checkpoint_identity(context),
    )
    return ScheduleRoundResult(
        progressed=progressed,
        stop_requested=stop_requested,
        last_field_id=field_id,
    )
