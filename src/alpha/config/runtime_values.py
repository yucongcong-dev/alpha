"""Structured runtime configuration snapshots loaded from YAML globals.

性能优化：每个 load_*_runtime_config() 只调用一次 get_yaml_config()，
提取所需 section 后本地读取所有值，避免 11+ 次重复 YAML 字典遍历。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .yaml import get_yaml_config, get_yaml_config_version

_HTTP_DEFAULTS = {
    "request_timeout": 90.0,
    "rate_limit_default_wait": 10.0,
    "polling_default_wait": 5.0,
    "polling_no_retry_after_wait": 1.5,
    "server_error_backoff_max": 30.0,
    "server_error_backoff_step": 3.0,
    "retry_operation_default_wait": 2.0,
    "login_retry_wait": 3.0,
    "simulation_retry_wait": 3.0,
    "polling_retry_buffer": 0.5,
    "backend": "urllib",
}
_FEEDBACK_DEFAULTS = {
    "feedback_mutation_highscore_threshold": 0.25,
    "feedback_template_min_priority": 105,
    "delta_std_priority_boost": 15,
    "expr_nearpass_boost_threshold": 0.50,
    "expr_iter_boost_threshold": 0.20,
    "expr_ratio_penalty_threshold": 0.30,
    "expr_mutation_extend_threshold": 0.15,
}
_QUALITY_DEFAULTS = {
    "min_sharpe": 1.25,
    "min_fitness": 1.0,
    "min_turnover": 0.01,
    "max_turnover": 0.70,
    "max_weight": 0.10,
}

_SUPPORTED_HTTP_BACKENDS = {"urllib", "httpx"}


def _validate_non_negative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"{name} must be >= 0; got {value!r}")


def _validate_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be > 0; got {value!r}")


def _get_yaml_global() -> dict[str, Any]:
    """获取整个 global 段（一次查询，避免重复遍历）。"""
    yaml_cfg = get_yaml_config()
    if not yaml_cfg:
        return {}
    global_cfg = yaml_cfg.get("global", {})
    return global_cfg if isinstance(global_cfg, dict) else {}


def yaml_global_section(section: str) -> dict[str, Any]:
    """Load a normalized `global.<section>` dictionary from the active YAML config."""
    global_cfg = _get_yaml_global()
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

    def __post_init__(self) -> None:
        backend = self.backend.strip().lower()
        if backend not in _SUPPORTED_HTTP_BACKENDS:
            supported = ", ".join(sorted(_SUPPORTED_HTTP_BACKENDS))
            raise ValueError(f"http.backend must be one of: {supported}; got {self.backend!r}")
        object.__setattr__(self, "backend", backend)
        _validate_positive("http.request_timeout", self.request_timeout)
        _validate_non_negative("http.rate_limit_default_wait", self.rate_limit_default_wait)
        _validate_non_negative("http.polling_default_wait", self.polling_default_wait)
        _validate_non_negative("http.polling_no_retry_after_wait", self.polling_no_retry_after_wait)
        _validate_non_negative("http.server_error_backoff_max", self.server_error_backoff_max)
        _validate_non_negative("http.server_error_backoff_step", self.server_error_backoff_step)
        if self.server_error_backoff_max < self.server_error_backoff_step:
            raise ValueError(
                "http.server_error_backoff_max must be >= "
                f"http.server_error_backoff_step; got {self.server_error_backoff_max!r} < "
                f"{self.server_error_backoff_step!r}"
            )
        _validate_non_negative(
            "http.retry_operation_default_wait", self.retry_operation_default_wait
        )
        _validate_non_negative("http.login_retry_wait", self.login_retry_wait)
        _validate_non_negative("http.simulation_retry_wait", self.simulation_retry_wait)
        _validate_non_negative("http.polling_retry_buffer", self.polling_retry_buffer)


@dataclass(frozen=True)
class FeedbackRuntimeConfig:
    feedback_mutation_highscore_threshold: float
    feedback_template_min_priority: int
    delta_std_priority_boost: int
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

    def __post_init__(self) -> None:
        _validate_non_negative("quality.min_sharpe", self.min_sharpe)
        _validate_non_negative("quality.min_fitness", self.min_fitness)
        _validate_non_negative("quality.min_turnover", self.min_turnover)
        _validate_positive("quality.max_turnover", self.max_turnover)
        if self.min_turnover > self.max_turnover:
            raise ValueError(
                "quality.min_turnover must be <= quality.max_turnover; "
                f"got {self.min_turnover!r} > {self.max_turnover!r}"
            )
        if not 0 < self.max_weight <= 1:
            raise ValueError(f"quality.max_weight must be > 0 and <= 1; got {self.max_weight!r}")


def load_http_runtime_config() -> HttpRuntimeConfig:
    """Build the current HTTP/runtime wait configuration snapshot.

    单次 YAML 查询，从 local http section 读取全部 11 个字段。
    """
    section = yaml_global_section("http")
    return HttpRuntimeConfig(
        request_timeout=float(section.get("request_timeout", _HTTP_DEFAULTS["request_timeout"])),
        rate_limit_default_wait=float(
            section.get("rate_limit_default_wait", _HTTP_DEFAULTS["rate_limit_default_wait"])
        ),
        polling_default_wait=float(
            section.get("polling_default_wait", _HTTP_DEFAULTS["polling_default_wait"])
        ),
        polling_no_retry_after_wait=float(
            section.get(
                "polling_no_retry_after_wait", _HTTP_DEFAULTS["polling_no_retry_after_wait"]
            )
        ),
        server_error_backoff_max=float(
            section.get("server_error_backoff_max", _HTTP_DEFAULTS["server_error_backoff_max"])
        ),
        server_error_backoff_step=float(
            section.get("server_error_backoff_step", _HTTP_DEFAULTS["server_error_backoff_step"])
        ),
        retry_operation_default_wait=float(
            section.get(
                "retry_operation_default_wait", _HTTP_DEFAULTS["retry_operation_default_wait"]
            )
        ),
        login_retry_wait=float(section.get("login_retry_wait", _HTTP_DEFAULTS["login_retry_wait"])),
        simulation_retry_wait=float(
            section.get("simulation_retry_wait", _HTTP_DEFAULTS["simulation_retry_wait"])
        ),
        polling_retry_buffer=float(
            section.get("polling_retry_buffer", _HTTP_DEFAULTS["polling_retry_buffer"])
        ),
        backend=str(section.get("backend", _HTTP_DEFAULTS["backend"])),
    )


def load_feedback_runtime_config() -> FeedbackRuntimeConfig:
    """Build the current feedback threshold configuration snapshot.

    单次 YAML 查询，从 local feedback section 读取有效阈值。
    """
    section = yaml_global_section("feedback")
    return FeedbackRuntimeConfig(
        feedback_mutation_highscore_threshold=float(
            section.get(
                "feedback_mutation_highscore_threshold",
                _FEEDBACK_DEFAULTS["feedback_mutation_highscore_threshold"],
            )
        ),
        feedback_template_min_priority=int(
            section.get(
                "feedback_template_min_priority",
                _FEEDBACK_DEFAULTS["feedback_template_min_priority"],
            )
        ),
        delta_std_priority_boost=int(
            section.get("delta_std_priority_boost", _FEEDBACK_DEFAULTS["delta_std_priority_boost"])
        ),
        expr_nearpass_boost_threshold=float(
            section.get(
                "expr_nearpass_boost_threshold",
                _FEEDBACK_DEFAULTS["expr_nearpass_boost_threshold"],
            )
        ),
        expr_iter_boost_threshold=float(
            section.get(
                "expr_iter_boost_threshold", _FEEDBACK_DEFAULTS["expr_iter_boost_threshold"]
            )
        ),
        expr_ratio_penalty_threshold=float(
            section.get(
                "expr_ratio_penalty_threshold", _FEEDBACK_DEFAULTS["expr_ratio_penalty_threshold"]
            )
        ),
        expr_mutation_extend_threshold=float(
            section.get(
                "expr_mutation_extend_threshold",
                _FEEDBACK_DEFAULTS["expr_mutation_extend_threshold"],
            )
        ),
    )


def load_expression_runtime_config() -> ExpressionRuntimeConfig:
    """Build the current expression-generation configuration snapshot."""
    section = yaml_global_section("expression")
    return ExpressionRuntimeConfig(backfill_window=int(section.get("backfill_window", 504)))


def load_simulation_runtime_config() -> SimulationRuntimeConfig:
    """Build the current simulation-date configuration snapshot."""
    section = yaml_global_section("simulation")
    return SimulationRuntimeConfig(
        start_date=str(section.get("start_date", "2020-01-01")),
        end_date=str(section.get("end_date", "2025-12-31")),
    )


def load_quality_runtime_config() -> QualityRuntimeConfig:
    """Build the single local quality gate used before platform checks."""
    section = yaml_global_section("quality")
    return QualityRuntimeConfig(
        min_sharpe=float(section.get("min_sharpe", _QUALITY_DEFAULTS["min_sharpe"])),
        min_fitness=float(section.get("min_fitness", _QUALITY_DEFAULTS["min_fitness"])),
        min_turnover=float(section.get("min_turnover", _QUALITY_DEFAULTS["min_turnover"])),
        max_turnover=float(section.get("max_turnover", _QUALITY_DEFAULTS["max_turnover"])),
        max_weight=float(section.get("max_weight", _QUALITY_DEFAULTS["max_weight"])),
    )


# ---------------------------------------------------------------------------
# 统一运行时配置复合对象 — 消除 30 个 getter 包装函数的冗余 YAML 查询
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeConfig:
    """运行时配置的单一聚合快照。调用方直接通过属性访问，无需包装函数。"""

    http: HttpRuntimeConfig
    feedback: FeedbackRuntimeConfig
    expression: ExpressionRuntimeConfig
    simulation: SimulationRuntimeConfig
    quality: QualityRuntimeConfig


_runtime_config_cache: RuntimeConfig | None = None
_runtime_config_source: object | None = None


def _build_runtime_config() -> RuntimeConfig:
    """构建完整的运行时配置。所有 7 个 section 一次加载。"""
    return RuntimeConfig(
        http=load_http_runtime_config(),
        feedback=load_feedback_runtime_config(),
        expression=load_expression_runtime_config(),
        simulation=load_simulation_runtime_config(),
        quality=load_quality_runtime_config(),
    )


def get_runtime_config() -> RuntimeConfig:
    """获取完整运行时配置（惰性构建 + 缓存）。

    取代原来 30 个独立的 get_*() 函数，消除 30→1 次 YAML 遍历的冗余。
    """
    global _runtime_config_cache, _runtime_config_source
    active_source = get_yaml_config_version()
    if _runtime_config_cache is None or _runtime_config_source != active_source:
        _runtime_config_cache = _build_runtime_config()
        _runtime_config_source = active_source
    return _runtime_config_cache


def clear_runtime_config_cache() -> None:
    """清除运行时配置缓存，强制下次访问重新加载。"""
    global _runtime_config_cache, _runtime_config_source
    _runtime_config_cache = None
    _runtime_config_source = None
