"""
YAML 驱动的动态配置读取函数。
"""

from __future__ import annotations

from typing import Any

from .constants import (
    BACKFILL_WINDOW,
    DELTA_STD_PRIORITY_BOOST,
    EXPR_ITER_BOOST_THRESHOLD,
    EXPR_MUTATION_EXTEND_THRESHOLD,
    EXPR_NEARPASS_BOOST_THRESHOLD,
    EXPR_RATIO_PENALTY_THRESHOLD,
    FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
    FEEDBACK_MUTATION_NEARPASS_THRESHOLD,
    FEEDBACK_TEMPLATE_MIN_PRIORITY,
    HTTP_REQUEST_TIMEOUT,
    LOGIN_RETRY_WAIT,
    POLLING_DEFAULT_WAIT,
    POLLING_NO_RETRY_AFTER_WAIT,
    POLLING_RETRY_BUFFER,
    PRECHECK_FALLBACK_MAX_TURNOVER,
    PRECHECK_FALLBACK_MAX_WEIGHT,
    PRECHECK_FALLBACK_MIN_FITNESS,
    PRECHECK_FALLBACK_MIN_SHARPE,
    PRECHECK_FALLBACK_MIN_TURNOVER,
    RATE_LIMIT_DEFAULT_WAIT,
    RETRY_OPERATION_DEFAULT_WAIT,
    SERVER_ERROR_BACKOFF_MAX,
    SERVER_ERROR_BACKOFF_STEP,
    SETTINGS_CLOSE_THRESHOLD,
    SETTINGS_NEARPASS_THRESHOLD,
    SETTINGS_VARIANT_BUDGET_HIGH,
    SETTINGS_VARIANT_BUDGET_MID,
    SIMULATION_DEFAULT_END_DATE,
    SIMULATION_DEFAULT_START_DATE,
    SIMULATION_RETRY_WAIT,
    SUBMIT_MAX_TURNOVER,
    SUBMIT_MAX_WEIGHT,
    SUBMIT_MIN_FITNESS,
    SUBMIT_MIN_SHARPE,
    SUBMIT_MIN_TURNOVER,
)
def _yaml_global_section(section: str) -> dict[str, Any]:
    from . import get_yaml_config

    yaml_cfg = get_yaml_config()
    if not yaml_cfg:
        return {}
    global_cfg = yaml_cfg.get("global", {})
    if not isinstance(global_cfg, dict):
        return {}
    sect = global_cfg.get(section, {})
    return sect if isinstance(sect, dict) else {}


def _yaml_get(section: str, key: str, default: Any) -> Any:
    return _yaml_global_section(section).get(key, default)


def get_http_request_timeout() -> float:
    return float(_yaml_get("http", "request_timeout", HTTP_REQUEST_TIMEOUT))


def get_rate_limit_default_wait() -> float:
    return float(_yaml_get("http", "rate_limit_default_wait", RATE_LIMIT_DEFAULT_WAIT))


def get_polling_default_wait() -> float:
    return float(_yaml_get("http", "polling_default_wait", POLLING_DEFAULT_WAIT))


def get_polling_no_retry_after_wait() -> float:
    return float(_yaml_get("http", "polling_no_retry_after_wait", POLLING_NO_RETRY_AFTER_WAIT))


def get_server_error_backoff_max() -> float:
    return float(_yaml_get("http", "server_error_backoff_max", SERVER_ERROR_BACKOFF_MAX))


def get_server_error_backoff_step() -> float:
    return float(_yaml_get("http", "server_error_backoff_step", SERVER_ERROR_BACKOFF_STEP))


def get_retry_operation_default_wait() -> float:
    return float(_yaml_get("http", "retry_operation_default_wait", RETRY_OPERATION_DEFAULT_WAIT))


def get_login_retry_wait() -> float:
    return float(_yaml_get("http", "login_retry_wait", LOGIN_RETRY_WAIT))


def get_simulation_retry_wait() -> float:
    return float(_yaml_get("http", "simulation_retry_wait", SIMULATION_RETRY_WAIT))


def get_polling_retry_buffer() -> float:
    return float(_yaml_get("http", "polling_retry_buffer", POLLING_RETRY_BUFFER))


