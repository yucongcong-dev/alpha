"""Runtime option dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..runtime.preset_mode import resolve_preset_mode
from .runtime_config import SimulationSettingsConfig, SimulationStageConfig

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
class CredentialLoadOptions:
    """Credential values and normalized storage paths used during bootstrap."""

    email: str | None
    password: str | None
    creds_file: str
    creds_key_file: str

    @classmethod
    def from_config(cls, config: ApplicationConfig) -> CredentialLoadOptions:
        return cls(
            email=config.credentials.email,
            password=config.credentials.password,
            creds_file=config.paths.creds_file,
            creds_key_file=config.paths.creds_key_file,
        )


@dataclass(frozen=True, kw_only=True)
class TemplateBuildOptions(SimulationSettingsConfig):
    """模板选择、反馈回路与 settings 变体展开所需的窄配置。"""

    dataset_id: str = ""
    max_templates_per_field: int = 0
    max_templates_per_family: int = 0
    legacy_similarity_penalty: int = 0
    template_library_file: str = ""
    preset_mode: bool = False

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
            simulation_stage=SimulationStageConfig.from_application_config(config),
            result_write=ResultWriteOptions.from_config(config),
            scheduler=SchedulerControlOptions.from_config(config),
            field_template_batch_size=max(1, config.planning.field_template_batch_size),
            full_run=config.planning.full_run,
        )
