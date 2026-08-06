"""
运行配置快照构建模块。
"""

from __future__ import annotations

from typing import Any

from ..config.application import ApplicationConfig
from ..config.strategy_profiles import normalize_strategy_profile
from ..models.io_types import RunPaths


def build_run_config_snapshot(
    config: ApplicationConfig,
    run_paths: RunPaths,
) -> dict[str, Any]:
    """构建用于结果落盘的运行配置快照。"""
    dataset = config.dataset
    simulation = config.simulation
    planning = config.planning
    execution = config.execution
    flags = config.runtime_flags
    return {
        "run": {
            "name": config.run_name,
        },
        "dataset": {
            "dataset_id": dataset.dataset_id,
            "region": dataset.region,
            "universe": dataset.universe,
            "instrument_type": dataset.instrument_type,
            "delay": dataset.delay,
        },
        "settings": {
            "decay": simulation.decay,
            "neutralization": simulation.neutralization,
            "truncation": simulation.truncation,
            "nan_handling": simulation.nan_handling,
            "max_trade": simulation.max_trade,
        },
        "limits": {
            "limit": planning.limit,
            "offset": planning.offset,
            "page_size": planning.page_size,
            "sleep_between_fields": planning.sleep_between_fields,
            "max_templates_per_field": planning.max_templates_per_field,
            "max_templates_per_family": planning.max_templates_per_family,
            "max_total_simulations": planning.max_total_simulations,
            "field_template_batch_size": max(1, planning.field_template_batch_size),
            "legacy_similarity_penalty": planning.legacy_similarity_penalty,
        },
        "concurrency": {
            "max_concurrent_simulations": execution.max_concurrent_simulations,
            "max_concurrent_creates": execution.max_concurrent_creates,
        },
        "retries": {
            "simulation_create_retries": execution.simulation_create_retries,
            "simulation_poll_retries": execution.simulation_poll_retries,
            "simulation_max_polls": execution.simulation_max_polls,
            "simulation_max_wait_seconds": execution.simulation_max_wait_seconds,
            "simulation_max_pending_cycles": execution.simulation_max_pending_cycles,
            "simulation_max_queue_seconds": execution.simulation_max_queue_seconds,
            "queue_busy_cooldown_seconds": execution.queue_busy_cooldown_seconds,
            "queue_busy_retry_limit": execution.queue_busy_retry_limit,
            "check_submission_retries": execution.check_submission_retries,
            "rate_limit_max_retries": execution.rate_limit_max_retries,
            "login_retries": execution.login_retries,
            "min_request_interval": execution.min_request_interval,
        },
        "filters": {
            "top_fields_by_feedback": planning.top_fields_by_feedback,
        },
        "paths": {
            "template_library_file": run_paths.template_library_file,
            "fields_cache_file": run_paths.fields_cache_file,
            "output": run_paths.output,
            "feedback_output": run_paths.feedback_output,
        },
        "runtime": {
            "strategy_profile": normalize_strategy_profile(flags.strategy_profile),
            "smoke_test": planning.smoke_test,
            "dry_run_plan": planning.dry_run_plan,
            "full_run": planning.full_run,
            "verbose": flags.verbose,
            "quiet": flags.quiet,
        },
    }
