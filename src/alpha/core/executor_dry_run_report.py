"""Structured dry-run planning summaries and log rendering."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import logging

from ..config._constants_strings import SENTINEL_UNKNOWN
from ..models.domain import TemplateField
from ..utils.helpers import first_non_empty


@dataclass(frozen=True)
class DryRunSample:
    field_id: str
    template_name: str
    priority: int
    settings: str
    expression: str


@dataclass(frozen=True)
class DryRunPlanSummary:
    fields_total: int
    planned_fields: int
    eligible_templates: int
    scheduled_templates: int
    budget_truncated: bool
    full_run: bool
    seed_fields_resolved: int
    seed_fields_remaining: int
    seed_budget_sufficient: bool
    filtered_templates: int
    unactionable_fields: int
    existing_results: int
    attempted_keys: int
    explain_counts: Counter[str]
    field_samples: tuple[TemplateField, ...]
    samples: tuple[DryRunSample, ...]


def render_dry_run_plan(summary: DryRunPlanSummary, *, log: logging.Logger) -> None:
    """Render one structured dry-run summary using the stable log contract."""
    counts = summary.explain_counts
    log.info("[dry-run] simulation creation is disabled; this is a plan only")
    log.info("[dry-run] planned_fields=%d", summary.planned_fields)
    log.info("[dry-run] eligible_simulations=%d", summary.eligible_templates)
    log.info("[dry-run] scheduled_simulations=%d", summary.scheduled_templates)
    log.info("[dry-run] budget_truncated=%s", str(summary.budget_truncated).lower())
    if summary.full_run:
        seed_scheduled = min(summary.seed_fields_remaining, summary.scheduled_templates)
        refine_scheduled = max(0, summary.scheduled_templates - seed_scheduled)
        log.info(
            "[dry-run] full_run_seed resolved=%d remaining=%d budget_sufficient=%s",
            summary.seed_fields_resolved,
            summary.seed_fields_remaining,
            str(summary.seed_budget_sufficient).lower(),
        )
        log.info(
            "[dry-run] full_run_schedule seed=%d refine=%d",
            seed_scheduled,
            refine_scheduled,
        )
    log.info("[dry-run] filtered_templates=%d", summary.filtered_templates)
    log.info("[dry-run] unactionable_fields=%d", summary.unactionable_fields)
    log.info("[dry-run] existing_results=%d", summary.existing_results)
    log.info("[dry-run] attempted_keys=%d", summary.attempted_keys)
    log.info(
        "[dry-run] explain_summary fields_total=%d planned=%d skipped=%d "
        "unactionable=%d templates_eligible=%d templates_scheduled=%d "
        "templates_filtered=%d",
        summary.fields_total,
        counts["field_planned"],
        counts["field_skipped"],
        counts["field_unactionable"],
        summary.eligible_templates,
        summary.scheduled_templates,
        counts["templates_filtered"],
    )
    log.info(
        "[dry-run] explain_fields skipped_queue=%d skipped_include=%d "
        "skipped_exclude=%d skipped_unknown=%d unactionable=%d",
        counts["field_skipped_queue"],
        counts["field_skipped_include"],
        counts["field_skipped_exclude"],
        counts["field_skipped_unknown"],
        counts["field_unactionable"],
    )
    log.info(
        "[dry-run] explain_templates name_filter=%d feedback=%d family=%d history=%d",
        counts["template_filtered_name_filter"],
        counts["template_filtered_feedback"],
        counts["template_filtered_family"],
        counts["template_filtered_history"],
    )
    log.info(
        "[dry-run] explain_blacklist name_stage=%d name_stage_family=%d "
        "name_family=%d legacy_name_only=%d pattern_expression=%d "
        "pattern_template_name=%d other=%d",
        counts["template_filtered_blacklist_name_stage"],
        counts["template_filtered_blacklist_name_stage_family"],
        counts["template_filtered_blacklist_name_family"],
        counts["template_filtered_blacklist_legacy_name_only"],
        _sum_counter_prefix(counts, "template_filtered_blacklist_pattern_expression_"),
        _sum_counter_prefix(counts, "template_filtered_blacklist_pattern_template_name_"),
        _sum_blacklist_other(counts),
    )
    log.info(
        "[dry-run] explain_feedback generate_no_feedback=%d generate_attempts=%d "
        "generate_score=%d generate_other=%d resimulate=%d settings_budget=%d",
        counts["feedback_generate_no_feedback"],
        counts["feedback_generate_attempts"],
        counts["feedback_generate_score"],
        counts["feedback_generate_other"],
        counts["feedback_resimulate"],
        counts["feedback_settings_budget"],
    )
    for index, field in enumerate(summary.field_samples, start=1):
        log.info(
            "[dry-run] field %d/%d id=%s rank=%s score=%.4f family=%s reason=%s "
            "coverage=%.4f alpha_count=%d user_count=%d",
            index,
            len(summary.field_samples),
            str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
            field.get("selection_rank", "?"),
            float(field.get("selection_score", 0.0) or 0.0),
            field.get("selection_family", "unknown"),
            field.get("selection_reason", "unknown"),
            float(field.get("coverage", 0.0) or 0.0),
            int(field.get("alphaCount", 0) or 0),
            int(field.get("userCount", 0) or 0),
        )
    for index, sample in enumerate(summary.samples, start=1):
        log.info(
            "[dry-run] sample %d/%d field=%s template=%s priority=%d settings=%s expression=%s",
            index,
            len(summary.samples),
            sample.field_id,
            sample.template_name,
            sample.priority,
            sample.settings,
            sample.expression,
        )


def _sum_counter_prefix(explain_counts: Counter[str], prefix: str) -> int:
    return sum(count for key, count in explain_counts.items() if key.startswith(prefix))


def _sum_blacklist_other(explain_counts: Counter[str]) -> int:
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
