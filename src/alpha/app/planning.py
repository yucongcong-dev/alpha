"""Read-only, offline dry-run planning entrypoint."""

from __future__ import annotations

import logging

from ..analysis.feedback_history import build_historical_run_state
from ..cli.filters import load_run_filters_extended
from ..config.application import ApplicationConfig
from ..core.executor import print_dry_run_plan
from ..generators.fields import load_fields_cache
from ..generators.templates.library_loader import load_template_library
from ..generators.templates.library_store import ensure_dataset_template_library
from ..models.io_types import RunPaths
from ..models.runtime_options import FieldFetchOptions
from ..policy.blacklist_context import set_active_datasets_root
from ..policy.expression import get_dataset_expression_policy
from .bootstrap_fields import prepare_fields_for_execution
from .bootstrap_state import create_execution_state
from .bootstrap_steps import build_effective_run_paths, resolve_bootstrap_paths

logger = logging.getLogger(__name__)


def run_dry_run_plan(args: ApplicationConfig, run_paths: RunPaths | None) -> bool:
    """Print a plan from local resources without authentication or filesystem writes."""
    paths = resolve_bootstrap_paths(args, run_paths)
    effective_run_paths = build_effective_run_paths(args, paths, run_paths)
    dataset_id = str(args.dataset_id)

    set_active_datasets_root(paths.datasets_root)
    template_library_file = ensure_dataset_template_library(paths.template_library_file, dataset_id)
    template_library = load_template_library(template_library_file)
    filters = load_run_filters_extended(effective_run_paths)
    expression_policy = get_dataset_expression_policy(dataset_id)
    historical_state = build_historical_run_state(
        paths.output_file,
        paths.feedback_output,
        repair_corrupt_summary=False,
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
        filters_dict=filters,
        expression_policy=expression_policy,
        historical_state=historical_state,
        args=args,
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

    execution_state = create_execution_state(
        dataset_id=dataset_id,
        historical_state=historical_state,
        datasets_root=paths.datasets_root,
    )
    print_dry_run_plan(
        args=args,
        fields=prepared_fields,
        filters=filters,
        template_library=template_library,
        historical_state=historical_state,
        execution_state=execution_state,
        use_dataset_heuristics=expression_policy.use_curated_heuristics,
    )
    return True
