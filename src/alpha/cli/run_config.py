"""
运行配置快照构建模块。
"""

from __future__ import annotations

from typing import Any

from ..models.io_types import RunPaths
from ..models.runtime_options import RunConfigSnapshotOptions


def build_run_config_snapshot(
    options: RunConfigSnapshotOptions,
    run_paths: RunPaths,
) -> dict[str, Any]:
    """构建用于结果落盘的运行配置快照。"""
    return {
        "run": {
            "name": options.run_name,
        },
        "dataset": {
            "dataset_id": options.dataset_id,
            "region": options.region,
            "universe": options.universe,
            "instrument_type": options.instrument_type,
            "delay": options.delay,
        },
        "settings": {
            "decay": options.decay,
            "neutralization": options.neutralization,
            "truncation": options.truncation,
            "nan_handling": options.nan_handling,
            "max_trade": options.max_trade,
        },
        "limits": {
            "limit": options.limit,
            "offset": options.offset,
            "page_size": options.page_size,
            "sleep_between_fields": options.sleep_between_fields,
            "max_templates_per_field": options.max_templates_per_field,
            "max_templates_per_family": options.max_templates_per_family,
            "field_template_batch_size": options.field_template_batch_size,
            "legacy_similarity_penalty": options.legacy_similarity_penalty,
        },
        "concurrency": {
            "max_concurrent_simulations": options.max_concurrent_simulations,
            "max_concurrent_creates": options.max_concurrent_creates,
        },
        "retries": {
            "simulation_create_retries": options.simulation_create_retries,
            "simulation_poll_retries": options.simulation_poll_retries,
            "simulation_max_polls": options.simulation_max_polls,
            "simulation_max_wait_seconds": options.simulation_max_wait_seconds,
            "simulation_max_pending_cycles": options.simulation_max_pending_cycles,
            "simulation_max_queue_seconds": options.simulation_max_queue_seconds,
            "queue_busy_cooldown_seconds": options.queue_busy_cooldown_seconds,
            "field_queue_busy_skip_after": options.field_queue_busy_skip_after,
            "check_submit_retries": options.check_submit_retries,
            "rate_limit_max_retries": options.rate_limit_max_retries,
            "login_retries": options.login_retries,
            "min_request_interval": options.min_request_interval,
        },
        "filters": {
            "top_fields_by_feedback": options.top_fields_by_feedback,
            "stop_after_submittable": options.stop_after_submittable,
        },
        "paths": {
            "template_library_file": run_paths.template_library_file,
            "fields_cache_file": run_paths.fields_cache_file,
            "output": run_paths.output,
            "feedback_output": run_paths.feedback_output,
        },
        "runtime": {
            "auto_update_blacklist": options.auto_update_blacklist,
            "auto_update_blacklist_mode": options.auto_update_blacklist_mode,
            "smoke_test": options.smoke_test,
            "dry_run_plan": options.dry_run_plan,
            "full_run": options.full_run,
            "verbose": options.verbose,
            "quiet": options.quiet,
        },
    }
