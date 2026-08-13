"""Dry-run plan construction helpers for executor."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, MutableMapping, Sequence
import logging
from typing import Protocol

from ..analysis.field_stats import decay_field_feedback
from ..config._constants_strings import (
    FEEDBACK_STAGE_RESIMULATE,
    SENTINEL_UNKNOWN,
    STAT_FIELD_ATTEMPTED_TEMPLATES,
)
from ..config._constants_thresholds import (
    DRY_RUN_SAMPLE_LIMIT,
    STATS_DEFAULT_SCORE,
)
from ..config.models import DatasetExpressionPolicy
from ..generators.fields import choose_field_name
from ..models.domain import FieldTestResult, TemplateField, TemplateLibrary
from ..models.io_types import RunFilters
from ..models.runtime_options import TemplateBuildOptions
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage
from ..runtime.contexts import (
    HistoricalRunState,
    PendingTemplateEntry,
    TemplateBuildContext,
)
from ..runtime.field_template_queue import select_seed_candidate
from ..runtime.state import ExecutionState
from ..utils.helpers import first_non_empty
from .executor_dry_run_report import (
    DryRunPlanSummary,
    DryRunSample,
    render_dry_run_plan,
)

logger = logging.getLogger(__name__)


class TemplateBuildContextBuilder(Protocol):
    """Build the shared template planning context for a dry-run plan."""

    def __call__(
        self,
        *,
        options: TemplateBuildOptions,
        fields: Sequence[TemplateField],
        template_library: TemplateLibrary,
        historical_state: HistoricalRunState,
        filters: RunFilters,
        expression_policy: DatasetExpressionPolicy,
        existing_results_count: int,
    ) -> TemplateBuildContext: ...


class FieldPendingTemplateBuilder(Protocol):
    """Build executable template entries for one field."""

    def __call__(
        self,
        build_ctx: TemplateBuildContext,
        field: TemplateField,
        *,
        attempted_keys: set[tuple[str, str, str, str]],
        prior_results: Sequence[FieldTestResult],
        reserved_keys: set[tuple[str, str, str, str]] | None = None,
        template_skip_reasons: MutableMapping[str, int] | None = None,
    ) -> tuple[list[PendingTemplateEntry], int, int]: ...


FieldSkipPredicate = Callable[[str, str, RunFilters], bool]
FieldSkipReasonResolver = Callable[[str, str, RunFilters], str | None]


def _record_feedback_explain_counts(
    explain_counts: Counter[str],
    build_ctx: TemplateBuildContext,
    field_id: str,
) -> None:
    """Record why one field enters generate or resimulate planning."""
    expression_policy = build_ctx.expression_policy or get_dataset_expression_policy(
        build_ctx.options.dataset_id,
        default_backfill_window=build_ctx.options.backfill_window,
    )
    raw_feedback = build_ctx.field_feedback.get(field_id)
    field_feedback = decay_field_feedback(
        raw_feedback,
        half_life_days=expression_policy.field_feedback_half_life_days,
    )
    if not field_feedback:
        explain_counts["feedback_generate_no_feedback"] += 1
        explain_counts["feedback_settings_budget"] += (
            expression_policy.feedback_loop_policy.generate.settings_variant_budget
        )
        return

    feedback_stage = resolve_feedback_stage(
        field_feedback,
        expression_policy.feedback_loop_policy,
    )
    if feedback_stage == FEEDBACK_STAGE_RESIMULATE:
        explain_counts["feedback_resimulate"] += 1
        explain_counts["feedback_settings_budget"] += (
            expression_policy.feedback_loop_policy.resimulate.settings_variant_budget
        )
        return

    attempted = int(field_feedback.get(STAT_FIELD_ATTEMPTED_TEMPLATES, 0) or 0)
    best_score = float(field_feedback.get("best_score", STATS_DEFAULT_SCORE) or STATS_DEFAULT_SCORE)
    if attempted < expression_policy.feedback_loop_policy.resimulate.min_attempted_templates:
        explain_counts["feedback_generate_attempts"] += 1
    elif best_score < expression_policy.feedback_loop_policy.resimulate.min_best_score:
        explain_counts["feedback_generate_score"] += 1
    else:
        explain_counts["feedback_generate_other"] += 1
    explain_counts["feedback_settings_budget"] += (
        expression_policy.feedback_loop_policy.generate.settings_variant_budget
    )


def build_dry_run_plan_summary(
    *,
    options: TemplateBuildOptions,
    fields: Sequence[TemplateField],
    filters: RunFilters,
    template_library: TemplateLibrary,
    historical_state: HistoricalRunState,
    execution_state: ExecutionState,
    expression_policy: DatasetExpressionPolicy,
    build_context: TemplateBuildContextBuilder,
    should_skip: FieldSkipPredicate,
    resolve_skip_reason: FieldSkipReasonResolver | None,
    build_pending: FieldPendingTemplateBuilder,
    full_run: bool,
    max_new_simulations: int,
    sample_limit: int = DRY_RUN_SAMPLE_LIMIT,
) -> DryRunPlanSummary:
    """Build the planned queue and its explain counters without rendering output."""
    planned_fields = 0
    eligible_templates = 0
    filtered_templates = 0
    unactionable_fields = 0
    attempted_field_ids = {
        field_id for field_id, _template, _expression, _settings in execution_state.attempted_keys
    }
    seed_fields_remaining = 0
    seed_fields_resolved = 0
    seed_templates_eligible = 0
    refine_templates_eligible = 0
    explain_counts: Counter[str] = Counter()
    seed_samples: list[DryRunSample] = []
    refine_samples: list[DryRunSample] = []
    build_ctx = build_context(
        options=options,
        fields=fields,
        template_library=template_library,
        historical_state=historical_state,
        filters=filters,
        expression_policy=expression_policy,
        existing_results_count=len(execution_state.result_ledger.results),
    )
    build_ctx.candidate_filter_counts = explain_counts

    for field in fields:
        field_id = str(first_non_empty(field.field_id, SENTINEL_UNKNOWN))
        field_name = choose_field_name(field)
        if should_skip(field_id, field_name, filters):
            explain_counts["field_skipped"] += 1
            skip_reason = (
                resolve_skip_reason(field_id, field_name, filters)
                if resolve_skip_reason is not None
                else None
            )
            explain_counts[f"field_skipped_{skip_reason or 'unknown'}"] += 1
            continue
        _record_feedback_explain_counts(explain_counts, build_ctx, field_id)
        pending_templates, filtered_count, _template_count = build_pending(
            build_ctx,
            field,
            attempted_keys=execution_state.attempted_keys,
            prior_results=[
                *historical_state.feedback_results,
                *execution_state.result_ledger.results,
            ],
            template_skip_reasons=explain_counts,
        )
        if filtered_count:
            explain_counts["templates_filtered"] += filtered_count
        if not pending_templates:
            unactionable_fields += 1
            explain_counts["field_unactionable"] += 1
            continue
        planned_fields += 1
        explain_counts["field_planned"] += 1
        eligible_templates += len(pending_templates)
        filtered_templates += filtered_count
        if full_run:
            if field_id in attempted_field_ids:
                seed_fields_resolved += 1
            else:
                seed_fields_remaining += 1
        sample_is_seed = full_run and field_id not in attempted_field_ids
        seed_entry = select_seed_candidate(pending_templates) if sample_is_seed else None
        if seed_entry is not None:
            seed_templates_eligible += 1
        refine_templates_eligible += len(pending_templates) - (1 if seed_entry else 0)
        sample_entries = [seed_entry] if seed_entry is not None else pending_templates
        sample_target = seed_samples if sample_is_seed else refine_samples
        for entry in sample_entries:
            if len(sample_target) >= sample_limit:
                break
            sample_target.append(
                DryRunSample(
                    field_id=field_id,
                    template_name=entry.template_name,
                    priority=entry.priority,
                    settings=entry.variant_fingerprint,
                    expression=entry.expression,
                )
            )

    samples = (
        (seed_samples + refine_samples)[:sample_limit]
        if full_run
        else refine_samples[:sample_limit]
    )
    simulation_budget = max(0, max_new_simulations)
    scheduled_templates = (
        min(eligible_templates, simulation_budget) if simulation_budget > 0 else eligible_templates
    )
    if full_run:
        if simulation_budget > 0:
            seed_templates_scheduled = min(seed_templates_eligible, simulation_budget)
            refine_templates_scheduled = min(
                refine_templates_eligible,
                max(0, simulation_budget - seed_templates_scheduled),
            )
        else:
            seed_templates_scheduled = seed_templates_eligible
            refine_templates_scheduled = refine_templates_eligible
    else:
        seed_templates_scheduled = 0
        refine_templates_scheduled = scheduled_templates
    return DryRunPlanSummary(
        fields_total=len(fields),
        planned_fields=planned_fields,
        eligible_templates=eligible_templates,
        seed_templates_eligible=seed_templates_eligible,
        refine_templates_eligible=refine_templates_eligible,
        scheduled_templates=scheduled_templates,
        seed_templates_scheduled=seed_templates_scheduled,
        refine_templates_scheduled=refine_templates_scheduled,
        budget_truncated=scheduled_templates < eligible_templates,
        full_run=full_run,
        seed_fields_resolved=seed_fields_resolved,
        seed_fields_remaining=seed_fields_remaining,
        seed_budget_sufficient=(
            simulation_budget <= 0 or simulation_budget >= seed_fields_remaining
        ),
        filtered_templates=filtered_templates,
        unactionable_fields=unactionable_fields,
        existing_results=len(execution_state.result_ledger.results),
        attempted_keys=len(execution_state.attempted_keys),
        explain_counts=explain_counts,
        field_samples=tuple(fields[:sample_limit]),
        samples=tuple(samples),
    )


def print_dry_run_plan(
    *,
    options: TemplateBuildOptions,
    fields: Sequence[TemplateField],
    filters: RunFilters,
    template_library: TemplateLibrary,
    historical_state: HistoricalRunState,
    execution_state: ExecutionState,
    expression_policy: DatasetExpressionPolicy,
    build_context: TemplateBuildContextBuilder,
    should_skip: FieldSkipPredicate,
    resolve_skip_reason: FieldSkipReasonResolver | None,
    build_pending: FieldPendingTemplateBuilder,
    full_run: bool,
    max_new_simulations: int,
    sample_limit: int = DRY_RUN_SAMPLE_LIMIT,
    log: logging.Logger = logger,
) -> None:
    """Build and render the planned field/template queue without creating simulations."""
    summary = build_dry_run_plan_summary(
        options=options,
        fields=fields,
        filters=filters,
        template_library=template_library,
        historical_state=historical_state,
        execution_state=execution_state,
        expression_policy=expression_policy,
        build_context=build_context,
        should_skip=should_skip,
        resolve_skip_reason=resolve_skip_reason,
        build_pending=build_pending,
        sample_limit=sample_limit,
        full_run=full_run,
        max_new_simulations=max_new_simulations,
    )
    render_dry_run_plan(summary, log=log)
