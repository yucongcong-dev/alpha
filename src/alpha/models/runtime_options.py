"""Runtime option dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..config.strategy_profiles import normalize_strategy_profile
from ..runtime.preset_mode import resolve_preset_mode
from .runtime_config import SimulationStageConfig
from .runtime_protocols import (
    TemplateBuildArgs,
)

if TYPE_CHECKING:
    from ..config.application import ApplicationConfig


@dataclass(frozen=True)
class ApiClientOptions:
    """API 客户端与线程级 worker client 的窄配置。"""

    min_request_interval: float = 0.0
    rate_limit_max_retries: int = 0
    login_retries: int = 0

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> ApiClientOptions:
        return cls(
            min_request_interval=config.execution.min_request_interval,
            rate_limit_max_retries=config.execution.rate_limit_max_retries,
            login_retries=config.execution.login_retries,
        )


@dataclass(frozen=True)
class BootstrapPathOptions:
    """Bootstrap path inputs normalized away from the full runtime config."""

    output: str = ""
    template_library_file: str = ""
    fields_cache_file: str = ""
    creds_file: str = ""
    creds_key_file: str = ""
    include_fields_file: str = ""
    exclude_fields_file: str = ""
    include_templates_file: str = ""
    exclude_templates_file: str = ""

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> BootstrapPathOptions:
        paths = config.paths
        return cls(
            output=paths.output,
            template_library_file=paths.template_library_file,
            fields_cache_file=paths.fields_cache_file,
            creds_file=paths.creds_file,
            creds_key_file=paths.creds_key_file,
            include_fields_file=paths.include_fields_file,
            exclude_fields_file=paths.exclude_fields_file,
            include_templates_file=paths.include_templates_file,
            exclude_templates_file=paths.exclude_templates_file,
        )


@dataclass(frozen=True)
class TemplateBuildOptions:
    """模板选择、反馈回路与 settings 变体展开所需的窄配置。"""

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
    max_trade: str = "OFF"
    dataset_id: str = ""
    max_templates_per_field: int = 0
    max_templates_per_family: int = 0
    legacy_similarity_penalty: int = 0
    template_library_file: str = ""
    start_date: str | None = None
    end_date: str | None = None
    preset_mode: bool = False

    @classmethod
    def from_args(cls, args: TemplateBuildArgs) -> TemplateBuildOptions:
        template_library_file = str(getattr(args, "template_library_file", "") or "")
        return cls(
            region=args.region,
            universe=args.universe,
            instrument_type=args.instrument_type,
            delay=args.delay,
            decay=args.decay,
            neutralization=args.neutralization,
            truncation=args.truncation,
            pasteurization=args.pasteurization,
            unit_handling=args.unit_handling,
            nan_handling=args.nan_handling,
            language=args.language,
            max_trade=str(getattr(args, "max_trade", "OFF") or "OFF"),
            dataset_id=args.dataset_id,
            max_templates_per_field=int(args.max_templates_per_field or 0),
            max_templates_per_family=int(args.max_templates_per_family or 0),
            legacy_similarity_penalty=int(args.legacy_similarity_penalty or 0),
            template_library_file=template_library_file,
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
            preset_mode=bool(getattr(args, "preset_mode", False))
            or resolve_preset_mode(
                template_library_file=template_library_file,
                include_fields_file=str(getattr(args, "include_fields_file", "") or ""),
                include_templates_file=str(getattr(args, "include_templates_file", "") or ""),
            ),
        )

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> TemplateBuildOptions:
        dataset = config.dataset
        simulation = config.simulation
        planning = config.planning
        paths = config.paths
        return cls(
            region=dataset.region,
            universe=dataset.universe,
            instrument_type=dataset.instrument_type,
            delay=dataset.delay,
            decay=simulation.decay,
            neutralization=simulation.neutralization,
            truncation=simulation.truncation,
            pasteurization=simulation.pasteurization,
            unit_handling=simulation.unit_handling,
            nan_handling=simulation.nan_handling,
            language=simulation.language,
            max_trade=simulation.max_trade,
            dataset_id=dataset.dataset_id,
            max_templates_per_field=planning.max_templates_per_field,
            max_templates_per_family=planning.max_templates_per_family,
            legacy_similarity_penalty=planning.legacy_similarity_penalty,
            template_library_file=paths.template_library_file,
            start_date=simulation.start_date,
            end_date=simulation.end_date,
            preset_mode=resolve_preset_mode(
                template_library_file=paths.template_library_file,
                include_fields_file=paths.include_fields_file,
                include_templates_file=paths.include_templates_file,
            ),
        )


@dataclass(frozen=True)
class ResultWriteOptions:
    """future 完成后结果落盘与副作用所需的窄配置。"""

    dataset_id: str = ""
    output_path: str = ""
    auto_update_blacklist: bool = False

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> ResultWriteOptions:
        """Build result persistence options from canonical config sections."""
        return cls(
            dataset_id=config.dataset.dataset_id,
            output_path=config.paths.output,
            auto_update_blacklist=config.runtime_flags.auto_update_blacklist,
        )


@dataclass(frozen=True)
class FieldFetchOptions:
    """字段缓存校验与字段列表拉取所需的窄配置。"""

    region: str
    universe: str
    instrument_type: str
    delay: int
    dataset_id: str = ""
    page_size: int = 0

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> FieldFetchOptions:
        return cls(
            region=config.dataset.region,
            universe=config.dataset.universe,
            instrument_type=config.dataset.instrument_type,
            delay=config.dataset.delay,
            dataset_id=config.dataset.dataset_id,
            page_size=config.planning.page_size,
        )


@dataclass(frozen=True)
class FieldSelectionOptions:
    """Field ranking and slicing knobs used during bootstrap planning."""

    top_fields_by_feedback: int = 0
    offset: int = 0
    limit: int = 0

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> FieldSelectionOptions:
        return cls(
            top_fields_by_feedback=config.planning.top_fields_by_feedback,
            offset=config.planning.offset,
            limit=config.planning.limit,
        )


@dataclass(frozen=True)
class BootstrapFieldOptions:
    """Field loading, pending-check refresh, and selection inputs for bootstrap."""

    dataset_id: str
    check_submission_retries: int
    fetch: FieldFetchOptions
    selection: FieldSelectionOptions

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> BootstrapFieldOptions:
        return cls(
            dataset_id=config.dataset.dataset_id,
            check_submission_retries=max(1, config.execution.check_submission_retries),
            fetch=FieldFetchOptions.from_config(config),
            selection=FieldSelectionOptions.from_config(config),
        )


@dataclass(frozen=True)
class RunConfigSnapshotOptions:
    """Inputs serialized into the persisted run configuration snapshot."""

    run_name: str = "default"
    dataset_id: str = ""
    region: str = ""
    universe: str = ""
    instrument_type: str = ""
    delay: int = 0
    decay: int = 0
    neutralization: str = ""
    truncation: float = 0.0
    nan_handling: str = ""
    max_trade: str = "OFF"
    limit: int = 0
    offset: int = 0
    page_size: int = 0
    sleep_between_fields: float = 0.0
    max_templates_per_field: int = 0
    max_templates_per_family: int = 0
    max_total_simulations: int = 0
    field_template_batch_size: int = 0
    legacy_similarity_penalty: int = 0
    max_concurrent_simulations: int = 0
    max_concurrent_creates: int = 0
    simulation_create_retries: int = 0
    simulation_poll_retries: int = 0
    simulation_max_polls: int = 0
    simulation_max_wait_seconds: float = 0.0
    simulation_max_pending_cycles: int = 0
    simulation_max_queue_seconds: float = 0.0
    queue_busy_cooldown_seconds: float = 0.0
    queue_busy_retry_limit: int = 0
    check_submission_retries: int = 0
    rate_limit_max_retries: int = 0
    login_retries: int = 0
    min_request_interval: float = 0.0
    top_fields_by_feedback: int = 0
    strategy_profile: str = "explore"
    auto_update_blacklist: bool = False
    smoke_test: bool = False
    dry_run_plan: bool = False
    full_run: bool = False
    verbose: bool = False
    quiet: bool = False

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> RunConfigSnapshotOptions:
        dataset = config.dataset
        simulation = config.simulation
        planning = config.planning
        execution = config.execution
        flags = config.runtime_flags
        return cls(
            run_name=config.run_name,
            dataset_id=dataset.dataset_id,
            region=dataset.region,
            universe=dataset.universe,
            instrument_type=dataset.instrument_type,
            delay=dataset.delay,
            decay=simulation.decay,
            neutralization=simulation.neutralization,
            truncation=simulation.truncation,
            nan_handling=simulation.nan_handling,
            max_trade=simulation.max_trade,
            limit=planning.limit,
            offset=planning.offset,
            page_size=planning.page_size,
            sleep_between_fields=planning.sleep_between_fields,
            max_templates_per_field=planning.max_templates_per_field,
            max_templates_per_family=planning.max_templates_per_family,
            max_total_simulations=planning.max_total_simulations,
            field_template_batch_size=max(1, planning.field_template_batch_size),
            legacy_similarity_penalty=planning.legacy_similarity_penalty,
            max_concurrent_simulations=execution.max_concurrent_simulations,
            max_concurrent_creates=execution.max_concurrent_creates,
            simulation_create_retries=execution.simulation_create_retries,
            simulation_poll_retries=execution.simulation_poll_retries,
            simulation_max_polls=execution.simulation_max_polls,
            simulation_max_wait_seconds=execution.simulation_max_wait_seconds,
            simulation_max_pending_cycles=execution.simulation_max_pending_cycles,
            simulation_max_queue_seconds=execution.simulation_max_queue_seconds,
            queue_busy_cooldown_seconds=execution.queue_busy_cooldown_seconds,
            queue_busy_retry_limit=execution.queue_busy_retry_limit,
            check_submission_retries=execution.check_submission_retries,
            rate_limit_max_retries=execution.rate_limit_max_retries,
            login_retries=execution.login_retries,
            min_request_interval=execution.min_request_interval,
            top_fields_by_feedback=planning.top_fields_by_feedback,
            strategy_profile=normalize_strategy_profile(flags.strategy_profile),
            auto_update_blacklist=flags.auto_update_blacklist,
            smoke_test=planning.smoke_test,
            dry_run_plan=planning.dry_run_plan,
            full_run=planning.full_run,
            verbose=flags.verbose,
            quiet=flags.quiet,
        )


@dataclass(frozen=True)
class SchedulerControlOptions:
    """Queue cooldown, throttling, and stop-condition knobs for scheduling."""

    queue_busy_cooldown_seconds: float = 0.0
    queue_busy_retry_limit: int = 0
    sleep_between_fields: float = 0.0
    max_total_simulations: int = 0

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> SchedulerControlOptions:
        return cls(
            queue_busy_cooldown_seconds=config.execution.queue_busy_cooldown_seconds,
            queue_busy_retry_limit=config.execution.queue_busy_retry_limit,
            sleep_between_fields=config.planning.sleep_between_fields,
            max_total_simulations=config.planning.max_total_simulations,
        )


@dataclass(frozen=True)
class RunLoopOptions:
    """Narrow configuration bundle used by the live run loop."""

    template_build: TemplateBuildOptions
    simulation_stage: SimulationStageConfig
    result_write: ResultWriteOptions
    scheduler: SchedulerControlOptions
    field_template_batch_size: int = 0
    full_run: bool = False

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> RunLoopOptions:
        """Build live-loop options while reading result settings canonically."""
        return cls(
            template_build=TemplateBuildOptions.from_config(config),
            simulation_stage=SimulationStageConfig.from_stage_args(config),
            result_write=ResultWriteOptions.from_config(config),
            scheduler=SchedulerControlOptions.from_config(config),
            field_template_batch_size=max(1, config.planning.field_template_batch_size),
            full_run=config.planning.full_run,
        )
