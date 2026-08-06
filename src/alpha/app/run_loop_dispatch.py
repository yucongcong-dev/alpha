"""Template dispatch helpers for breadth-first run-loop scheduling."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..core.scheduler import maybe_restore_runtime_concurrency, throttle_before_submission
from ..models.domain import TemplateField
from ..runtime.contexts import PendingTemplateEntry
from ..runtime.field_template_queue import FieldTemplateQueue
from .loop_future_support import drain_until_capacity, submit_template_future
from .run_loop_feedback import RuntimeFeedbackRefresh, refresh_runtime_feedback

if TYPE_CHECKING:
    from .run_loop_rounds import ScheduleRoundContext

logger = logging.getLogger(__name__)


def apply_feedback_refresh(
    context: ScheduleRoundContext,
    feedback_refresh: RuntimeFeedbackRefresh,
) -> None:
    """Invalidate cached field queues affected by newly consumed runtime feedback."""
    if feedback_refresh.invalidate_all:
        context.field_template_queues.clear()
        return
    invalidated_field_ids = feedback_refresh.changed_field_ids | feedback_refresh.retry_field_ids
    for field_id in invalidated_field_ids:
        context.field_template_queues.pop(field_id, None)


def dispatch_templates_for_field(
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
        if execution_state.future_queue.should_stop_scheduling():
            return True

        maybe_restore_runtime_concurrency(runtime_state)
        result_count_before_drain = len(result_ledger.results)
        drain_until_capacity(
            executor_state=execution_state,
            runtime_state=runtime_state,
            scheduler_options=scheduler_options,
            completion_ctx=context.completion_ctx,
            field_id=field_id,
        )
        if execution_state.future_queue.should_stop_scheduling():
            return True
        if len(result_ledger.results) != result_count_before_drain:
            feedback_refresh = refresh_runtime_feedback(
                context.template_build_ctx,
                result_ledger.results,
            )
            apply_feedback_refresh(context, feedback_refresh)
            if feedback_refresh.invalidate_all or field_id in (
                feedback_refresh.changed_field_ids | feedback_refresh.retry_field_ids
            ):
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
