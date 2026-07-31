"""Focused loaders for bootstrap resource assembly."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from ..config.models import DatasetExpressionPolicy
from ..models.domain import TemplateField, TemplateLibrary
from ..models.io_types import RunFilters, RunPaths
from ..models.runtime_options import FieldFetchOptions
from ..runtime.contexts import HistoricalRunState
from .bootstrap_types import (
    BootstrapPaths,
    FieldLoadingServices,
    SupportingResourceServices,
)

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
    paths: BootstrapPaths,
    effective_run_paths: RunPaths,
    services: SupportingResourceServices,
) -> BootstrapLoadedResources:
    """Load template library, blacklist, filters, and historical feedback state."""
    return load_supporting_resources(
        dataset_id=dataset_id,
        paths=paths,
        effective_run_paths=effective_run_paths,
        services=services,
        repair_corrupt_summary=True,
        log_blacklist=True,
    )


def load_supporting_resources(
    *,
    dataset_id: str,
    paths: BootstrapPaths,
    effective_run_paths: RunPaths,
    services: SupportingResourceServices,
    repair_corrupt_summary: bool,
    log_blacklist: bool = True,
) -> BootstrapLoadedResources:
    """Load local template, filter, policy, and history resources for a run plan."""
    services.set_active_datasets_root(paths.datasets_root)
    template_library_file = services.ensure_dataset_template_library(
        paths.template_library_file, dataset_id
    )

    template_library = services.load_template_library(template_library_file)
    logger.info(
        "[templates] dataset=%s library=%s entries=%d",
        dataset_id,
        template_library_file,
        sum(len(items) for items in template_library.values()),
    )

    if log_blacklist:
        blacklist_path = services.ensure_template_blacklist_file(dataset_id)
        blacklist_payload = services.read_blacklist_payload(dataset_id)
        learned_count, rule_count = services.summarize_blacklist_payload(blacklist_payload)
        logger.info(
            "[blacklist] dataset=%s file=%s learned_templates=%d expression_rules=%d",
            dataset_id,
            blacklist_path,
            learned_count,
            rule_count,
        )

    return BootstrapLoadedResources(
        template_library=template_library,
        filters=services.load_run_filters_extended(effective_run_paths),
        expression_policy=services.get_dataset_expression_policy(dataset_id),
        historical_state=services.build_historical_run_state(
            paths.output_file,
            paths.feedback_output,
            repair_corrupt_summary=repair_corrupt_summary,
        ),
    )


def load_bootstrap_fields(
    *,
    dataset_id: str,
    bootstrap_client,
    paths: BootstrapPaths,
    field_fetch_options: FieldFetchOptions,
    services: FieldLoadingServices,
) -> list[TemplateField]:
    """Load cached fields and refresh from the upstream source when needed."""
    cached_fields = services.load_fields_cache(
        paths.fields_cache_file,
        dataset_id=dataset_id,
        region=field_fetch_options.region,
        universe=field_fetch_options.universe,
        instrument_type=field_fetch_options.instrument_type,
        delay=field_fetch_options.delay,
    )
    return services.fetch_fields_with_cache(
        bootstrap_client,
        field_fetch_options,
        paths.fields_cache_file,
        cached_fields,
    )
