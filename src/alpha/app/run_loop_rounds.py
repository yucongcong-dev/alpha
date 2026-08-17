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
from .run_loop_feedback import RuntimeFeedbackRefresh, refresh_runtime_feedback
from .run_loop_resume import persist_replanning_checkpoint
from .run_loop_seed_phase import SeedPhaseState

logger = logging.getLogger(__name__)


def _checkpoint_identity(context: ScheduleRoundContext) -> CheckpointIdentity:
    return CheckpointIdentity(run_fingerprint=context.dependencies.completion_ctx.run_fingerprint)


@dataclass(frozen=True)
class ScheduleRoundResult:
    """Summary of a single breadth-first scheduling round."""

    progressed: bool
    stop_requested: bool
    last_field_id: str


@dataclass(frozen=True)
class ScheduleDependencies:
    """Immutable resources and policy shared by every scheduling round."""

    simulation_config: SimulationStageConfig
    execution_resources: SimulationExecutionResources
    filters: RunFilters
    historical_state: HistoricalRunState
    template_build_ctx: TemplateBuildContext
    completion_ctx: FutureCompletionContext
    state_file: str
    scheduler_options: SchedulerControlOptions


@dataclass
class ScheduleRuntime:
    """Mutable scheduling state owned by one breadth-first run."""

    execution_state: ExecutionState
    runtime_state: RuntimeConcurrencyState
    executor: ThreadPoolExecutor
    field_template_batch_size: int
    scheduled_simulations: int = 0
    field_template_queues: dict[str, FieldTemplateQueue] = dataclass_field(default_factory=dict)
    seed_phase: SeedPhaseState = dataclass_field(default_factory=SeedPhaseState)


@dataclass
class ScheduleRoundContext:
    """Round input plus explicitly owned mutable scheduling state."""

    dependencies: ScheduleDependencies
    runtime: ScheduleRuntime
    fields: list[TemplateField]

    def __post_init__(self) -> None:
        self.runtime.field_template_batch_size = max(
            1, int(self.runtime.field_template_batch_size or 0)
        )
        self.runtime.seed_phase.sync(self.runtime.execution_state)

    def reached_simulation_budget(self) -> bool:
        """Return whether this process has dispatched its configured simulation budget."""
        budget = self.dependencies.scheduler_options.max_new_simulations
        return budget > 0 and self.runtime.scheduled_simulations >= budget


def refresh_completed_feedback(context: ScheduleRoundContext) -> RuntimeFeedbackRefresh:
    """Refresh feedback after a completion drain and invalidate affected queues."""
    feedback_refresh = refresh_runtime_feedback(
        context.dependencies.template_build_ctx,
        context.runtime.execution_state.result_ledger.results,
    )
    apply_feedback_refresh(context, feedback_refresh)
    return feedback_refresh


