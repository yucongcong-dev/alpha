"""Compatibility getters backed by structured runtime configuration snapshots."""

from __future__ import annotations

from .runtime_values import (
    load_expression_runtime_config,
    load_feedback_runtime_config,
    load_http_runtime_config,
    load_precheck_quality_runtime_config,
    load_simulation_runtime_config,
    load_submit_quality_runtime_config,
)


def get_http_backend() -> str:
    return load_http_runtime_config().backend


def get_http_request_timeout() -> float:
    return load_http_runtime_config().request_timeout


def get_rate_limit_default_wait() -> float:
    return load_http_runtime_config().rate_limit_default_wait


def get_polling_default_wait() -> float:
    return load_http_runtime_config().polling_default_wait


def get_polling_no_retry_after_wait() -> float:
    return load_http_runtime_config().polling_no_retry_after_wait


def get_server_error_backoff_max() -> float:
    return load_http_runtime_config().server_error_backoff_max


def get_server_error_backoff_step() -> float:
    return load_http_runtime_config().server_error_backoff_step


def get_retry_operation_default_wait() -> float:
    return load_http_runtime_config().retry_operation_default_wait


def get_login_retry_wait() -> float:
    return load_http_runtime_config().login_retry_wait


def get_simulation_retry_wait() -> float:
    return load_http_runtime_config().simulation_retry_wait


def get_polling_retry_buffer() -> float:
    return load_http_runtime_config().polling_retry_buffer


def get_settings_variant_budget_high() -> float:
    return load_feedback_runtime_config().settings_variant_budget_high


def get_settings_variant_budget_mid() -> float:
    return load_feedback_runtime_config().settings_variant_budget_mid


def get_feedback_mutation_nearpass_threshold() -> float:
    return load_feedback_runtime_config().feedback_mutation_nearpass_threshold


def get_feedback_mutation_highscore_threshold() -> float:
    return load_feedback_runtime_config().feedback_mutation_highscore_threshold


def get_feedback_template_min_priority() -> int:
    return load_feedback_runtime_config().feedback_template_min_priority


def get_delta_std_priority_boost() -> int:
    return load_feedback_runtime_config().delta_std_priority_boost


def get_settings_nearpass_threshold() -> float:
    return load_feedback_runtime_config().settings_nearpass_threshold


def get_settings_close_threshold() -> float:
    return load_feedback_runtime_config().settings_close_threshold


def get_expr_nearpass_boost_threshold() -> float:
    return load_feedback_runtime_config().expr_nearpass_boost_threshold


def get_expr_iter_boost_threshold() -> float:
    return load_feedback_runtime_config().expr_iter_boost_threshold


def get_expr_ratio_penalty_threshold() -> float:
    return load_feedback_runtime_config().expr_ratio_penalty_threshold


def get_expr_mutation_extend_threshold() -> float:
    return load_feedback_runtime_config().expr_mutation_extend_threshold


def get_backfill_window() -> int:
    return load_expression_runtime_config().backfill_window


def get_simulation_default_start_date() -> str:
    return load_simulation_runtime_config().start_date


def get_simulation_default_end_date() -> str:
    return load_simulation_runtime_config().end_date


def get_precheck_fallback_min_sharpe() -> float:
    return load_precheck_quality_runtime_config().min_sharpe


def get_precheck_fallback_min_fitness() -> float:
    return load_precheck_quality_runtime_config().min_fitness


def get_precheck_fallback_min_turnover() -> float:
    return load_precheck_quality_runtime_config().min_turnover


def get_precheck_fallback_max_turnover() -> float:
    return load_precheck_quality_runtime_config().max_turnover


def get_precheck_fallback_max_weight() -> float:
    return load_precheck_quality_runtime_config().max_weight


def get_submit_min_sharpe() -> float:
    return load_submit_quality_runtime_config().min_sharpe


def get_submit_min_fitness() -> float:
    return load_submit_quality_runtime_config().min_fitness


def get_submit_min_turnover() -> float:
    return load_submit_quality_runtime_config().min_turnover


def get_submit_max_turnover() -> float:
    return load_submit_quality_runtime_config().max_turnover


def get_submit_max_weight() -> float:
    return load_submit_quality_runtime_config().max_weight
