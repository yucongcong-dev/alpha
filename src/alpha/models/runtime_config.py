"""Runtime configuration dataclasses used by the active runtime path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.application import ApplicationConfig


@dataclass(frozen=True, kw_only=True)
class SimulationSettingsConfig:
    instrument_type: str
    region: str
    universe: str
    delay: int
    decay: int
    neutralization: str
    truncation: float
    pasteurization: str
    unit_handling: str
    nan_handling: str
    language: str
    max_trade: str = "OFF"
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class SimulationStageConfig(SimulationSettingsConfig):
    simulation_create_retries: int = 0
    simulation_poll_retries: int = 0
    simulation_max_polls: int = 0
    simulation_max_wait_seconds: float = 0.0
    simulation_max_pending_cycles: int = 0
    simulation_max_queue_seconds: float = 0.0
    check_submission_retries: int = 0

    min_sharpe: float = 0.0
    min_fitness: float = 0.0
    min_turnover: float = 0.0
    max_turnover: float = 0.0
    max_weight: float = 0.0

    @classmethod
    def from_application_config(cls, config: ApplicationConfig) -> SimulationStageConfig:
        """Build stage settings from the canonical application config sections."""
        dataset = config.dataset
        simulation = config.simulation
        execution = config.execution
        quality = config.quality
        return cls(
            instrument_type=dataset.instrument_type,
            region=dataset.region,
            universe=dataset.universe,
            delay=dataset.delay,
            decay=simulation.decay,
            neutralization=simulation.neutralization,
            truncation=simulation.truncation,
            pasteurization=simulation.pasteurization,
            unit_handling=simulation.unit_handling,
            nan_handling=simulation.nan_handling,
            language=simulation.language,
            max_trade=simulation.max_trade,
            start_date=simulation.start_date,
            end_date=simulation.end_date,
            simulation_create_retries=execution.simulation_create_retries,
            simulation_poll_retries=execution.simulation_poll_retries,
            simulation_max_polls=execution.simulation_max_polls,
            simulation_max_wait_seconds=execution.simulation_max_wait_seconds,
            simulation_max_pending_cycles=execution.simulation_max_pending_cycles,
            simulation_max_queue_seconds=execution.simulation_max_queue_seconds,
            check_submission_retries=execution.check_submission_retries,
            min_sharpe=quality.min_sharpe,
            min_fitness=quality.min_fitness,
            min_turnover=quality.min_turnover,
            max_turnover=quality.max_turnover,
            max_weight=quality.max_weight,
        )
