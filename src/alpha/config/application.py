"""Immutable application configuration assembled at the CLI boundary."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.io_types import RunPaths
from .application_sections import (
    CredentialsConfig,
    CredentialsConfigView,
    DatasetConfig,
    DatasetConfigView,
    ExecutionConfig,
    ExecutionConfigView,
    PlanningConfig,
    PlanningConfigView,
    QualityConfig,
    QualityConfigView,
    RuntimeFlagsConfig,
    RuntimeFlagsConfigView,
    SimulationConfig,
    SimulationConfigView,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplicationConfig(
    CredentialsConfigView,
    DatasetConfigView,
    SimulationConfigView,
    PlanningConfigView,
    ExecutionConfigView,
    QualityConfigView,
    RuntimeFlagsConfigView,
):
    """Validated runtime configuration used after argument parsing.

    ``argparse.Namespace`` remains a CLI implementation detail.  The active
    runtime receives this immutable snapshot, including normalized paths, so
    later stages cannot silently rewrite configuration values.
    """

    paths: RunPaths
    command: str
    config: str
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
            credentials=CredentialsConfig.from_args(args),
            dataset=DatasetConfig.from_args(args),
            simulation=SimulationConfig.from_args(args),
            planning=PlanningConfig.from_args(args),
            execution=ExecutionConfig.from_args(args),
            quality=QualityConfig.from_args(args),
            runtime_flags=RuntimeFlagsConfig.from_args(args),
        )

    @property
    def output(self) -> str:
        return self.paths.output

    @property
    def feedback_output(self) -> str:
        return self.paths.feedback_output

    @property
    def template_library_file(self) -> str:
        return self.paths.template_library_file

    @property
    def fields_cache_file(self) -> str:
        return self.paths.fields_cache_file

    @property
    def creds_file(self) -> str:
        return self.paths.creds_file

    @property
    def creds_key_file(self) -> str:
        return self.paths.creds_key_file

    @property
    def include_fields_file(self) -> str:
        return self.paths.include_fields_file

    @property
    def exclude_fields_file(self) -> str:
        return self.paths.exclude_fields_file

    @property
    def include_templates_file(self) -> str:
        return self.paths.include_templates_file

    @property
    def exclude_templates_file(self) -> str:
        return self.paths.exclude_templates_file

    @property
    def log_file(self) -> str:
        return self.paths.log_file

    @property
    def state_file(self) -> str:
        return self.paths.state_file

    @property
    def checkpoint_file(self) -> str:
        return self.paths.checkpoint_file
