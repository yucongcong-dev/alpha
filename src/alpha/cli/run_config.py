"""
运行配置快照构建模块。
"""

from __future__ import annotations

from typing import Any

from ..models.io_types import RunPaths
from ..models.runtime import RunConfigArgs


def build_run_config_snapshot(args: RunConfigArgs, run_paths: RunPaths) -> dict[str, Any]:
    """构建用于结果落盘的运行配置快照。"""
    return {
        "dataset": {
            "dataset_id": args.dataset_id,
            "region": args.region,
            "universe": args.universe,
            "instrument_type": args.instrument_type,
            "delay": args.delay,
        },
        "settings": {
            "decay": args.decay,
            "neutralization": args.neutralization,
            "truncation": args.truncation,
            "nan_handling": args.nan_handling,
        },
        "limits": {
            "limit": args.limit,
            "offset": args.offset,
            "page_size": args.page_size,
            "sleep_between_fields": args.sleep_between_fields,
            "max_templates_per_field": args.max_templates_per_field,
            "max_templates_per_family": args.max_templates_per_family,
            "field_template_batch_size": args.field_template_batch_size,
            "legacy_similarity_penalty": args.legacy_similarity_penalty,
            "disable_legacy_after": args.disable_legacy_after,
        },
        "concurrency": {
            "max_concurrent_simulations": args.max_concurrent_simulations,
            "max_concurrent_creates": args.max_concurrent_creates,
        },
        "retries": {
            "simulation_create_retries": args.simulation_create_retries,
            "simulation_poll_retries": args.simulation_poll_retries,
            "simulation_max_polls": args.simulation_max_polls,
            "simulation_max_wait_seconds": args.simulation_max_wait_seconds,
            "simulation_max_pending_cycles": args.simulation_max_pending_cycles,
            "simulation_max_queue_seconds": args.simulation_max_queue_seconds,
            "queue_busy_cooldown_seconds": args.queue_busy_cooldown_seconds,
            "field_queue_busy_skip_after": args.field_queue_busy_skip_after,
            "check_submit_retries": args.check_submit_retries,
            "submit_retries": args.submit_retries,
            "rate_limit_max_retries": args.rate_limit_max_retries,
            "login_retries": args.login_retries,
            "min_request_interval": args.min_request_interval,
        },
        "filters": {
            "template_disable_after": args.template_disable_after,
            "top_fields_by_feedback": args.top_fields_by_feedback,
            "stop_after_submittable": args.stop_after_submittable,
        },
        "paths": {
            "template_library_file": run_paths.template_library_file,
            "fields_cache_file": run_paths.fields_cache_file,
            "output": run_paths.output,
            "feedback_output": run_paths.feedback_output,
        },
        "runtime": {
            "submit": args.submit,
            "auto_update_blacklist": args.auto_update_blacklist,
            "smoke_test": args.smoke_test,
            "dry_run_plan": args.dry_run_plan,
            "full_run": args.full_run,
            "verbose": args.verbose,
            "quiet": args.quiet,
        },
    }