def execute_schedule_round(
    context: ScheduleRoundContext,
    *,
    round_index: int,
) -> ScheduleRoundResult:
    """Execute one scheduling round across every remaining field."""
    scheduler_options = context.dependencies.scheduler_options
    execution_state = context.runtime.execution_state
    progressed_this_round = False
    last_field_id = ""
    context.runtime.seed_phase.sync(execution_state)
    if execution_state.future_queue.should_stop_scheduling():
        return ScheduleRoundResult(
            progressed=False,
            stop_requested=True,
            last_field_id="",
        )
    logger.info(
        "[schedule] round=%d phase=%s breadth-first batch_size=%d fields=%d",
        round_index,
        context.runtime.seed_phase.phase_name,
        context.runtime.field_template_batch_size,
        len(context.fields),
    )

    for field_index, field in enumerate(context.fields, start=1):
        if context.reached_simulation_budget():
            logger.info(
                "[stop] 达到 max-new-simulations=%d seed_fields_unresolved=%d "
                "seed_fields_inflight=%d",
                scheduler_options.max_new_simulations,
                context.runtime.seed_phase.remaining_count,
                len(context.runtime.seed_phase.inflight_field_ids),
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
    """Schedule one field through a short-lived field scheduling session."""
    return FieldSchedulingSession(
        context=context,
        field=field,
        field_index=field_index,
        total_fields=total_fields,
        round_index=round_index,
    ).execute()


class FieldSchedulingSession:
    """Own the feedback, queue, dispatch, and checkpoint work for one field."""

    def __init__(
        self,
        *,
        context: ScheduleRoundContext,
        field: TemplateField,
        field_index: int,
        total_fields: int,
        round_index: int,
    ) -> None:
        self.context = context
        self.field = field
        self.field_index = field_index
        self.total_fields = total_fields
        self.round_index = round_index
        self.execution_state = context.runtime.execution_state
        self.runtime_state = context.runtime.runtime_state
        self.field_id = str(first_non_empty(field.field_id, SENTINEL_UNKNOWN))
        self.field_name = choose_field_name(field)
        self.field_type = choose_field_type(field)
        self.seed_phase_active = context.runtime.seed_phase.active

    def execute(self) -> ScheduleRoundResult:
        """Run the field's scheduling lifecycle and persist its final state."""
        if self.context.runtime.seed_phase.should_wait_or_skip(self.field_id):
            return self._result(progressed=False)
        if should_skip_field(
            self.field_id,
            self.field_name,
            self.context.dependencies.filters,
        ):
            progressed = self._resolve_seed_field()
            self._persist_checkpoint()
            return self._result(progressed=progressed)

        template_queue = self._template_queue()
        pending_count = len(template_queue.entries)
        seed_resolution_progressed = (
            self._resolve_seed_field() if self.seed_phase_active and pending_count == 0 else False
        )
        logger.debug(
            "[progress] 字段 %d/%d field_id=%s templates=%d pending=%d filtered=%d",
            self.field_index,
            self.total_fields,
            self.field_id,
            template_queue.template_count,
            pending_count,
            template_queue.filtered_templates,
        )
        scheduled_templates = (
            template_queue.peek_seed()
            if self.seed_phase_active
            else template_queue.peek(self.context.runtime.field_template_batch_size)
        )
        deferred_templates = max(0, pending_count - len(scheduled_templates))
        progressed = bool(scheduled_templates) or seed_resolution_progressed
        if deferred_templates > 0:
            logger.debug(
                "[schedule] field=%s round=%d dispatch=%d deferred=%d",
                self.field_id,
                self.round_index,
                len(scheduled_templates),
                deferred_templates,
            )

        queue_count_before_dispatch = len(template_queue.entries)
        stop_requested = dispatch_templates_for_field(
            context=self.context,
            field=self.field,
            field_id=self.field_id,
            field_name=self.field_name,
            field_type=self.field_type,
            scheduled_templates=scheduled_templates,
            template_queue=template_queue,
        )
        if self.seed_phase_active and len(template_queue.entries) < queue_count_before_dispatch:
            self.context.runtime.seed_phase.mark_inflight(self.field_id)
        self._persist_checkpoint()
        return self._result(progressed=progressed, stop_requested=stop_requested)

    def _template_queue(self) -> FieldTemplateQueue:
        template_queue = self.context.runtime.field_template_queues.get(self.field_id)
        if template_queue is not None:
            return template_queue
        pending_templates, filtered_templates, template_count = build_pending_templates_for_field(
            self.context.dependencies.template_build_ctx,
            self.field,
            attempted_keys=(
                self.execution_state.attempted_keys
                | self.execution_state.queue_retry_state.exhausted_keys
            ),
            prior_results=[
                *self.context.dependencies.historical_state.feedback_results,
                *self.execution_state.result_ledger.results,
            ],
            reserved_keys=inflight_template_keys(self.execution_state.future_queue.pending_futures),
        )
        template_queue = FieldTemplateQueue.create(
            pending_templates,
            filtered_templates=filtered_templates,
            template_count=template_count,
        )
        self.context.runtime.field_template_queues[self.field_id] = template_queue
        return template_queue

    def _resolve_seed_field(self) -> bool:
        return self.context.runtime.seed_phase.resolve(self.field_id)

    def _persist_checkpoint(self) -> None:
        persist_replanning_checkpoint(
            state_file=self.context.dependencies.state_file,
            execution_state=self.execution_state,
            runtime_state=self.runtime_state,
            identity=_checkpoint_identity(self.context),
        )

    def _result(
        self,
        *,
        progressed: bool,
        stop_requested: bool = False,
    ) -> ScheduleRoundResult:
        return ScheduleRoundResult(
            progressed=progressed,
            stop_requested=stop_requested,
            last_field_id=self.field_id,
        )
