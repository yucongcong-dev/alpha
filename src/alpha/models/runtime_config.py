"""Runtime configuration dataclasses.

This module defines typed dataclasses for all runtime configuration,
replacing the Protocol-based approach that allowed argparse.Namespace leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApiClientConfig:
    min_request_interval: float = 0.0
    rate_limit_max_retries: int = 0
    login_retries: int = 0


@dataclass(frozen=True)
class CredentialsConfig:
    email: str | None = None
    password: str | None = None
    creds_file: str = ""
    creds_key_file: str = ""


@dataclass(frozen=True)
class FieldFetchConfig:
    dataset_id: str = ""
    page_size: int = 0
    region: str = ""
    universe: str = ""
    instrument_type: str = ""
    delay: int = 0


@dataclass(frozen=True)
class FieldSelectionConfig:
    top_fields_by_feedback: int = 0
    offset: int = 0
    limit: int = 0


@dataclass(frozen=True)
class TemplateBuildConfig:
    dataset_id: str = ""
    max_templates_per_field: int = 0
    max_templates_per_family: int = 0
    legacy_similarity_penalty: int = 0
    template_disable_after: int = 0
    disable_legacy_after: int = 0
    region: str = "USA"
    universe: str = "TOP3000"
    instrument_type: str = "EQUITY"
    delay: int = 1
    decay: int = 4
    neutralization: str = "SUBINDUSTRY"
    truncation: float = 0.08
    pasteurization: str = "ON"
    unit_handling: str = "VERIFY"
    nan_handling: str = "OFF"
    language: str = "FASTEXPR"
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class ResultWriteConfig:
    dataset_id: str = ""
    output: str = ""
    auto_update_blacklist: bool = False


@dataclass(frozen=True)
class CleanConfig:
    include_credentials: bool = False
    dry_run_clean: bool = False


@dataclass(frozen=True)
class SimulationSettingsConfig:
    instrument_type: str = "EQUITY"
    region: str = "USA"
    universe: str = "TOP3000"
    delay: int = 1
    decay: int = 4
    neutralization: str = "SUBINDUSTRY"
    truncation: float = 0.08
    pasteurization: str = "ON"
    unit_handling: str = "VERIFY"
    nan_handling: str = "OFF"
    language: str = "FASTEXPR"
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class SimulationStageConfig(SimulationSettingsConfig):
    simulation_create_retries: int = 0
    simulation_poll_retries: int = 0
    simulation_max_polls: int = 0
    simulation_max_wait_seconds: int = 0
    simulation_max_pending_cycles: int = 0
    simulation_max_queue_seconds: int = 0
    check_submit_retries: int = 0

    submit_retries: int = 0
    submit: bool = False
    min_sharpe: float = 0.0
    min_fitness: float = 0.0
    min_turnover: float = 0.0
    max_turnover: float = 0.0
    max_weight: float = 0.0


@dataclass(frozen=True)
class SchedulerConfig:
    queue_busy_cooldown_seconds: int = 0
    field_queue_busy_skip_after: int = 0
    sleep_between_fields: float = 0.0
    dataset_id: str = ""
    output: str = ""
    auto_update_blacklist: bool = False


@dataclass(frozen=True)
class RunLoopConfig(SimulationStageConfig, SchedulerConfig):
    dry_run_plan: bool = False
    field_template_batch_size: int = 0
    stop_after_submittable: bool = False


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
    def from_args(cls, args) -> BootstrapConfig:
        """Build a BootstrapConfig from an argparse.Namespace."""
        api_client = ApiClientConfig(
            min_request_interval=float(getattr(args, "min_request_interval", 0.0) or 0.0),
            rate_limit_max_retries=int(getattr(args, "rate_limit_max_retries", 0) or 0),
            login_retries=int(getattr(args, "login_retries", 0) or 0),
        )
        credentials = CredentialsConfig(
            email=getattr(args, "email", None),
            password=getattr(args, "password", None),
            creds_file=str(getattr(args, "creds_file", "") or ""),
            creds_key_file=str(getattr(args, "creds_key_file", "") or ""),
        )
        field_fetch = FieldFetchConfig(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            page_size=int(getattr(args, "page_size", 0) or 0),
            region=str(getattr(args, "region", "") or ""),
            universe=str(getattr(args, "universe", "") or ""),
            instrument_type=str(getattr(args, "instrument_type", "") or ""),
            delay=int(getattr(args, "delay", 0) or 0),
        )
        field_selection = FieldSelectionConfig(
            top_fields_by_feedback=int(getattr(args, "top_fields_by_feedback", 0) or 0),
            offset=int(getattr(args, "offset", 0) or 0),
            limit=int(getattr(args, "limit", 0) or 0),
        )
        template_build = TemplateBuildConfig(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            max_templates_per_field=int(getattr(args, "max_templates_per_field", 0) or 0),
            max_templates_per_family=int(getattr(args, "max_templates_per_family", 0) or 0),
            legacy_similarity_penalty=int(getattr(args, "legacy_similarity_penalty", 0) or 0),
            template_disable_after=int(getattr(args, "template_disable_after", 0) or 0),
            disable_legacy_after=int(getattr(args, "disable_legacy_after", 0) or 0),
            region=str(getattr(args, "region", "USA") or "USA"),
            universe=str(getattr(args, "universe", "TOP3000") or "TOP3000"),
            instrument_type=str(getattr(args, "instrument_type", "EQUITY") or "EQUITY"),
            delay=int(getattr(args, "delay", 1) or 1),
            decay=int(getattr(args, "decay", 4) or 4),
            neutralization=str(getattr(args, "neutralization", "SUBINDUSTRY") or "SUBINDUSTRY"),
            truncation=float(getattr(args, "truncation", 0.08) or 0.08),
            pasteurization=str(getattr(args, "pasteurization", "ON") or "ON"),
            unit_handling=str(getattr(args, "unit_handling", "VERIFY") or "VERIFY"),
            nan_handling=str(getattr(args, "nan_handling", "OFF") or "OFF"),
            language=str(getattr(args, "language", "FASTEXPR") or "FASTEXPR"),
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
        )
        simulation = SimulationStageConfig(
            instrument_type=str(getattr(args, "instrument_type", "") or ""),
            region=str(getattr(args, "region", "") or ""),
            universe=str(getattr(args, "universe", "") or ""),
            delay=int(getattr(args, "delay", 0) or 0),
            decay=int(getattr(args, "decay", 0) or 0),
            neutralization=str(getattr(args, "neutralization", "") or ""),
            truncation=float(getattr(args, "truncation", 0.0) or 0.0),
            pasteurization=str(getattr(args, "pasteurization", "") or ""),
            unit_handling=str(getattr(args, "unit_handling", "") or ""),
            nan_handling=str(getattr(args, "nan_handling", "") or ""),
            language=str(getattr(args, "language", "") or ""),
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
            simulation_create_retries=int(getattr(args, "simulation_create_retries", 0) or 0),
            simulation_poll_retries=int(getattr(args, "simulation_poll_retries", 0) or 0),
            simulation_max_polls=int(getattr(args, "simulation_max_polls", 0) or 0),
            simulation_max_wait_seconds=int(getattr(args, "simulation_max_wait_seconds", 0) or 0),
            simulation_max_pending_cycles=int(getattr(args, "simulation_max_pending_cycles", 0) or 0),
            simulation_max_queue_seconds=int(getattr(args, "simulation_max_queue_seconds", 0) or 0),
            check_submit_retries=int(getattr(args, "check_submit_retries", 0) or 0),
            submit_retries=int(getattr(args, "submit_retries", 0) or 0),
            submit=bool(getattr(args, "submit", False)),
            min_sharpe=float(getattr(args, "min_sharpe", 0.0) or 0.0),
            min_fitness=float(getattr(args, "min_fitness", 0.0) or 0.0),
            min_turnover=float(getattr(args, "min_turnover", 0.0) or 0.0),
            max_turnover=float(getattr(args, "max_turnover", 0.0) or 0.0),
            max_weight=float(getattr(args, "max_weight", 0.0) or 0.0),
        )
        scheduler = SchedulerConfig(
            queue_busy_cooldown_seconds=int(getattr(args, "queue_busy_cooldown_seconds", 0) or 0),
            field_queue_busy_skip_after=int(getattr(args, "field_queue_busy_skip_after", 0) or 0),
            sleep_between_fields=float(getattr(args, "sleep_between_fields", 0.0) or 0.0),
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            output=str(getattr(args, "output", "") or ""),
            auto_update_blacklist=bool(getattr(args, "auto_update_blacklist", False)),
        )
        run_loop = RunLoopConfig(
            instrument_type=str(getattr(args, "instrument_type", "") or ""),
            region=str(getattr(args, "region", "") or ""),
            universe=str(getattr(args, "universe", "") or ""),
            delay=int(getattr(args, "delay", 0) or 0),
            decay=int(getattr(args, "decay", 0) or 0),
            neutralization=str(getattr(args, "neutralization", "") or ""),
            truncation=float(getattr(args, "truncation", 0.0) or 0.0),
            pasteurization=str(getattr(args, "pasteurization", "") or ""),
            unit_handling=str(getattr(args, "unit_handling", "") or ""),
            nan_handling=str(getattr(args, "nan_handling", "") or ""),
            language=str(getattr(args, "language", "") or ""),
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
            simulation_create_retries=int(getattr(args, "simulation_create_retries", 0) or 0),
            simulation_poll_retries=int(getattr(args, "simulation_poll_retries", 0) or 0),
            simulation_max_polls=int(getattr(args, "simulation_max_polls", 0) or 0),
            simulation_max_wait_seconds=int(getattr(args, "simulation_max_wait_seconds", 0) or 0),
            simulation_max_pending_cycles=int(getattr(args, "simulation_max_pending_cycles", 0) or 0),
            simulation_max_queue_seconds=int(getattr(args, "simulation_max_queue_seconds", 0) or 0),
            check_submit_retries=int(getattr(args, "check_submit_retries", 0) or 0),
            submit_retries=int(getattr(args, "submit_retries", 0) or 0),
            submit=bool(getattr(args, "submit", False)),
            min_sharpe=float(getattr(args, "min_sharpe", 0.0) or 0.0),
            min_fitness=float(getattr(args, "min_fitness", 0.0) or 0.0),
            min_turnover=float(getattr(args, "min_turnover", 0.0) or 0.0),
            max_turnover=float(getattr(args, "max_turnover", 0.0) or 0.0),
            max_weight=float(getattr(args, "max_weight", 0.0) or 0.0),
            queue_busy_cooldown_seconds=int(getattr(args, "queue_busy_cooldown_seconds", 0) or 0),
            field_queue_busy_skip_after=int(getattr(args, "field_queue_busy_skip_after", 0) or 0),
            sleep_between_fields=float(getattr(args, "sleep_between_fields", 0.0) or 0.0),
            dry_run_plan=bool(getattr(args, "dry_run_plan", False)),
            field_template_batch_size=int(getattr(args, "field_template_batch_size", 0) or 0),
            stop_after_submittable=bool(getattr(args, "stop_after_submittable", False)),
        )
        result_write = ResultWriteConfig(
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            output=str(getattr(args, "output", "") or ""),
            auto_update_blacklist=bool(getattr(args, "auto_update_blacklist", False)),
        )
        clean = CleanConfig(
            include_credentials=bool(getattr(args, "include_credentials", False)),
            dry_run_clean=bool(getattr(args, "dry_run_clean", False)),
        )

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
            output=str(getattr(args, "output", "") or ""),
            template_library_file=str(getattr(args, "template_library_file", "") or ""),
            fields_cache_file=str(getattr(args, "fields_cache_file", "") or ""),
            max_concurrent_simulations=int(getattr(args, "max_concurrent_simulations", 0) or 0),
            max_concurrent_creates=int(getattr(args, "max_concurrent_creates", 0) or 0),
            smoke_test=bool(getattr(args, "smoke_test", False)),
            full_run=bool(getattr(args, "full_run", False)),
            verbose=bool(getattr(args, "verbose", False)),
            quiet=bool(getattr(args, "quiet", False)),
        )
