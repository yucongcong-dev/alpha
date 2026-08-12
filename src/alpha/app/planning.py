"""Read-only, offline dry-run planning entrypoint."""

from __future__ import annotations

import logging

from ..config.application import ApplicationConfig
from ..core.executor import print_dry_run_plan
from ..generators.fields import load_fields_cache
from ..models.runtime_options import (
    BootstrapFieldOptions,
    TemplateBuildOptions,
)
from .bootstrap_fields import prepare_fields_for_execution
from .bootstrap_state import create_execution_state
from .bootstrap_supporting_resources import load_supporting_resources

logger = logging.getLogger(__name__)


def run_dry_run_plan(args: ApplicationConfig) -> bool:
    """Print a plan from local resources without authentication or filesystem writes."""
    field_options = BootstrapFieldOptions.from_config(args)
    template_options = TemplateBuildOptions.from_config(args)
    paths = args.paths
    dataset_id = field_options.dataset_id

    supporting_resources = load_supporting_resources(
        dataset_id=dataset_id,
        paths=paths,
        backfill_window=template_options.backfill_window,
        repair_corrupt_summary=False,
        log_blacklist=False,
    )

    fields = load_fields_cache(
        paths.fields_cache_file,
        dataset_id=dataset_id,
        region=field_options.fetch.region,
        universe=field_options.fetch.universe,
        instrument_type=field_options.fetch.instrument_type,
        delay=field_options.fetch.delay,
        cache_ttl_hours=0,
    )
    if not fields:
        logger.error(
            "[dry-run] no matching local field cache at %s; dry-run is offline and cannot plan "
            "without a previously cached field list",
            paths.fields_cache_file,
        )
        logger.error(
            "[dry-run] populate the cache with one authenticated smoke run first, e.g. "
            "`python -m alpha --dataset-id %s --run-mode smoke`, or point "
            "--fields-cache-file at an existing cache from the same market scope",
            dataset_id,
        )
        return False

    prepared_fields, field_stats = prepare_fields_for_execution(
        list(fields),
        filters_dict=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        historical_state=supporting_resources.historical_state,
        selection_options=field_options.selection,
    )
    if not prepared_fields:
        logger.error("[dry-run] no fields remain after local filtering")
        return False
    logger.info(
        "[dry-run] field_filter cached=%d filtered=%d ranked=%d selected=%d "
        "families=%d unexplored=%d excluded_rule=%d low_coverage=%d "
        "low_date_coverage=%d low_alpha=%d low_user=%d high_alpha=%d high_user=%d",
        field_stats.get("cached_field_count", len(fields)),
        field_stats.get("filtered_field_count", len(prepared_fields)),
        field_stats.get("ranked_field_count", len(prepared_fields)),
        len(prepared_fields),
        field_stats.get("selected_family_count", 0),
        field_stats.get("selected_unexplored_count", 0),
        field_stats.get("prefiltered_count", 0),
        field_stats.get("low_coverage_count", 0),
        field_stats.get("low_date_coverage_count", 0),
        field_stats.get("low_alpha_count", 0),
        field_stats.get("low_user_count", 0),
        field_stats.get("high_alpha_count", 0),
        field_stats.get("high_user_count", 0),
    )
    unknown_metadata_count = sum(
        field_stats.get(key, 0)
        for key in (
            "unknown_coverage_count",
            "unknown_date_coverage_count",
            "unknown_alpha_count",
            "unknown_user_count",
        )
    )
    if unknown_metadata_count:
        logger.info(
            "[dry-run] unknown_field_metadata=%d coverage=%d dateCoverage=%d "
            "alphaCount=%d userCount=%d",
            unknown_metadata_count,
            field_stats.get("unknown_coverage_count", 0),
            field_stats.get("unknown_date_coverage_count", 0),
            field_stats.get("unknown_alpha_count", 0),
            field_stats.get("unknown_user_count", 0),
        )

    execution_state = create_execution_state(
        historical_state=supporting_resources.historical_state,
    )
    print_dry_run_plan(
        options=template_options,
        fields=prepared_fields,
        filters=supporting_resources.filters,
        template_library=supporting_resources.template_library,
        historical_state=supporting_resources.historical_state,
        execution_state=execution_state,
        expression_policy=supporting_resources.expression_policy,
        full_run=args.planning.full_run,
        max_total_simulations=args.planning.max_total_simulations,
    )
    return True
