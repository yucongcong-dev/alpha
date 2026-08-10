"""Immutable application configuration assembled at the CLI boundary."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.io_types import RunPaths
from .application_sections import (
    CredentialsConfig,
    DatasetConfig,
    ExecutionConfig,
    PlanningConfig,
    QualityConfig,
    RuntimeFlagsConfig,
    SimulationConfig,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CleanConfig:
    """Narrow configuration for the repository-wide cleanup command."""

    command: str
    credentials: CredentialsConfig

    @classmethod
    def from_args(cls, args: object) -> CleanConfig:
        return cls(
            command="clean",
            credentials=CredentialsConfig.from_args(args),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplicationConfig:
    """Validated runtime configuration used after argument parsing.

    ``argparse.Namespace`` remains a CLI implementation detail.  The active
    runtime receives this immutable snapshot, including normalized paths, so
    later stages cannot silently rewrite configuration values.
    """

    paths: RunPaths
    command: str
    config: str
    run_name: str
    credentials: CredentialsConfig
    dataset: DatasetConfig
    simulation: SimulationConfig
    planning: PlanningConfig
    execution: ExecutionConfig
    quality: QualityConfig
    runtime_flags: RuntimeFlagsConfig

    @classmethod
    def from_args(cls, args: object, paths: RunPaths) -> ApplicationConfig:
        """Build a typed immutable snapshot from a resolved CLI namespace."""

        return cls(
            paths=paths,
            command=str(getattr(args, "command", "run")),
            config=str(getattr(args, "config", "") or ""),
            run_name=str(getattr(args, "run_name", "default") or "default"),
            credentials=CredentialsConfig.from_args(args),
            dataset=DatasetConfig.from_args(args),
            simulation=SimulationConfig.from_args(args),
            planning=PlanningConfig.from_args(args),
            execution=ExecutionConfig.from_args(args),
            quality=QualityConfig.from_args(args),
            runtime_flags=RuntimeFlagsConfig.from_args(args),
        )


CommandConfig = ApplicationConfig | CleanConfig
