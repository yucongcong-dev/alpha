"""Read-only, offline dry-run planning entrypoint."""

from __future__ import annotations

import logging

from ..analysis.feedback_history import build_historical_run_state
from ..cli.filters import load_run_filters_extended
from ..config.application import ApplicationConfig
from ..core.executor import print_dry_run_plan
from ..generators.fields import load_fields_cache
from ..generators.fingerprint import stable_fingerprint
from ..generators.payload import build_settings_fingerprint
from ..generators.templates.library_loader import load_template_library
from ..generators.templates.library_store import ensure_dataset_template_library
from ..models.io_types import RunPaths
from ..models.runtime_options import FieldFetchOptions, FieldSelectionOptions
from ..policy.blacklist_context import set_active_datasets_root
from ..policy.blacklist_store import (
    ensure_template_blacklist_file,
    read_blacklist_payload,
    summarize_blacklist_payload,
)
from ..policy.expression import get_dataset_expression_policy
from .bootstrap_field_selection import prepare_fields_for_execution
from .bootstrap_resource_loading import load_supporting_resources
from .bootstrap_state import create_execution_state
from .bootstrap_steps import build_effective_run_paths, resolve_bootstrap_paths
from .bootstrap_types import SupportingResourceServices

logger = logging.getLogger(__name__)


def build_planning_supporting_services() -> SupportingResourceServices:
    """Build local-resource dependencies so tests/runtime overrides stay effective."""
    return SupportingResourceServices(
        set_active_datasets_root=set_active_datasets_root,
        ensure_dataset_template_library=ensure_dataset_template_library,
        ensure_template_blacklist_file=ensure_template_blacklist_file,
        load_template_library=load_template_library,
        read_blacklist_payload=read_blacklist_payload,
        summarize_blacklist_payload=summarize_blacklist_payload,
        load_run_filters_extended=load_run_filters_extended,
        get_dataset_expression_policy=get_dataset_expression_policy,
        stable_fingerprint=stable_fingerprint,
        build_settings_fingerprint=build_settings_fingerprint,
        build_historical_run_state=build_historical_run_state,
    )


def run_dry_run_plan(args: ApplicationConfig, run_paths: RunPaths | None) -> bool:
    """Print a plan from local resources without authentication or filesystem writes."""
    paths = resolve_bootstrap_paths(args, run_paths)
    effective_run_paths = build_effective_run_paths(args, paths, run_paths)
    dataset_id = str(args.dataset_id)

    supporting_resources = load_supporting_resources(
        dataset_id=dataset_id,
        paths=paths,
        effective_run_paths=effective_run_paths,
        services=build_planning_supporting_services(),
        repair_corrupt_summary=False,
        log_blacklist=False,
    )

    field_options = FieldFetchOptions.from_args(args)
    fields = load_fields_cache(
        paths.fields_cache_file,
        dataset_id=dataset_id,
        region=field_options.region,
        universe=field_options.universe,
        instrument_type=field_options.instrument_type,
        delay=field_options.delay,
        cache_ttl_hours=0,
    )
    if not fields:
        logger.error(
            "[dry-run] no matching local field cache at %s; run a normal authenticated command "
            "once to populate it",
            paths.fields_cache_file,
        )
        return False

    prepared_fields, field_stats = prepare_fields_for_execution(
        list(fields),
        filters_dict=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        historical_state=supporting_resources.historical_state,
        selection_options=FieldSelectionOptions.from_args(args),
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
        dataset_id=dataset_id,
        historical_state=supporting_resources.historical_state,
        datasets_root=paths.datasets_root,
    )
    print_dry_run_plan(
        args=args,
        fields=prepared_fields,
        filters=supporting_resources.filters,
        template_library=supporting_resources.template_library,
        historical_state=supporting_resources.historical_state,
        execution_state=execution_state,
        use_dataset_heuristics=supporting_resources.expression_policy.use_curated_heuristics,
    )
    return True
