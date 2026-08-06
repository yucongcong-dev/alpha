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
    SectionField,
    SimulationConfig,
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

    email = SectionField[str | None]("credentials")
    password = SectionField[str | None]("credentials")
    include_credentials = SectionField[bool]("credentials")
    dry_run_clean = SectionField[bool]("credentials")

    dataset_id = SectionField[str]("dataset")
    region = SectionField[str]("dataset")
    universe = SectionField[str]("dataset")
    instrument_type = SectionField[str]("dataset")
    delay = SectionField[int]("dataset")

    decay = SectionField[int]("simulation")
    neutralization = SectionField[str]("simulation")
    truncation = SectionField[float]("simulation")
    nan_handling = SectionField[str]("simulation")
    pasteurization = SectionField[str]("simulation")
    unit_handling = SectionField[str]("simulation")
    max_trade = SectionField[str]("simulation")
    language = SectionField[str]("simulation")
    start_date = SectionField[str | None]("simulation")
    end_date = SectionField[str | None]("simulation")
    backfill_window = SectionField[int]("simulation")

    smoke_test = SectionField[bool]("planning")
    full_run = SectionField[bool]("planning")
    dry_run_plan = SectionField[bool]("planning")
    limit = SectionField[int]("planning")
    offset = SectionField[int]("planning")
    page_size = SectionField[int]("planning")
    sleep_between_fields = SectionField[float]("planning")
    max_templates_per_field = SectionField[int]("planning")
    max_templates_per_family = SectionField[int]("planning")
    max_total_simulations = SectionField[int]("planning")
    field_template_batch_size = SectionField[int]("planning")
    legacy_similarity_penalty = SectionField[int]("planning")
    top_fields_by_feedback = SectionField[int]("planning")

    min_request_interval = SectionField[float]("execution")
    rate_limit_max_retries = SectionField[int]("execution")
    login_retries = SectionField[int]("execution")
    simulation_create_retries = SectionField[int]("execution")
    simulation_poll_retries = SectionField[int]("execution")
    max_concurrent_simulations = SectionField[int]("execution")
    max_concurrent_creates = SectionField[int]("execution")
    simulation_max_polls = SectionField[int]("execution")
    simulation_max_wait_seconds = SectionField[float]("execution")
    simulation_max_pending_cycles = SectionField[int]("execution")
    simulation_max_queue_seconds = SectionField[float]("execution")
    queue_busy_cooldown_seconds = SectionField[float]("execution")
    queue_busy_retry_limit = SectionField[int]("execution")
    check_submission_retries = SectionField[int]("execution")

    min_sharpe = SectionField[float]("quality")
    min_fitness = SectionField[float]("quality")
    min_turnover = SectionField[float]("quality")
    max_turnover = SectionField[float]("quality")
    max_weight = SectionField[float]("quality")

    strategy_profile = SectionField[str]("runtime_flags")
    auto_update_blacklist = SectionField[bool]("runtime_flags")
    verbose = SectionField[bool]("runtime_flags")
    quiet = SectionField[bool]("runtime_flags")

    output = SectionField[str]("paths")
    feedback_output = SectionField[str]("paths")
    template_library_file = SectionField[str]("paths")
    fields_cache_file = SectionField[str]("paths")
    creds_file = SectionField[str]("paths")
    creds_key_file = SectionField[str]("paths")
    include_fields_file = SectionField[str]("paths")
    exclude_fields_file = SectionField[str]("paths")
    include_templates_file = SectionField[str]("paths")
    exclude_templates_file = SectionField[str]("paths")
    log_file = SectionField[str]("paths")
    state_file = SectionField[str]("paths")
    checkpoint_file = SectionField[str]("paths")

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
