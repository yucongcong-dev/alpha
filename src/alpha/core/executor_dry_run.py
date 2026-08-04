"""Dry-run planning output helpers for executor."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, MutableMapping, Sequence
import logging
from typing import Protocol

from ..analysis.field_stats import decay_field_feedback
from ..config.constants import (
    DRY_RUN_SAMPLE_LIMIT,
    FEEDBACK_STAGE_RESIMULATE,
    SENTINEL_UNKNOWN,
    STAT_FIELD_ATTEMPTED_TEMPLATES,
    STATS_DEFAULT_SCORE,
)
from ..generators.fields import choose_field_name
from ..models.domain import FieldTestResult, TemplateField, TemplateLibrary
from ..models.io_types import RunFilters
from ..models.runtime_protocols import TemplateBuildArgs
from ..policy.expression import get_dataset_expression_policy, resolve_feedback_stage
from ..runtime.contexts import (
    HistoricalRunState,
    PendingTemplateEntry,
    TemplateBuildContext,
)
from ..runtime.state import ExecutionState
from ..utils.helpers import first_non_empty

logger = logging.getLogger(__name__)


class TemplateBuildContextBuilder(Protocol):
    """Build the shared template planning context for a dry-run plan."""

    def __call__(
        self,
        *,
        args: TemplateBuildArgs,
        fields: Sequence[TemplateField],
        template_library: TemplateLibrary,
        historical_state: HistoricalRunState,
        filters: RunFilters,
        use_dataset_heuristics: bool,
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


FieldSkipPredicate = Callable[[str, str, RunFilters, set[str]], bool]
FieldSkipReasonResolver = Callable[[str, str, RunFilters, set[str]], str | None]


def _record_feedback_explain_counts(
    explain_counts: Counter[str],
    build_ctx: TemplateBuildContext,
    field_id: str,
    *,
    args: TemplateBuildArgs,
) -> None:
    """Record why one field enters generate or resimulate planning."""
    options = getattr(build_ctx, "options", args)
    expression_policy = getattr(
        build_ctx, "expression_policy", None
    ) or get_dataset_expression_policy(str(getattr(options, "dataset_id", "") or ""))
    field_feedback_map = getattr(build_ctx, "field_feedback", {}) or {}
    raw_feedback = (
        field_feedback_map.get(field_id) if isinstance(field_feedback_map, dict) else None
    )
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


def print_dry_run_plan(
    *,
    args: TemplateBuildArgs,
    fields: Sequence[TemplateField],
    filters: RunFilters,
    template_library: TemplateLibrary,
    historical_state: HistoricalRunState,
    execution_state: ExecutionState,
    use_dataset_heuristics: bool,
    build_context: TemplateBuildContextBuilder,
    should_skip: FieldSkipPredicate,
    resolve_skip_reason: FieldSkipReasonResolver | None,
    build_pending: FieldPendingTemplateBuilder,
    sample_limit: int = DRY_RUN_SAMPLE_LIMIT,
    log: logging.Logger = logger,
) -> None:
    """Print the planned field/template queue without creating simulations."""
    planned_fields = 0
    eligible_templates = 0
    filtered_templates = 0
    unactionable_fields = 0
    explain_counts: Counter[str] = Counter()
    samples: list[dict[str, object]] = []
    build_ctx = build_context(
        args=args,
        fields=fields,
        template_library=template_library,
        historical_state=historical_state,
        filters=filters,
        use_dataset_heuristics=use_dataset_heuristics,
        existing_results_count=len(execution_state.result_ledger.results),
    )

    for field in fields:
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        field_name = choose_field_name(field)
        if should_skip(
            field_id,
            field_name,
            filters,
            execution_state.field_queue.skipped_fields,
        ):
            explain_counts["field_skipped"] += 1
            skip_reason = (
                resolve_skip_reason(
                    field_id,
                    field_name,
                    filters,
                    execution_state.field_queue.skipped_fields,
                )
                if resolve_skip_reason is not None
                else None
            )
            explain_counts[f"field_skipped_{skip_reason or 'unknown'}"] += 1
            continue
        _record_feedback_explain_counts(
            explain_counts,
            build_ctx,
            field_id,
            args=args,
        )
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
        for entry in pending_templates:
            if len(samples) >= sample_limit:
                break
            samples.append(
                {
                    "field_id": field_id,
                    "field_name": field_name,
                    "template_name": entry.template_name,
                    "priority": entry.priority,
                    "settings": entry.variant_fingerprint,
                    "expression": entry.expression,
                }
            )

    simulation_budget = max(0, int(getattr(args, "max_total_simulations", 0) or 0))
    scheduled_templates = (
        min(eligible_templates, simulation_budget) if simulation_budget > 0 else eligible_templates
    )
    budget_truncated = scheduled_templates < eligible_templates

    log.info("[dry-run] simulation creation is disabled; this is a plan only")
    log.info("[dry-run] planned_fields=%d", planned_fields)
    log.info("[dry-run] eligible_simulations=%d", eligible_templates)
    log.info("[dry-run] scheduled_simulations=%d", scheduled_templates)
    log.info("[dry-run] budget_truncated=%s", str(budget_truncated).lower())
    log.info("[dry-run] filtered_templates=%d", filtered_templates)
    log.info("[dry-run] unactionable_fields=%d", unactionable_fields)
    log.info("[dry-run] existing_results=%d", len(execution_state.result_ledger.results))
    log.info("[dry-run] attempted_keys=%d", len(execution_state.attempted_keys))
    log.info(
        "[dry-run] explain_summary fields_total=%d planned=%d skipped=%d "
        "unactionable=%d templates_eligible=%d templates_scheduled=%d "
        "templates_filtered=%d",
        len(fields),
        explain_counts["field_planned"],
        explain_counts["field_skipped"],
        explain_counts["field_unactionable"],
        eligible_templates,
        scheduled_templates,
        explain_counts["templates_filtered"],
    )
    log.info(
        "[dry-run] explain_fields skipped_queue=%d skipped_include=%d "
        "skipped_exclude=%d skipped_unknown=%d unactionable=%d",
        explain_counts["field_skipped_queue"],
        explain_counts["field_skipped_include"],
        explain_counts["field_skipped_exclude"],
        explain_counts["field_skipped_unknown"],
        explain_counts["field_unactionable"],
    )
    log.info(
        "[dry-run] explain_templates name_filter=%d feedback=%d family=%d history=%d",
        explain_counts["template_filtered_name_filter"],
        explain_counts["template_filtered_feedback"],
        explain_counts["template_filtered_family"],
        explain_counts["template_filtered_history"],
    )
    log.info(
        "[dry-run] explain_blacklist name_stage=%d name_stage_family=%d "
        "name_family=%d legacy_name_only=%d pattern_expression=%d "
        "pattern_template_name=%d other=%d",
        explain_counts["template_filtered_blacklist_name_stage"],
        explain_counts["template_filtered_blacklist_name_stage_family"],
        explain_counts["template_filtered_blacklist_name_family"],
        explain_counts["template_filtered_blacklist_legacy_name_only"],
        _sum_counter_prefix(explain_counts, "template_filtered_blacklist_pattern_expression_"),
        _sum_counter_prefix(explain_counts, "template_filtered_blacklist_pattern_template_name_"),
        _sum_blacklist_other(explain_counts),
    )
    log.info(
        "[dry-run] explain_feedback generate_no_feedback=%d generate_attempts=%d "
        "generate_score=%d generate_other=%d resimulate=%d settings_budget=%d",
        explain_counts["feedback_generate_no_feedback"],
        explain_counts["feedback_generate_attempts"],
        explain_counts["feedback_generate_score"],
        explain_counts["feedback_generate_other"],
        explain_counts["feedback_resimulate"],
        explain_counts["feedback_settings_budget"],
    )
    for index, field in enumerate(fields[:sample_limit], start=1):
        log.info(
            "[dry-run] field %d/%d id=%s rank=%s score=%.4f family=%s reason=%s "
            "coverage=%.4f alpha_count=%d user_count=%d",
            index,
            min(len(fields), sample_limit),
            str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
            field.get("selection_rank", "?"),
            float(field.get("selection_score", 0.0) or 0.0),
            field.get("selection_family", "unknown"),
            field.get("selection_reason", "unknown"),
            float(field.get("coverage", 0.0) or 0.0),
            int(field.get("alphaCount", 0) or 0),
            int(field.get("userCount", 0) or 0),
        )
    for index, sample in enumerate(samples, start=1):
        log.info(
            "[dry-run] sample %d/%d field=%s template=%s priority=%d settings=%s expression=%s",
            index,
            len(samples),
            sample["field_id"],
            sample["template_name"],
            sample["priority"],
            sample["settings"],
            sample["expression"],
        )


def _sum_counter_prefix(explain_counts: Counter[str], prefix: str) -> int:
    """Sum dry-run counters with one shared prefix."""
    return sum(count for key, count in explain_counts.items() if key.startswith(prefix))


def _sum_blacklist_other(explain_counts: Counter[str]) -> int:
    """Count blacklist reasons not represented by the stable explain buckets."""
    known_keys = {
        "template_filtered_blacklist_name_stage",
        "template_filtered_blacklist_name_stage_family",
        "template_filtered_blacklist_name_family",
        "template_filtered_blacklist_legacy_name_only",
    }
    return sum(
        count
        for key, count in explain_counts.items()
        if key.startswith("template_filtered_blacklist_")
        and key not in known_keys
        and not key.startswith("template_filtered_blacklist_pattern_expression_")
        and not key.startswith("template_filtered_blacklist_pattern_template_name_")
    )
