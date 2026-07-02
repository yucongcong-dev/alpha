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
from ..config.getters import (
    get_submit_max_turnover,
    get_submit_max_weight,
    get_submit_min_fitness,
    get_submit_min_sharpe,
    get_submit_min_turnover,
)
from ..models.runtime import SimulationStageArgs

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
        return cls(
            min_sharpe=getattr(args, "min_sharpe", cls.min_sharpe),
            min_fitness=getattr(args, "min_fitness", cls.min_fitness),
            min_turnover=getattr(args, "min_turnover", cls.min_turnover),
            max_turnover=getattr(args, "max_turnover", cls.max_turnover),
            max_weight=getattr(args, "max_weight", cls.max_weight),
        )


def precheck_simulation_metrics(
    simulation_result: SimulationPayload,
    *,
    min_sharpe: float = get_submit_min_sharpe(),
    min_fitness: float = get_submit_min_fitness(),
    min_turnover: float = get_submit_min_turnover(),
    max_turnover: float = get_submit_max_turnover(),
    max_weight: float = get_submit_max_weight(),
) -> tuple[bool, str, list[CheckResultDict]]:
    """Run local metric checks before calling check-submit."""
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
                _KEY_NAME: check_name,
                _KEY_RESULT: _RESULT_FAIL,
                _KEY_VALUE: float(v),
                _KEY_LIMIT: limit,
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
        f"{f[_KEY_NAME].lower()}: {f[_KEY_VALUE]:.4f} vs limit {f[_KEY_LIMIT]}" for f in failures
    ]
    return False, "; ".join(reason_parts), failures
