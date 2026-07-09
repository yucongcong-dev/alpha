"""Runtime configuration dataclasses.

This module defines typed dataclasses for all runtime configuration,
replacing the Protocol-based approach that allowed argparse.Namespace leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .runtime_options import (
    ApiClientOptions,
    FieldFetchOptions,
    ResultWriteOptions,
    TemplateBuildOptions,
)
from .runtime_protocols import (
    ApiClientArgs,
    BootstrapRuntimeArgs,
    CleanRuntimeArgs,
    CredentialsArgs,
    FieldFetchArgs,
    FieldSelectionArgs,
    ResultWriteArgs,
    RunLoopArgs,
    SchedulerRuntimeArgs,
    SimulationSettingsArgs,
    SimulationStageArgs,
    TemplateBuildArgs,
)


@dataclass(frozen=True)
class ApiClientConfig:
    min_request_interval: float = 0.0
    rate_limit_max_retries: int = 0
    login_retries: int = 0

    @classmethod
    def from_args(cls, args: ApiClientArgs) -> ApiClientConfig:
        options = ApiClientOptions.from_args(args)
        return cls(
            min_request_interval=options.min_request_interval,
            rate_limit_max_retries=options.rate_limit_max_retries,
            login_retries=options.login_retries,
        )


@dataclass(frozen=True)
class CredentialsConfig:
    email: str | None = None
    password: str | None = None
    creds_file: str = ""
    creds_key_file: str = ""

    @classmethod
    def from_args(cls, args: CredentialsArgs) -> CredentialsConfig:
        return cls(
            email=args.email,
            password=args.password,
            creds_file=str(args.creds_file or ""),
            creds_key_file=str(args.creds_key_file or ""),
        )


@dataclass(frozen=True)
class FieldFetchConfig:
    region: str
    universe: str
    instrument_type: str
    delay: int
    dataset_id: str = ""
    page_size: int = 0

    @classmethod
    def from_args(cls, args: FieldFetchArgs) -> FieldFetchConfig:
        options = FieldFetchOptions.from_args(args)
        return cls(
            region=options.region,
            universe=options.universe,
            instrument_type=options.instrument_type,
            delay=options.delay,
            dataset_id=options.dataset_id,
            page_size=options.page_size,
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


@dataclass(frozen=True)
class TemplateBuildConfig:
    region: str
    universe: str
    instrument_type: str
    delay: int
    decay: int
    neutralization: str
    truncation: float
    pasteurization: str
    unit_handling: str
    nan_handling: str
    language: str
    dataset_id: str = ""
    max_templates_per_field: int = 0
    max_templates_per_family: int = 0
    legacy_similarity_penalty: int = 0
    template_disable_after: int = 0
    disable_legacy_after: int = 0
    start_date: str | None = None
    end_date: str | None = None

    @classmethod
    def from_args(cls, args: TemplateBuildArgs) -> TemplateBuildConfig:
        options = TemplateBuildOptions.from_args(args)
        return cls(
            region=options.region,
            universe=options.universe,
            instrument_type=options.instrument_type,
            delay=options.delay,
            decay=options.decay,
            neutralization=options.neutralization,
            truncation=options.truncation,
            pasteurization=options.pasteurization,
            unit_handling=options.unit_handling,
            nan_handling=options.nan_handling,
            language=options.language,
            dataset_id=options.dataset_id,
            max_templates_per_field=options.max_templates_per_field,
            max_templates_per_family=options.max_templates_per_family,
            legacy_similarity_penalty=options.legacy_similarity_penalty,
            template_disable_after=options.template_disable_after,
            disable_legacy_after=options.disable_legacy_after,
            start_date=options.start_date,
            end_date=options.end_date,
        )


@dataclass(frozen=True)
class ResultWriteConfig:
    dataset_id: str = ""
    output: str = ""
    auto_update_blacklist: bool = False

    @classmethod
    def from_args(cls, args: ResultWriteArgs) -> ResultWriteConfig:
        options = ResultWriteOptions.from_args(args)
        return cls(
            dataset_id=options.dataset_id,
            output=options.output_path,
            auto_update_blacklist=options.auto_update_blacklist,
        )


@dataclass(frozen=True)
class CleanConfig:
    include_credentials: bool = False
    dry_run_clean: bool = False

    @classmethod
    def from_args(cls, args: CleanRuntimeArgs) -> CleanConfig:
        return cls(
            include_credentials=bool(args.include_credentials),
            dry_run_clean=bool(args.dry_run_clean),
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


@dataclass(frozen=True)
class SchedulerConfig:
    queue_busy_cooldown_seconds: int = 0
    field_queue_busy_skip_after: int = 0
    sleep_between_fields: float = 0.0
    dataset_id: str = ""
    output: str = ""
    auto_update_blacklist: bool = False

    @classmethod
    def from_args(cls, args: SchedulerRuntimeArgs) -> SchedulerConfig:
        return cls(
            queue_busy_cooldown_seconds=int(args.queue_busy_cooldown_seconds or 0),
            field_queue_busy_skip_after=int(args.field_queue_busy_skip_after or 0),
            sleep_between_fields=float(args.sleep_between_fields or 0.0),
            dataset_id=str(args.dataset_id or ""),
            output=str(args.output or ""),
            auto_update_blacklist=bool(args.auto_update_blacklist),
        )


@dataclass(frozen=True)
class RunLoopConfig(SimulationStageConfig, SchedulerConfig):
    dry_run_plan: bool = False
    field_template_batch_size: int = 0
    stop_after_submittable: bool = False

    @classmethod
    def from_args(cls, args: RunLoopArgs) -> RunLoopConfig:
        simulation = SimulationStageConfig.from_args(args)
        scheduler = SchedulerConfig.from_args(args)
        return cls(
            instrument_type=simulation.instrument_type,
            region=simulation.region,
            universe=simulation.universe,
            delay=simulation.delay,
            decay=simulation.decay,
            neutralization=simulation.neutralization,
            truncation=simulation.truncation,
            pasteurization=simulation.pasteurization,
            unit_handling=simulation.unit_handling,
            nan_handling=simulation.nan_handling,
            language=simulation.language,
            start_date=simulation.start_date,
            end_date=simulation.end_date,
            simulation_create_retries=simulation.simulation_create_retries,
            simulation_poll_retries=simulation.simulation_poll_retries,
            simulation_max_polls=simulation.simulation_max_polls,
            simulation_max_wait_seconds=simulation.simulation_max_wait_seconds,
            simulation_max_pending_cycles=simulation.simulation_max_pending_cycles,
            simulation_max_queue_seconds=simulation.simulation_max_queue_seconds,
            check_submit_retries=simulation.check_submit_retries,
            min_sharpe=simulation.min_sharpe,
            min_fitness=simulation.min_fitness,
            min_turnover=simulation.min_turnover,
            max_turnover=simulation.max_turnover,
            max_weight=simulation.max_weight,
            queue_busy_cooldown_seconds=scheduler.queue_busy_cooldown_seconds,
            field_queue_busy_skip_after=scheduler.field_queue_busy_skip_after,
            sleep_between_fields=scheduler.sleep_between_fields,
            dataset_id=scheduler.dataset_id,
            output=scheduler.output,
            auto_update_blacklist=scheduler.auto_update_blacklist,
            dry_run_plan=bool(args.dry_run_plan),
            field_template_batch_size=int(args.field_template_batch_size or 0),
            stop_after_submittable=bool(args.stop_after_submittable),
        )


@dataclass(frozen=True)
class BootstrapConfig:
    api_client: ApiClientConfig = field(default_factory=ApiClientConfig)
    credentials: CredentialsConfig = field(default_factory=CredentialsConfig)
    field_fetch: FieldFetchConfig = field(default_factory=FieldFetchConfig)
    field_selection: FieldSelectionConfig = field(default_factory=FieldSelectionConfig)
    template_build: TemplateBuildConfig = field(default_factory=TemplateBuildConfig)
    simulation: SimulationStageConfig = field(default_factory=SimulationStageConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    run_loop: RunLoopConfig = field(default_factory=RunLoopConfig)
    result_write: ResultWriteConfig = field(default_factory=ResultWriteConfig)
    clean: CleanConfig = field(default_factory=CleanConfig)

    output: str = ""
    template_library_file: str = ""
    fields_cache_file: str = ""
    max_concurrent_simulations: int = 0
    max_concurrent_creates: int = 0
    smoke_test: bool = False
    full_run: bool = False
    verbose: bool = False
    quiet: bool = False

    @classmethod
    def from_args(cls, args: BootstrapRuntimeArgs) -> BootstrapConfig:
        """Build a BootstrapConfig from runtime args without duplicating narrow extractors."""
        api_client = ApiClientConfig.from_args(args)
        credentials = CredentialsConfig.from_args(args)
        field_fetch = FieldFetchConfig.from_args(args)
        field_selection = FieldSelectionConfig.from_args(args)
        template_build = TemplateBuildConfig.from_args(args)
        simulation = SimulationStageConfig.from_args(args)
        scheduler = SchedulerConfig.from_args(args)
        run_loop = RunLoopConfig.from_args(args)
        result_write = ResultWriteConfig.from_args(args)
        clean = CleanConfig.from_args(args)

        return cls(
            api_client=api_client,
            credentials=credentials,
            field_fetch=field_fetch,
            field_selection=field_selection,
            template_build=template_build,
            simulation=simulation,
            scheduler=scheduler,
            run_loop=run_loop,
            result_write=result_write,
            clean=clean,
            output=str(args.output or ""),
            template_library_file=str(args.template_library_file or ""),
            fields_cache_file=str(args.fields_cache_file or ""),
            max_concurrent_simulations=int(args.max_concurrent_simulations or 0),
            max_concurrent_creates=int(args.max_concurrent_creates or 0),
            smoke_test=bool(args.smoke_test),
            full_run=bool(args.full_run),
            verbose=bool(args.verbose),
            quiet=bool(args.quiet),
        )
