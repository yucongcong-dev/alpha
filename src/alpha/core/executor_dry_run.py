"""Dry-run planning output helpers for executor."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import logging
from typing import Protocol

from ..config.constants import DRY_RUN_SAMPLE_LIMIT, SENTINEL_UNKNOWN
from ..generators.fields import choose_field_name
from ..models.domain import FieldTestResult, TemplateField, TemplateLibrary
from ..models.io_types import RunFilters
from ..models.runtime_protocols import TemplateBuildArgs
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
    ) -> tuple[list[PendingTemplateEntry], int, int]: ...


FieldSkipPredicate = Callable[[str, str, RunFilters, set[str]], bool]


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
    build_pending: FieldPendingTemplateBuilder,
    sample_limit: int = DRY_RUN_SAMPLE_LIMIT,
    log: logging.Logger = logger,
) -> None:
    """Print the planned field/template queue without creating simulations."""
    planned_fields = 0
    planned_templates = 0
    filtered_templates = 0
    unactionable_fields = 0
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
            continue
        pending_templates, filtered_count, _template_count = build_pending(
            build_ctx,
            field,
            attempted_keys=execution_state.attempted_keys,
            prior_results=[
                *historical_state.feedback_results,
                *execution_state.result_ledger.results,
            ],
        )
        if not pending_templates:
            unactionable_fields += 1
            continue
        planned_fields += 1
        planned_templates += len(pending_templates)
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

    log.info("[dry-run] simulation creation is disabled; this is a plan only")
    log.info("[dry-run] planned_fields=%d", planned_fields)
    log.info("[dry-run] planned_simulations=%d", planned_templates)
    log.info("[dry-run] filtered_templates=%d", filtered_templates)
    log.info("[dry-run] unactionable_fields=%d", unactionable_fields)
    log.info("[dry-run] existing_results=%d", len(execution_state.result_ledger.results))
    log.info("[dry-run] attempted_keys=%d", len(execution_state.attempted_keys))
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