def get_settings_variant_budget_high() -> float:
    return float(_yaml_get("feedback", "settings_variant_budget_high", SETTINGS_VARIANT_BUDGET_HIGH))


def get_settings_variant_budget_mid() -> float:
    return float(_yaml_get("feedback", "settings_variant_budget_mid", SETTINGS_VARIANT_BUDGET_MID))


def get_feedback_mutation_nearpass_threshold() -> float:
    return float(
        _yaml_get(
            "feedback",
            "feedback_mutation_nearpass_threshold",
            FEEDBACK_MUTATION_NEARPASS_THRESHOLD,
        )
    )


def get_feedback_mutation_highscore_threshold() -> float:
    return float(
        _yaml_get(
            "feedback",
            "feedback_mutation_highscore_threshold",
            FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
        )
    )


def get_feedback_template_min_priority() -> int:
    return int(_yaml_get("feedback", "feedback_template_min_priority", FEEDBACK_TEMPLATE_MIN_PRIORITY))


def get_delta_std_priority_boost() -> int:
    return int(_yaml_get("feedback", "delta_std_priority_boost", DELTA_STD_PRIORITY_BOOST))


def get_settings_nearpass_threshold() -> float:
    return float(_yaml_get("feedback", "settings_nearpass_threshold", SETTINGS_NEARPASS_THRESHOLD))


def get_settings_close_threshold() -> float:
    return float(_yaml_get("feedback", "settings_close_threshold", SETTINGS_CLOSE_THRESHOLD))


def get_expr_nearpass_boost_threshold() -> float:
    return float(_yaml_get("feedback", "expr_nearpass_boost_threshold", EXPR_NEARPASS_BOOST_THRESHOLD))


def get_expr_iter_boost_threshold() -> float:
    return float(_yaml_get("feedback", "expr_iter_boost_threshold", EXPR_ITER_BOOST_THRESHOLD))


def get_expr_ratio_penalty_threshold() -> float:
    return float(_yaml_get("feedback", "expr_ratio_penalty_threshold", EXPR_RATIO_PENALTY_THRESHOLD))


def get_expr_mutation_extend_threshold() -> float:
    return float(_yaml_get("feedback", "expr_mutation_extend_threshold", EXPR_MUTATION_EXTEND_THRESHOLD))


def get_backfill_window() -> int:
    return int(_yaml_get("expression", "backfill_window", BACKFILL_WINDOW))


def get_simulation_default_start_date() -> str:
    return str(_yaml_get("simulation", "start_date", SIMULATION_DEFAULT_START_DATE))


def get_simulation_default_end_date() -> str:
    return str(_yaml_get("simulation", "end_date", SIMULATION_DEFAULT_END_DATE))


def get_precheck_fallback_min_sharpe() -> float:
    return float(_yaml_get("quality", "min_sharpe", PRECHECK_FALLBACK_MIN_SHARPE))


def get_precheck_fallback_min_fitness() -> float:
    return float(_yaml_get("quality", "min_fitness", PRECHECK_FALLBACK_MIN_FITNESS))


def get_precheck_fallback_min_turnover() -> float:
    return float(_yaml_get("quality", "min_turnover", PRECHECK_FALLBACK_MIN_TURNOVER))


def get_precheck_fallback_max_turnover() -> float:
    return float(_yaml_get("quality", "max_turnover", PRECHECK_FALLBACK_MAX_TURNOVER))


def get_precheck_fallback_max_weight() -> float:
    return float(_yaml_get("quality", "max_weight", PRECHECK_FALLBACK_MAX_WEIGHT))


def get_submit_min_sharpe() -> float:
    return float(_yaml_get("quality", "min_sharpe", SUBMIT_MIN_SHARPE))


def get_submit_min_fitness() -> float:
    return float(_yaml_get("quality", "min_fitness", SUBMIT_MIN_FITNESS))


def get_submit_min_turnover() -> float:
    return float(_yaml_get("quality", "min_turnover", SUBMIT_MIN_TURNOVER))


def get_submit_max_turnover() -> float:
    return float(_yaml_get("quality", "max_turnover", SUBMIT_MAX_TURNOVER))


def get_submit_max_weight() -> float:
    return float(_yaml_get("quality", "max_weight", SUBMIT_MAX_WEIGHT))
