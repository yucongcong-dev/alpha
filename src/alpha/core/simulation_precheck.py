"""Local simulation metric precheck helpers."""

from __future__ import annotations

from dataclasses import dataclass

from ..api.api_types import CheckResultDict, SimulationPayload
from ..config.constants import (
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_TURNOVER,
    PRECHECK_FALLBACK_MAX_TURNOVER,
    PRECHECK_FALLBACK_MAX_WEIGHT,
    PRECHECK_FALLBACK_MIN_FITNESS,
    PRECHECK_FALLBACK_MIN_SHARPE,
    PRECHECK_FALLBACK_MIN_TURNOVER,
)
from ..config.runtime_values import get_runtime_config
from ..models.runtime_protocols import SimulationStageArgs

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
    min_sharpe: float = PRECHECK_FALLBACK_MIN_SHARPE
    min_fitness: float = PRECHECK_FALLBACK_MIN_FITNESS
    min_turnover: float = PRECHECK_FALLBACK_MIN_TURNOVER
    max_turnover: float = PRECHECK_FALLBACK_MAX_TURNOVER
    max_weight: float = PRECHECK_FALLBACK_MAX_WEIGHT

    @classmethod
    def from_args(cls, args: SimulationStageArgs) -> PrecheckConfig:
        def _float_attr(name: str, default: float) -> float:
            try:
                return float(getattr(args, name, default))
            except (TypeError, ValueError):
                return default

        return cls(
            min_sharpe=_float_attr("min_sharpe", cls.min_sharpe),
            min_fitness=_float_attr("min_fitness", cls.min_fitness),
            min_turnover=_float_attr("min_turnover", cls.min_turnover),
            max_turnover=_float_attr("max_turnover", cls.max_turnover),
            max_weight=_float_attr("max_weight", cls.max_weight),
        )


def build_default_submit_precheck_config() -> PrecheckConfig:
    """Load submit-grade precheck defaults from the current runtime config."""
    quality = get_runtime_config().submit_quality
    return PrecheckConfig(
        min_sharpe=quality.min_sharpe,
        min_fitness=quality.min_fitness,
        min_turnover=quality.min_turnover,
        max_turnover=quality.max_turnover,
        max_weight=quality.max_weight,
    )


def precheck_simulation_metrics(
    simulation_result: SimulationPayload,
    *,
    min_sharpe: float | None = None,
    min_fitness: float | None = None,
    min_turnover: float | None = None,
    max_turnover: float | None = None,
    max_weight: float | None = None,
) -> tuple[bool, str, list[CheckResultDict]]:
    """Run local metric checks before calling check-submit."""
    if any(
        value is None for value in (min_sharpe, min_fitness, min_turnover, max_turnover, max_weight)
    ):
        default_config = build_default_submit_precheck_config()
        min_sharpe = default_config.min_sharpe if min_sharpe is None else min_sharpe
        min_fitness = default_config.min_fitness if min_fitness is None else min_fitness
        min_turnover = default_config.min_turnover if min_turnover is None else min_turnover
        max_turnover = default_config.max_turnover if max_turnover is None else max_turnover
        max_weight = default_config.max_weight if max_weight is None else max_weight
    assert min_sharpe is not None
    assert min_fitness is not None
    assert min_turnover is not None
    assert max_turnover is not None
    assert max_weight is not None

    is_section = simulation_result.get(_KEY_IS)
    if not isinstance(is_section, dict):
        return True, "", []

    sharpe = is_section.get(_KEY_SHARPE)
    fitness = is_section.get(_KEY_FITNESS)
    turnover = is_section.get(_KEY_TURNOVER)
    max_stock_weight = (
        is_section.get(_KEY_MAX_WEIGHT)
        or is_section.get(_KEY_MAX_WEIGHT_ALT)
        or is_section.get(_KEY_CONCENTRATED_WEIGHT)
    )

    failures: list[CheckResultDict] = []

    def _add_failure(check_name: str, v: int | float, limit: float) -> None:
        failures.append(
            {
                "name": check_name,
                "result": _RESULT_FAIL,
                "value": float(v),
                "limit": limit,
            }
        )

    if isinstance(sharpe, (int, float)) and sharpe < min_sharpe:
        _add_failure(CHECK_LOW_SHARPE, sharpe, min_sharpe)
    if isinstance(fitness, (int, float)) and fitness < min_fitness:
        _add_failure(CHECK_LOW_FITNESS, fitness, min_fitness)
    if isinstance(turnover, (int, float)):
        if turnover < min_turnover:
            _add_failure(CHECK_LOW_TURNOVER, turnover, min_turnover)
        elif turnover > max_turnover:
            _add_failure(CHECK_HIGH_TURNOVER, turnover, max_turnover)
    if isinstance(max_stock_weight, (int, float)) and max_stock_weight > max_weight:
        _add_failure(CHECK_CONCENTRATED_WEIGHT, max_stock_weight, max_weight)

    if not failures:
        return True, "", []

    reason_parts = [
        f"{f['name'].lower()}: {float(f['value']):.4f} vs limit {f['limit']}" for f in failures
    ]
    return False, "; ".join(reason_parts), failures
