"""Runtime configuration dataclasses used by the active runtime path."""

from __future__ import annotations

from dataclasses import dataclass

from .runtime_protocols import (
    FieldSelectionArgs,
    SimulationSettingsArgs,
    SimulationStageArgs,
)


@dataclass(frozen=True)
class FieldSelectionConfig:
    top_fields_by_feedback: int = 0
    offset: int = 0
    limit: int = 0

    @classmethod
    def from_args(cls, args: FieldSelectionArgs) -> FieldSelectionConfig:
        return cls(
            top_fields_by_feedback=int(args.top_fields_by_feedback or 0),
            offset=int(args.offset or 0),
            limit=int(args.limit or 0),
        )


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

    @classmethod
    def from_args(cls, args: SimulationSettingsArgs) -> SimulationSettingsConfig:
        return cls(
            instrument_type=args.instrument_type,
            region=args.region,
            universe=args.universe,
            delay=args.delay,
            decay=args.decay,
            neutralization=args.neutralization,
            truncation=args.truncation,
            pasteurization=args.pasteurization,
            unit_handling=args.unit_handling,
            nan_handling=args.nan_handling,
            language=args.language,
            max_trade=str(getattr(args, "max_trade", "OFF") or "OFF"),
            start_date=args.start_date,
            end_date=args.end_date,
        )


@dataclass(frozen=True)
class SimulationStageConfig(SimulationSettingsConfig):
    simulation_create_retries: int = 0
    simulation_poll_retries: int = 0
    simulation_max_polls: int = 0
    simulation_max_wait_seconds: int = 0
    simulation_max_pending_cycles: int = 0
    simulation_max_queue_seconds: int = 0
    check_submit_retries: int = 0


    min_sharpe: float = 0.0
    min_fitness: float = 0.0
    min_turnover: float = 0.0
    max_turnover: float = 0.0
    max_weight: float = 0.0

    @classmethod
    def from_args(cls, args: SimulationStageArgs) -> SimulationStageConfig:
        settings = SimulationSettingsConfig.from_args(args)
        return cls(
            instrument_type=settings.instrument_type,
            region=settings.region,
            universe=settings.universe,
            delay=settings.delay,
            decay=settings.decay,
            neutralization=settings.neutralization,
            truncation=settings.truncation,
            pasteurization=settings.pasteurization,
            unit_handling=settings.unit_handling,
            nan_handling=settings.nan_handling,
            language=settings.language,
            max_trade=settings.max_trade,
            start_date=settings.start_date,
            end_date=settings.end_date,
            simulation_create_retries=int(args.simulation_create_retries or 0),
            simulation_poll_retries=int(args.simulation_poll_retries or 0),
            simulation_max_polls=int(args.simulation_max_polls or 0),
            simulation_max_wait_seconds=int(args.simulation_max_wait_seconds or 0),
            simulation_max_pending_cycles=int(args.simulation_max_pending_cycles or 0),
            simulation_max_queue_seconds=int(args.simulation_max_queue_seconds or 0),
            check_submit_retries=int(args.check_submit_retries or 0),
            min_sharpe=float(args.min_sharpe or 0.0),
            min_fitness=float(args.min_fitness or 0.0),
            min_turnover=float(args.min_turnover or 0.0),
            max_turnover=float(args.max_turnover or 0.0),
            max_weight=float(args.max_weight or 0.0),
        )
