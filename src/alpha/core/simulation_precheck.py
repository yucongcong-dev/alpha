"""Local simulation metric diagnostic helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..api.api_types import CheckResultDict, SimulationPayload
from ..config.static_config import get_static_config

_RESULT_FAIL: str = "FAIL"
_KEY_CONCENTRATED_WEIGHT: str = "concentratedWeight"
_KEY_FITNESS: str = "fitness"
_KEY_IS: str = "is"
_KEY_LIMIT: str = "limit"
_KEY_MAX_WEIGHT: str = "maxWeight"
_KEY_MAX_WEIGHT_ALT: str = "max_weight"
_KEY_NAME: str = "name"
_KEY_RESULT: str = "result"
_KEY_SHARPE: str = "sharpe"
_KEY_TURNOVER: str = "turnover"
_KEY_VALUE: str = "value"


@dataclass
class PrecheckConfig:
    min_sharpe: float = field(default_factory=lambda: get_static_config().submit_min_sharpe)
    min_fitness: float = field(default_factory=lambda: get_static_config().submit_min_fitness)
    min_turnover: float = field(default_factory=lambda: get_static_config().submit_min_turnover)
    max_turnover: float = field(default_factory=lambda: get_static_config().submit_max_turnover)
    max_weight: float = field(default_factory=lambda: get_static_config().submit_max_weight)


def _resolve_precheck_config(
    *,
    min_sharpe: float | None,
    min_fitness: float | None,
    min_turnover: float | None,
    max_turnover: float | None,
    max_weight: float | None,
) -> PrecheckConfig:
    if all(
        value is not None
        for value in (min_sharpe, min_fitness, min_turnover, max_turnover, max_weight)
    ):
        assert min_sharpe is not None
        assert min_fitness is not None
        assert min_turnover is not None
        assert max_turnover is not None
        assert max_weight is not None
        return PrecheckConfig(
            min_sharpe=min_sharpe,
            min_fitness=min_fitness,
            min_turnover=min_turnover,
            max_turnover=max_turnover,
            max_weight=max_weight,
        )
    defaults = PrecheckConfig()
    return PrecheckConfig(
        min_sharpe=defaults.min_sharpe if min_sharpe is None else min_sharpe,
        min_fitness=defaults.min_fitness if min_fitness is None else min_fitness,
        min_turnover=defaults.min_turnover if min_turnover is None else min_turnover,
        max_turnover=defaults.max_turnover if max_turnover is None else max_turnover,
        max_weight=defaults.max_weight if max_weight is None else max_weight,
    )


def _metric_failures(
    is_section: dict[str, object],
    config: PrecheckConfig,
) -> list[CheckResultDict]:
    failures: list[CheckResultDict] = []

    def add_failure(check_name: str, value: int | float, limit: float) -> None:
        failures.append(
            {
                "name": check_name,
                "result": _RESULT_FAIL,
                "value": float(value),
                "limit": limit,
            }
        )

    sharpe = is_section.get(_KEY_SHARPE)
    fitness = is_section.get(_KEY_FITNESS)
    turnover = is_section.get(_KEY_TURNOVER)
    max_stock_weight = (
        is_section.get(_KEY_MAX_WEIGHT)
        or is_section.get(_KEY_MAX_WEIGHT_ALT)
        or is_section.get(_KEY_CONCENTRATED_WEIGHT)
    )
    if isinstance(sharpe, (int, float)) and sharpe < config.min_sharpe:
        add_failure(get_static_config().check_low_sharpe, sharpe, config.min_sharpe)
    if isinstance(fitness, (int, float)) and fitness < config.min_fitness:
        add_failure(get_static_config().check_low_fitness, fitness, config.min_fitness)
    if isinstance(turnover, (int, float)):
        if turnover < config.min_turnover:
            add_failure(get_static_config().check_low_turnover, turnover, config.min_turnover)
        elif turnover > config.max_turnover:
            add_failure(get_static_config().check_high_turnover, turnover, config.max_turnover)
    if isinstance(max_stock_weight, (int, float)) and max_stock_weight > config.max_weight:
        add_failure(
            get_static_config().check_concentrated_weight, max_stock_weight, config.max_weight
        )
    return failures


def _format_failure_reason(failures: list[CheckResultDict]) -> str:
    reason_parts = []
    for failure in failures:
        value = failure.get("value")
        formatted_value = f"{value:.4f}" if isinstance(value, (int, float)) else "unknown"
        reason_parts.append(
            f"{failure['name'].lower()}: {formatted_value} vs limit {failure.get('limit')}"
        )
    return "; ".join(reason_parts)


def precheck_simulation_metrics(
    simulation_result: SimulationPayload,
    *,
    min_sharpe: float | None = None,
    min_fitness: float | None = None,
    min_turnover: float | None = None,
    max_turnover: float | None = None,
    max_weight: float | None = None,
) -> tuple[bool, str, list[CheckResultDict]]:
    """Evaluate local thresholds for diagnostics before Check Submission."""
    is_section = simulation_result.get(_KEY_IS)
    if not isinstance(is_section, dict):
        return True, "", []
    config = _resolve_precheck_config(
        min_sharpe=min_sharpe,
        min_fitness=min_fitness,
        min_turnover=min_turnover,
        max_turnover=max_turnover,
        max_weight=max_weight,
    )
    failures = _metric_failures(is_section, config)
    if not failures:
        return True, "", []
    return False, _format_failure_reason(failures), failures
