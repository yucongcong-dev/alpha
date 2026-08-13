"""Immutable application configuration assembled at the CLI boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

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
from .runtime_values import RuntimeConfig, get_runtime_config


@dataclass(frozen=True, slots=True, kw_only=True)
class CleanConfig:
    """Narrow configuration for previewing or confirming runtime cleanup."""

    command: str
    dataset_id: str | None
    all_datasets: bool
    include_credentials: bool
    confirm_clean: bool
    dry_run_clean: bool

    def __post_init__(self) -> None:
        if self.dataset_id and self.all_datasets:
            raise ValueError("clean accepts either --dataset-id or --all-datasets, not both")
        if self.confirm_clean and self.dry_run_clean:
            raise ValueError("--confirm-clean and --dry-run-clean cannot be used together")
        if self.confirm_clean and not (self.dataset_id or self.all_datasets):
            raise ValueError(
                "confirmed clean requires an explicit --dataset-id or --all-datasets scope"
            )
        if self.include_credentials and not self.all_datasets:
            raise ValueError("--include-credentials requires --all-datasets")

    @property
    def preview_only(self) -> bool:
        return self.dry_run_clean or not self.confirm_clean

    @classmethod
    def from_args(cls, args: object) -> CleanConfig:
        explicit_keys = frozenset(getattr(args, "_explicit_cli_keys", frozenset()))
        dataset_id = (
            str(getattr(args, "dataset_id", "") or "").strip()
            if "dataset_id" in explicit_keys
            else ""
        )
        return cls(
            command="clean",
            dataset_id=dataset_id or None,
            all_datasets=bool(getattr(args, "all_datasets", False)),
            include_credentials=bool(getattr(args, "include_credentials", False)),
            confirm_clean=bool(getattr(args, "confirm_clean", False)),
            dry_run_clean=bool(getattr(args, "dry_run_clean", False)),
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
    runtime_values: RuntimeConfig
    config_sources: Mapping[str, str]
    config_source_chains: Mapping[str, tuple[str, ...]]

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
            # YAML-backed waits and feedback thresholds are part of one resolved
            # run. Do not let later stages observe edits made while it is running.
            runtime_values=get_runtime_config(),
            config_sources=MappingProxyType(
                {
                    str(key): str(value)
                    for key, value in dict(getattr(args, "_config_sources", {})).items()
                }
            ),
            config_source_chains=MappingProxyType(
                {
                    str(key): tuple(str(item) for item in value)
                    for key, value in dict(getattr(args, "_config_source_chains", {})).items()
                }
            ),
        )


CommandConfig = ApplicationConfig | CleanConfig
