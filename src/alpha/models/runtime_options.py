"""Runtime option dataclasses."""

from __future__ import annotations

from dataclasses import dataclass

from ..config.strategy_profiles import normalize_strategy_profile
from ..runtime.preset_mode import resolve_preset_mode
from .runtime_config import SimulationStageConfig
from .runtime_protocols import (
    ApiClientArgs,
    BootstrapFieldArgs,
    BootstrapPathArgs,
    FieldFetchArgs,
    FieldSelectionArgs,
    ResultWriteArgs,
    RunLoopArgs,
    SchedulerControlArgs,
    TemplateBuildArgs,
)


@dataclass(frozen=True)
class ApiClientOptions:
    """API 客户端与线程级 worker client 的窄配置。"""

    min_request_interval: float = 0.0
    rate_limit_max_retries: int = 0
    login_retries: int = 0

    @classmethod
    def from_args(cls, args: ApiClientArgs) -> ApiClientOptions:
        return cls(
            min_request_interval=float(args.min_request_interval or 0.0),
            rate_limit_max_retries=int(args.rate_limit_max_retries or 0),
            login_retries=int(args.login_retries or 0),
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
    def from_args(cls, args: BootstrapPathArgs) -> BootstrapPathOptions:
        return cls(
            output=str(args.output or ""),
            template_library_file=str(args.template_library_file or ""),
            fields_cache_file=str(args.fields_cache_file or ""),
            creds_file=str(args.creds_file or ""),
            creds_key_file=str(args.creds_key_file or ""),
            include_fields_file=str(args.include_fields_file or ""),
            exclude_fields_file=str(args.exclude_fields_file or ""),
            include_templates_file=str(args.include_templates_file or ""),
            exclude_templates_file=str(args.exclude_templates_file or ""),
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


@dataclass(frozen=True)
class ResultWriteOptions:
    """future 完成后结果落盘与副作用所需的窄配置。"""

    dataset_id: str = ""
    output_path: str = ""
    auto_update_blacklist: bool = False
    auto_update_blacklist_mode: str = "repository"

    @classmethod
    def from_args(cls, args: ResultWriteArgs) -> ResultWriteOptions:
        return cls(
            dataset_id=str(args.dataset_id or ""),
            output_path=str(args.output or ""),
            auto_update_blacklist=bool(getattr(args, "auto_update_blacklist", False)),
            auto_update_blacklist_mode=str(
                getattr(args, "auto_update_blacklist_mode", "repository") or "repository"
            ),
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
    def from_args(cls, args: FieldFetchArgs) -> FieldFetchOptions:
        return cls(
            region=args.region,
            universe=args.universe,
            instrument_type=args.instrument_type,
            delay=args.delay,
            dataset_id=args.dataset_id,
            page_size=int(args.page_size or 0),
        )


@dataclass(frozen=True)
class FieldSelectionOptions:
    """Field ranking and slicing knobs used during bootstrap planning."""

    top_fields_by_feedback: int = 0
    offset: int = 0
    limit: int = 0

    @classmethod
    def from_args(cls, args: FieldSelectionArgs) -> FieldSelectionOptions:
        return cls(
            top_fields_by_feedback=int(getattr(args, "top_fields_by_feedback", 0) or 0),
            offset=int(getattr(args, "offset", 0) or 0),
            limit=int(getattr(args, "limit", 0) or 0),
        )


@dataclass(frozen=True)
class BootstrapFieldOptions:
    """Field loading, pending-check refresh, and selection inputs for bootstrap."""

    dataset_id: str
    check_submission_retries: int
    fetch: FieldFetchOptions
    selection: FieldSelectionOptions

    @classmethod
    def from_args(cls, args: BootstrapFieldArgs) -> BootstrapFieldOptions:
        return cls(
            dataset_id=str(args.dataset_id or ""),
            check_submission_retries=int(getattr(args, "check_submission_retries", 1) or 1),
            fetch=FieldFetchOptions.from_args(args),
            selection=FieldSelectionOptions.from_args(args),
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
    field_queue_busy_skip_after: int = 0
    check_submission_retries: int = 0
    rate_limit_max_retries: int = 0
    login_retries: int = 0
    min_request_interval: float = 0.0
    top_fields_by_feedback: int = 0
    stop_after_submittable: int = 0
    strategy_profile: str = "explore"
    auto_update_blacklist: bool = False
    auto_update_blacklist_mode: str = "repository"
    smoke_test: bool = False
    dry_run_plan: bool = False
    full_run: bool = False
    verbose: bool = False
    quiet: bool = False

    @classmethod
    def from_args(cls, args: object) -> RunConfigSnapshotOptions:
        return cls(
            run_name=str(getattr(args, "run_name", "default") or "default"),
            dataset_id=str(getattr(args, "dataset_id", "") or ""),
            region=str(getattr(args, "region", "") or ""),
            universe=str(getattr(args, "universe", "") or ""),
            instrument_type=str(getattr(args, "instrument_type", "") or ""),
            delay=int(getattr(args, "delay", 0) or 0),
            decay=int(getattr(args, "decay", 0) or 0),
            neutralization=str(getattr(args, "neutralization", "") or ""),
            truncation=float(getattr(args, "truncation", 0.0) or 0.0),
            nan_handling=str(getattr(args, "nan_handling", "") or ""),
            max_trade=str(getattr(args, "max_trade", "OFF") or "OFF"),
            limit=int(getattr(args, "limit", 0) or 0),
            offset=int(getattr(args, "offset", 0) or 0),
            page_size=int(getattr(args, "page_size", 0) or 0),
            sleep_between_fields=float(getattr(args, "sleep_between_fields", 0.0) or 0.0),
            max_templates_per_field=int(getattr(args, "max_templates_per_field", 0) or 0),
            max_templates_per_family=int(getattr(args, "max_templates_per_family", 0) or 0),
            field_template_batch_size=int(getattr(args, "field_template_batch_size", 0) or 0),
            legacy_similarity_penalty=int(getattr(args, "legacy_similarity_penalty", 0) or 0),
            max_concurrent_simulations=int(getattr(args, "max_concurrent_simulations", 0) or 0),
            max_concurrent_creates=int(getattr(args, "max_concurrent_creates", 0) or 0),
            simulation_create_retries=int(getattr(args, "simulation_create_retries", 0) or 0),
            simulation_poll_retries=int(getattr(args, "simulation_poll_retries", 0) or 0),
            simulation_max_polls=int(getattr(args, "simulation_max_polls", 0) or 0),
            simulation_max_wait_seconds=float(
                getattr(args, "simulation_max_wait_seconds", 0.0) or 0.0
            ),
            simulation_max_pending_cycles=int(
                getattr(args, "simulation_max_pending_cycles", 0) or 0
            ),
            simulation_max_queue_seconds=float(
                getattr(args, "simulation_max_queue_seconds", 0.0) or 0.0
            ),
            queue_busy_cooldown_seconds=float(
                getattr(args, "queue_busy_cooldown_seconds", 0.0) or 0.0
            ),
            field_queue_busy_skip_after=int(getattr(args, "field_queue_busy_skip_after", 0) or 0),
            check_submission_retries=int(getattr(args, "check_submission_retries", 0) or 0),
            rate_limit_max_retries=int(getattr(args, "rate_limit_max_retries", 0) or 0),
            login_retries=int(getattr(args, "login_retries", 0) or 0),
            min_request_interval=float(getattr(args, "min_request_interval", 0.0) or 0.0),
            top_fields_by_feedback=int(getattr(args, "top_fields_by_feedback", 0) or 0),
            stop_after_submittable=int(getattr(args, "stop_after_submittable", 0) or 0),
            strategy_profile=normalize_strategy_profile(
                getattr(args, "strategy_profile", "explore")
            ),
            auto_update_blacklist=bool(getattr(args, "auto_update_blacklist", False)),
            auto_update_blacklist_mode=str(
                getattr(args, "auto_update_blacklist_mode", "repository") or "repository"
            ),
            smoke_test=bool(getattr(args, "smoke_test", False)),
            dry_run_plan=bool(getattr(args, "dry_run_plan", False)),
            full_run=bool(getattr(args, "full_run", False)),
            verbose=bool(getattr(args, "verbose", False)),
            quiet=bool(getattr(args, "quiet", False)),
        )


@dataclass(frozen=True)
class SchedulerControlOptions:
    """Queue cooldown, throttling, and stop-condition knobs for scheduling."""

    queue_busy_cooldown_seconds: float = 0.0
    field_queue_busy_skip_after: int = 0
    sleep_between_fields: float = 0.0
    stop_after_submittable: int = 0

    @classmethod
    def from_args(cls, args: SchedulerControlArgs) -> SchedulerControlOptions:
        return cls(
            queue_busy_cooldown_seconds=float(
                getattr(args, "queue_busy_cooldown_seconds", 0.0) or 0.0
            ),
            field_queue_busy_skip_after=int(getattr(args, "field_queue_busy_skip_after", 0) or 0),
            sleep_between_fields=float(getattr(args, "sleep_between_fields", 0.0) or 0.0),
            stop_after_submittable=int(getattr(args, "stop_after_submittable", 0) or 0),
        )


@dataclass(frozen=True)
class RunLoopOptions:
    """Narrow configuration bundle used by the live run loop."""

    template_build: TemplateBuildOptions
    simulation_stage: SimulationStageConfig
    result_write: ResultWriteOptions
    scheduler: SchedulerControlOptions
    field_template_batch_size: int = 0

    @classmethod
    def from_args(cls, args: RunLoopArgs) -> RunLoopOptions:
        return cls(
            template_build=TemplateBuildOptions.from_args(args),
            simulation_stage=SimulationStageConfig.from_stage_args(args),
            result_write=ResultWriteOptions.from_args(args),
            scheduler=SchedulerControlOptions.from_args(args),
            field_template_batch_size=max(
                0,
                int(getattr(args, "field_template_batch_size", 0) or 0),
            ),
        )
