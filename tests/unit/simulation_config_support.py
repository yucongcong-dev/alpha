"""Shared simulation-stage configuration for focused unit tests."""

from __future__ import annotations

from alpha.models.runtime_config import SimulationStageConfig


def build_simulation_stage_config(**overrides: object) -> SimulationStageConfig:
    values: dict[str, object] = {
        "instrument_type": "EQUITY",
        "region": "USA",
        "universe": "TOP3000",
        "delay": 1,
        "decay": 4,
        "neutralization": "SUBINDUSTRY",
        "truncation": 0.08,
        "pasteurization": "ON",
        "unit_handling": "VERIFY",
        "nan_handling": "OFF",
        "language": "FASTEXPR",
        "max_trade": "OFF",
        "simulation_create_retries": 3,
        "simulation_poll_retries": 3,
        "simulation_max_polls": 10,
        "simulation_max_wait_seconds": 60,
        "simulation_max_pending_cycles": 10,
        "simulation_max_queue_seconds": 30,
        "check_submission_retries": 3,
        "min_sharpe": 1.25,
        "min_fitness": 1.0,
        "min_turnover": 0.01,
        "max_turnover": 0.7,
        "max_weight": 0.1,
    }
    values.update(overrides)
    return SimulationStageConfig(**values)  # type: ignore[arg-type]
