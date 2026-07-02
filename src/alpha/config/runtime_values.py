"""Structured runtime configuration snapshots loaded from YAML globals."""

from __future__ import annotations

from dataclasses import dataclass
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
from .types import ConfigSection


def yaml_global_section(section: str) -> ConfigSection:
    """Load a normalized `global.<section>` dictionary from the active YAML config."""
    from . import get_yaml_config

    yaml_cfg = get_yaml_config()
    if not yaml_cfg:
        return {}
    global_cfg = yaml_cfg.get("global", {})
    if not isinstance(global_cfg, dict):
        return {}
    sect = global_cfg.get(section, {})
    return sect if isinstance(sect, dict) else {}


def yaml_global_value(section: str, key: str, default: Any) -> Any:
    """Read a single scalar from the active YAML globals."""
    return yaml_global_section(section).get(key, default)


@dataclass(frozen=True)
class HttpRuntimeConfig:
    request_timeout: float
    rate_limit_default_wait: float
    polling_default_wait: float
    polling_no_retry_after_wait: float
    server_error_backoff_max: float
    server_error_backoff_step: float
    retry_operation_default_wait: float
    login_retry_wait: float
    simulation_retry_wait: float
    polling_retry_buffer: float
    backend: str = "urllib"


@dataclass(frozen=True)
class FeedbackRuntimeConfig:
    settings_variant_budget_high: float
    settings_variant_budget_mid: float
    feedback_mutation_nearpass_threshold: float
    feedback_mutation_highscore_threshold: float
    feedback_template_min_priority: int
    delta_std_priority_boost: int
    settings_nearpass_threshold: float
    settings_close_threshold: float
    expr_nearpass_boost_threshold: float
    expr_iter_boost_threshold: float
    expr_ratio_penalty_threshold: float
    expr_mutation_extend_threshold: float


@dataclass(frozen=True)
class ExpressionRuntimeConfig:
    backfill_window: int


@dataclass(frozen=True)
class SimulationRuntimeConfig:
    start_date: str
    end_date: str


@dataclass(frozen=True)
class QualityRuntimeConfig:
    min_sharpe: float
    min_fitness: float
    min_turnover: float
    max_turnover: float
    max_weight: float


def load_http_runtime_config() -> HttpRuntimeConfig:
    """Build the current HTTP/runtime wait configuration snapshot."""
    return HttpRuntimeConfig(
        request_timeout=float(yaml_global_value("http", "request_timeout", HTTP_REQUEST_TIMEOUT)),
        rate_limit_default_wait=float(
            yaml_global_value("http", "rate_limit_default_wait", RATE_LIMIT_DEFAULT_WAIT)
        ),
        polling_default_wait=float(
            yaml_global_value("http", "polling_default_wait", POLLING_DEFAULT_WAIT)
        ),
        polling_no_retry_after_wait=float(
            yaml_global_value(
                "http",
                "polling_no_retry_after_wait",
                POLLING_NO_RETRY_AFTER_WAIT,
            )
        ),
        server_error_backoff_max=float(
            yaml_global_value("http", "server_error_backoff_max", SERVER_ERROR_BACKOFF_MAX)
        ),
        server_error_backoff_step=float(
            yaml_global_value("http", "server_error_backoff_step", SERVER_ERROR_BACKOFF_STEP)
        ),
        retry_operation_default_wait=float(
            yaml_global_value(
                "http",
                "retry_operation_default_wait",
                RETRY_OPERATION_DEFAULT_WAIT,
            )
        ),
        login_retry_wait=float(yaml_global_value("http", "login_retry_wait", LOGIN_RETRY_WAIT)),
        simulation_retry_wait=float(
            yaml_global_value("http", "simulation_retry_wait", SIMULATION_RETRY_WAIT)
        ),
        polling_retry_buffer=float(
            yaml_global_value("http", "polling_retry_buffer", POLLING_RETRY_BUFFER)
        ),
        backend=str(yaml_global_value("http", "backend", "")),
    )


