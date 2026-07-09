"""Focused loaders for bootstrap resource assembly."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config.models import DatasetExpressionPolicy
from ..models.domain import TemplateField, TemplateLibrary
from ..models.io_types import RunFilters, RunPaths
from ..models.runtime_options import FieldFetchOptions
from ..runtime import HistoricalRunState
from .bootstrap_types import BootstrapPaths

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
    set_active_blacklists_dir_fn,
    ensure_dataset_template_library_fn,
    ensure_template_blacklist_file_fn,
    load_template_library_fn,
    read_blacklist_payload_fn,
    summarize_blacklist_payload_fn,
    load_run_filters_extended_fn,
    get_dataset_expression_policy_fn,
    build_historical_run_state_fn,
) -> BootstrapLoadedResources:
    """Load template library, blacklist, filters, and historical feedback state."""
    set_active_blacklists_dir_fn()
    template_library_file = ensure_dataset_template_library_fn(paths.template_library_file, dataset_id)
    blacklist_path = ensure_template_blacklist_file_fn(dataset_id)

    template_library = load_template_library_fn(template_library_file)
    logger.info(
        "[templates] dataset=%s library=%s entries=%d",
        dataset_id,
        template_library_file,
        sum(len(items) for items in template_library.values()),
    )

    blacklist_payload = read_blacklist_payload_fn(dataset_id)
    learned_count, rule_count = summarize_blacklist_payload_fn(blacklist_payload)
    logger.info(
        "[blacklist] dataset=%s file=%s learned_templates=%d expression_rules=%d",
        dataset_id,
        blacklist_path,
        learned_count,
        rule_count,
    )

    return BootstrapLoadedResources(
        template_library=template_library,
        filters=load_run_filters_extended_fn(effective_run_paths),
        expression_policy=get_dataset_expression_policy_fn(dataset_id),
        historical_state=build_historical_run_state_fn(paths.output_file, paths.feedback_output),
    )


def load_bootstrap_fields(
    *,
    dataset_id: str,
    bootstrap_client,
    paths: BootstrapPaths,
    field_fetch_options: FieldFetchOptions,
    load_fields_cache_fn,
    fetch_fields_with_cache_fn,
) -> list[TemplateField] | list[dict[str, object]]:
    """Load cached fields and refresh from the upstream source when needed."""
    cached_fields = load_fields_cache_fn(
        paths.fields_cache_file,
        dataset_id=dataset_id,
        region=field_fetch_options.region,
        universe=field_fetch_options.universe,
        instrument_type=field_fetch_options.instrument_type,
        delay=field_fetch_options.delay,
    )
    return fetch_fields_with_cache_fn(
        bootstrap_client,
        field_fetch_options,
        paths.fields_cache_file,
        cached_fields,
    )
