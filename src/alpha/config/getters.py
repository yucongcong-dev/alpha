"""兼容性访问器 — 现已退化为单一 RuntimeConfig 复合对象的轻量委托。

所有 30 个 get_*() 函数共享同一个 `get_runtime_config()` 调用，
消除原来 30 次独立 YAML 查询的冗余。
"""

from __future__ import annotations

from .runtime_values import RuntimeConfig, get_runtime_config

__all__ = [
    "get_backfill_window",
    "get_delta_std_priority_boost",
    "get_expr_iter_boost_threshold",
    "get_expr_mutation_extend_threshold",
    "get_expr_nearpass_boost_threshold",
    "get_expr_ratio_penalty_threshold",
    "get_feedback_mutation_highscore_threshold",
    "get_feedback_mutation_nearpass_threshold",
    "get_feedback_template_min_priority",
    "get_http_backend",
    "get_http_request_timeout",
    "get_login_retry_wait",
    "get_polling_default_wait",
    "get_polling_no_retry_after_wait",
    "get_polling_retry_buffer",
    "get_precheck_fallback_max_turnover",
    "get_precheck_fallback_max_weight",
    "get_precheck_fallback_min_fitness",
    "get_precheck_fallback_min_sharpe",
    "get_precheck_fallback_min_turnover",
    "get_rate_limit_default_wait",
    "get_retry_operation_default_wait",
    "get_server_error_backoff_max",
    "get_server_error_backoff_step",
    "get_settings_close_threshold",
    "get_settings_nearpass_threshold",
    "get_settings_variant_budget_high",
    "get_settings_variant_budget_mid",
    "get_simulation_default_end_date",
    "get_simulation_default_start_date",
    "get_simulation_retry_wait",
    "get_submit_max_turnover",
    "get_submit_max_weight",
    "get_submit_min_fitness",
    "get_submit_min_sharpe",
    "get_submit_min_turnover",
]


def _rc() -> RuntimeConfig:
    return get_runtime_config()


# ---- HTTP ----

def get_http_backend() -> str:
    return _rc().http.backend


def get_http_request_timeout() -> float:
    return _rc().http.request_timeout


def get_rate_limit_default_wait() -> float:
    return _rc().http.rate_limit_default_wait


def get_polling_default_wait() -> float:
    return _rc().http.polling_default_wait


def get_polling_no_retry_after_wait() -> float:
    return _rc().http.polling_no_retry_after_wait


def get_server_error_backoff_max() -> float:
    return _rc().http.server_error_backoff_max


def get_server_error_backoff_step() -> float:
    return _rc().http.server_error_backoff_step


def get_retry_operation_default_wait() -> float:
    return _rc().http.retry_operation_default_wait


def get_login_retry_wait() -> float:
    return _rc().http.login_retry_wait


def get_simulation_retry_wait() -> float:
    return _rc().http.simulation_retry_wait


def get_polling_retry_buffer() -> float:
    return _rc().http.polling_retry_buffer


# ---- Feedback ----

def get_settings_variant_budget_high() -> float:
    return _rc().feedback.settings_variant_budget_high


def get_settings_variant_budget_mid() -> float:
    return _rc().feedback.settings_variant_budget_mid


def get_feedback_mutation_nearpass_threshold() -> float:
    return _rc().feedback.feedback_mutation_nearpass_threshold


def get_feedback_mutation_highscore_threshold() -> float:
    return _rc().feedback.feedback_mutation_highscore_threshold


def get_feedback_template_min_priority() -> int:
    return _rc().feedback.feedback_template_min_priority


def get_delta_std_priority_boost() -> int:
    return _rc().feedback.delta_std_priority_boost


def get_settings_nearpass_threshold() -> float:
    return _rc().feedback.settings_nearpass_threshold


def get_settings_close_threshold() -> float:
    return _rc().feedback.settings_close_threshold


def get_expr_nearpass_boost_threshold() -> float:
    return _rc().feedback.expr_nearpass_boost_threshold


def get_expr_iter_boost_threshold() -> float:
    return _rc().feedback.expr_iter_boost_threshold


def get_expr_ratio_penalty_threshold() -> float:
    return _rc().feedback.expr_ratio_penalty_threshold


def get_expr_mutation_extend_threshold() -> float:
    return _rc().feedback.expr_mutation_extend_threshold


# ---- Expression ----

def get_backfill_window() -> int:
    return _rc().expression.backfill_window


# ---- Simulation ----

def get_simulation_default_start_date() -> str:
    return _rc().simulation.start_date


def get_simulation_default_end_date() -> str:
    return _rc().simulation.end_date


# ---- Precheck Quality ----

def get_precheck_fallback_min_sharpe() -> float:
    return _rc().precheck_quality.min_sharpe


def get_precheck_fallback_min_fitness() -> float:
    return _rc().precheck_quality.min_fitness


def get_precheck_fallback_min_turnover() -> float:
    return _rc().precheck_quality.min_turnover


def get_precheck_fallback_max_turnover() -> float:
    return _rc().precheck_quality.max_turnover


def get_precheck_fallback_max_weight() -> float:
    return _rc().precheck_quality.max_weight


# ---- Submit Quality ----

def get_submit_min_sharpe() -> float:
    return _rc().submit_quality.min_sharpe


def get_submit_min_fitness() -> float:
    return _rc().submit_quality.min_fitness


def get_submit_min_turnover() -> float:
    return _rc().submit_quality.min_turnover


def get_submit_max_turnover() -> float:
    return _rc().submit_quality.max_turnover


def get_submit_max_weight() -> float:
    return _rc().submit_quality.max_weight
