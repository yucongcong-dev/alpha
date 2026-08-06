"""Supporting resource loading shared by live bootstrap and dry-run planning."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from ..analysis.feedback_history import build_historical_run_state
from ..cli.filters import load_run_filters_extended
from ..config.models import DatasetExpressionPolicy
from ..generators.templates.library_loader import load_template_library
from ..generators.templates.library_store import ensure_dataset_template_library
from ..models.domain import TemplateLibrary
from ..models.io_types import RunFilters, RunPaths
from ..policy.blacklist_context import set_active_datasets_root
from ..policy.blacklist_store import (
    ensure_template_blacklist_file,
    read_blacklist_payload,
    summarize_blacklist_payload,
)
from ..policy.expression import get_dataset_expression_policy
from ..runtime.contexts import HistoricalRunState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BootstrapLoadedResources:
    """Non-field bootstrap resources loaded before field fetch and ranking."""

    template_library: TemplateLibrary
    filters: RunFilters
    expression_policy: DatasetExpressionPolicy
    historical_state: HistoricalRunState


def load_bootstrap_supporting_resources(
    *,
    dataset_id: str,
    paths: RunPaths,
    backfill_window: int,
) -> BootstrapLoadedResources:
    """Load template library, blacklist, filters, and historical feedback state."""
    return load_supporting_resources(
        dataset_id=dataset_id,
        paths=paths,
        backfill_window=backfill_window,
        repair_corrupt_summary=True,
        log_blacklist=True,
    )


def load_supporting_resources(
    *,
    dataset_id: str,
    paths: RunPaths,
    backfill_window: int,
    repair_corrupt_summary: bool,
    log_blacklist: bool = True,
) -> BootstrapLoadedResources:
    """Load local template, filter, policy, and history resources for a run plan."""
    set_active_datasets_root(paths.datasets_root)
    template_library_file = ensure_dataset_template_library(paths.template_library_file, dataset_id)

    template_library = load_template_library(
        template_library_file,
        default_backfill_window=backfill_window,
    )
    logger.info(
        "[templates] dataset=%s library=%s entries=%d",
        dataset_id,
        template_library_file,
        sum(len(items) for items in template_library.values()),
    )

    if log_blacklist:
        blacklist_path = ensure_template_blacklist_file(dataset_id)
        blacklist_payload = read_blacklist_payload(dataset_id)
        learned_count, rule_count = summarize_blacklist_payload(blacklist_payload)
        logger.info(
            "[blacklist] dataset=%s file=%s learned_templates=%d expression_rules=%d",
            dataset_id,
            blacklist_path,
            learned_count,
            rule_count,
        )
    return BootstrapLoadedResources(
        template_library=template_library,
        filters=load_run_filters_extended(paths),
        expression_policy=get_dataset_expression_policy(dataset_id),
        historical_state=build_historical_run_state(
            paths.output,
            paths.feedback_output,
            repair_corrupt_summary=repair_corrupt_summary,
        ),
    )