def load_feedback_runtime_config() -> FeedbackRuntimeConfig:
    """Build the current feedback threshold configuration snapshot."""
    return FeedbackRuntimeConfig(
        settings_variant_budget_high=float(
            yaml_global_value(
                "feedback",
                "settings_variant_budget_high",
                SETTINGS_VARIANT_BUDGET_HIGH,
            )
        ),
        settings_variant_budget_mid=float(
            yaml_global_value(
                "feedback",
                "settings_variant_budget_mid",
                SETTINGS_VARIANT_BUDGET_MID,
            )
        ),
        feedback_mutation_nearpass_threshold=float(
            yaml_global_value(
                "feedback",
                "feedback_mutation_nearpass_threshold",
                FEEDBACK_MUTATION_NEARPASS_THRESHOLD,
            )
        ),
        feedback_mutation_highscore_threshold=float(
            yaml_global_value(
                "feedback",
                "feedback_mutation_highscore_threshold",
                FEEDBACK_MUTATION_HIGHSCORE_THRESHOLD,
            )
        ),
        feedback_template_min_priority=int(
            yaml_global_value(
                "feedback",
                "feedback_template_min_priority",
                FEEDBACK_TEMPLATE_MIN_PRIORITY,
            )
        ),
        delta_std_priority_boost=int(
            yaml_global_value("feedback", "delta_std_priority_boost", DELTA_STD_PRIORITY_BOOST)
        ),
        settings_nearpass_threshold=float(
            yaml_global_value("feedback", "settings_nearpass_threshold", SETTINGS_NEARPASS_THRESHOLD)
        ),
        settings_close_threshold=float(
            yaml_global_value("feedback", "settings_close_threshold", SETTINGS_CLOSE_THRESHOLD)
        ),
        expr_nearpass_boost_threshold=float(
            yaml_global_value(
                "feedback",
                "expr_nearpass_boost_threshold",
                EXPR_NEARPASS_BOOST_THRESHOLD,
            )
        ),
        expr_iter_boost_threshold=float(
            yaml_global_value("feedback", "expr_iter_boost_threshold", EXPR_ITER_BOOST_THRESHOLD)
        ),
        expr_ratio_penalty_threshold=float(
            yaml_global_value(
                "feedback",
                "expr_ratio_penalty_threshold",
                EXPR_RATIO_PENALTY_THRESHOLD,
            )
        ),
        expr_mutation_extend_threshold=float(
            yaml_global_value(
                "feedback",
                "expr_mutation_extend_threshold",
                EXPR_MUTATION_EXTEND_THRESHOLD,
            )
        ),
    )


def load_expression_runtime_config() -> ExpressionRuntimeConfig:
    """Build the current expression-generation configuration snapshot."""
    return ExpressionRuntimeConfig(
        backfill_window=int(yaml_global_value("expression", "backfill_window", BACKFILL_WINDOW))
    )


def load_simulation_runtime_config() -> SimulationRuntimeConfig:
    """Build the current simulation-date configuration snapshot."""
    return SimulationRuntimeConfig(
        start_date=str(
            yaml_global_value("simulation", "start_date", SIMULATION_DEFAULT_START_DATE)
        ),
        end_date=str(yaml_global_value("simulation", "end_date", SIMULATION_DEFAULT_END_DATE)),
    )


def load_precheck_quality_runtime_config() -> QualityRuntimeConfig:
    """Build the current quality thresholds used by local precheck fallbacks."""
    return QualityRuntimeConfig(
        min_sharpe=float(yaml_global_value("quality", "min_sharpe", PRECHECK_FALLBACK_MIN_SHARPE)),
        min_fitness=float(
            yaml_global_value("quality", "min_fitness", PRECHECK_FALLBACK_MIN_FITNESS)
        ),
        min_turnover=float(
            yaml_global_value("quality", "min_turnover", PRECHECK_FALLBACK_MIN_TURNOVER)
        ),
        max_turnover=float(
            yaml_global_value("quality", "max_turnover", PRECHECK_FALLBACK_MAX_TURNOVER)
        ),
        max_weight=float(yaml_global_value("quality", "max_weight", PRECHECK_FALLBACK_MAX_WEIGHT)),
    )


def load_submit_quality_runtime_config() -> QualityRuntimeConfig:
    """Build the current quality thresholds used for submit-grade checks."""
    return QualityRuntimeConfig(
        min_sharpe=float(yaml_global_value("quality", "min_sharpe", SUBMIT_MIN_SHARPE)),
        min_fitness=float(yaml_global_value("quality", "min_fitness", SUBMIT_MIN_FITNESS)),
        min_turnover=float(yaml_global_value("quality", "min_turnover", SUBMIT_MIN_TURNOVER)),
        max_turnover=float(yaml_global_value("quality", "max_turnover", SUBMIT_MAX_TURNOVER)),
        max_weight=float(yaml_global_value("quality", "max_weight", SUBMIT_MAX_WEIGHT)),
    )

