"""Typed sections and compatibility views for application configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _value(args: object, name: str, default: Any = None) -> Any:
    return getattr(args, name, default)


@dataclass(frozen=True, slots=True, kw_only=True)
class CredentialsConfig:
    email: str | None
    password: str | None
    include_credentials: bool
    dry_run_clean: bool

    @classmethod
    def from_args(cls, args: object) -> CredentialsConfig:
        return cls(
            email=_value(args, "email"),
            password=_value(args, "password"),
            include_credentials=bool(_value(args, "include_credentials", False)),
            dry_run_clean=bool(_value(args, "dry_run_clean", False)),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DatasetConfig:
    dataset_id: str
    region: str
    universe: str
    instrument_type: str
    delay: int

    @classmethod
    def from_args(cls, args: object) -> DatasetConfig:
        return cls(
            dataset_id=str(_value(args, "dataset_id", "") or ""),
            region=str(_value(args, "region", "") or ""),
            universe=str(_value(args, "universe", "") or ""),
            instrument_type=str(_value(args, "instrument_type", "") or ""),
            delay=int(_value(args, "delay", 0) or 0),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SimulationConfig:
    decay: int
    neutralization: str
    truncation: float
    nan_handling: str
    pasteurization: str
    unit_handling: str
    max_trade: str
    language: str
    start_date: str | None
    end_date: str | None
    backfill_window: int

    @classmethod
    def from_args(cls, args: object) -> SimulationConfig:
        return cls(
            decay=int(_value(args, "decay", 0) or 0),
            neutralization=str(_value(args, "neutralization", "") or ""),
            truncation=float(_value(args, "truncation", 0.0) or 0.0),
            nan_handling=str(_value(args, "nan_handling", "") or ""),
            pasteurization=str(_value(args, "pasteurization", "") or ""),
            unit_handling=str(_value(args, "unit_handling", "") or ""),
            max_trade=str(_value(args, "max_trade", "OFF") or "OFF"),
            language=str(_value(args, "language", "") or ""),
            start_date=_value(args, "start_date"),
            end_date=_value(args, "end_date"),
            backfill_window=int(_value(args, "backfill_window", 0) or 0),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PlanningConfig:
    smoke_test: bool
    full_run: bool
    dry_run_plan: bool
    limit: int
    offset: int
    page_size: int
    sleep_between_fields: float
    max_templates_per_field: int
    max_templates_per_family: int
    field_template_batch_size: int
    legacy_similarity_penalty: int
    disable_legacy_after: int
    template_disable_after: int
    top_fields_by_feedback: int
    stop_after_submittable: int

    @classmethod
    def from_args(cls, args: object) -> PlanningConfig:
        return cls(
            smoke_test=bool(_value(args, "smoke_test", False)),
            full_run=bool(_value(args, "full_run", False)),
            dry_run_plan=bool(_value(args, "dry_run_plan", False)),
            limit=int(_value(args, "limit", 0) or 0),
            offset=int(_value(args, "offset", 0) or 0),
            page_size=int(_value(args, "page_size", 0) or 0),
            sleep_between_fields=float(_value(args, "sleep_between_fields", 0.0) or 0.0),
            max_templates_per_field=int(_value(args, "max_templates_per_field", 0) or 0),
            max_templates_per_family=int(_value(args, "max_templates_per_family", 0) or 0),
            field_template_batch_size=int(_value(args, "field_template_batch_size", 0) or 0),
            legacy_similarity_penalty=int(_value(args, "legacy_similarity_penalty", 0) or 0),
            disable_legacy_after=int(_value(args, "disable_legacy_after", 0) or 0),
            template_disable_after=int(_value(args, "template_disable_after", 0) or 0),
            top_fields_by_feedback=int(_value(args, "top_fields_by_feedback", 0) or 0),
            stop_after_submittable=int(_value(args, "stop_after_submittable", 0) or 0),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionConfig:
    min_request_interval: float
    rate_limit_max_retries: int
    login_retries: int
    simulation_create_retries: int
    simulation_poll_retries: int
    max_concurrent_simulations: int
    max_concurrent_creates: int
    simulation_max_polls: int
    simulation_max_wait_seconds: float
    simulation_max_pending_cycles: int
    simulation_max_queue_seconds: float
    queue_busy_cooldown_seconds: float
    field_queue_busy_skip_after: int
    check_submit_retries: int

    @classmethod
    def from_args(cls, args: object) -> ExecutionConfig:
        return cls(
            min_request_interval=float(_value(args, "min_request_interval", 0.0) or 0.0),
            rate_limit_max_retries=int(_value(args, "rate_limit_max_retries", 0) or 0),
            login_retries=int(_value(args, "login_retries", 0) or 0),
            simulation_create_retries=int(_value(args, "simulation_create_retries", 0) or 0),
            simulation_poll_retries=int(_value(args, "simulation_poll_retries", 0) or 0),
            max_concurrent_simulations=int(_value(args, "max_concurrent_simulations", 0) or 0),
            max_concurrent_creates=int(_value(args, "max_concurrent_creates", 0) or 0),
            simulation_max_polls=int(_value(args, "simulation_max_polls", 0) or 0),
            simulation_max_wait_seconds=float(
                _value(args, "simulation_max_wait_seconds", 0.0) or 0.0
            ),
            simulation_max_pending_cycles=int(
                _value(args, "simulation_max_pending_cycles", 0) or 0
            ),
            simulation_max_queue_seconds=float(
                _value(args, "simulation_max_queue_seconds", 0.0) or 0.0
            ),
            queue_busy_cooldown_seconds=float(
                _value(args, "queue_busy_cooldown_seconds", 0.0) or 0.0
            ),
            field_queue_busy_skip_after=int(_value(args, "field_queue_busy_skip_after", 0) or 0),
            check_submit_retries=int(_value(args, "check_submit_retries", 0) or 0),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class QualityConfig:
    min_sharpe: float
    min_fitness: float
    min_turnover: float
    max_turnover: float
    max_weight: float

    def __post_init__(self) -> None:
        if self.max_turnover > 0 and self.min_turnover > self.max_turnover:
            raise ValueError("min_turnover cannot exceed max_turnover")

    @classmethod
    def from_args(cls, args: object) -> QualityConfig:
        return cls(
            min_sharpe=float(_value(args, "min_sharpe", 0.0) or 0.0),
            min_fitness=float(_value(args, "min_fitness", 0.0) or 0.0),
            min_turnover=float(_value(args, "min_turnover", 0.0) or 0.0),
            max_turnover=float(_value(args, "max_turnover", 0.0) or 0.0),
            max_weight=float(_value(args, "max_weight", 0.0) or 0.0),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeFlagsConfig:
    auto_update_blacklist: bool
    verbose: bool
    quiet: bool

    @classmethod
    def from_args(cls, args: object) -> RuntimeFlagsConfig:
        return cls(
            auto_update_blacklist=bool(_value(args, "auto_update_blacklist", False)),
            verbose=bool(_value(args, "verbose", False)),
            quiet=bool(_value(args, "quiet", False)),
        )


class CredentialsConfigView:
    __slots__ = ()

    credentials: CredentialsConfig

    @property
    def email(self) -> str | None:
        return self.credentials.email

    @property
    def password(self) -> str | None:
        return self.credentials.password

    @property
    def include_credentials(self) -> bool:
        return self.credentials.include_credentials

    @property
    def dry_run_clean(self) -> bool:
        return self.credentials.dry_run_clean


class DatasetConfigView:
    __slots__ = ()

    dataset: DatasetConfig

    @property
    def dataset_id(self) -> str:
        return self.dataset.dataset_id

    @property
    def region(self) -> str:
        return self.dataset.region

    @property
    def universe(self) -> str:
        return self.dataset.universe

    @property
    def instrument_type(self) -> str:
        return self.dataset.instrument_type

    @property
    def delay(self) -> int:
        return self.dataset.delay


class SimulationConfigView:
    __slots__ = ()

    simulation: SimulationConfig

    @property
    def decay(self) -> int:
        return self.simulation.decay

    @property
    def neutralization(self) -> str:
        return self.simulation.neutralization

    @property
    def truncation(self) -> float:
        return self.simulation.truncation

    @property
    def nan_handling(self) -> str:
        return self.simulation.nan_handling

    @property
    def pasteurization(self) -> str:
        return self.simulation.pasteurization

    @property
    def unit_handling(self) -> str:
        return self.simulation.unit_handling

    @property
    def max_trade(self) -> str:
        return self.simulation.max_trade

    @property
    def language(self) -> str:
        return self.simulation.language

    @property
    def start_date(self) -> str | None:
        return self.simulation.start_date

    @property
    def end_date(self) -> str | None:
        return self.simulation.end_date

    @property
    def backfill_window(self) -> int:
        return self.simulation.backfill_window


class PlanningConfigView:
    __slots__ = ()

    planning: PlanningConfig

    @property
    def smoke_test(self) -> bool:
        return self.planning.smoke_test

    @property
    def full_run(self) -> bool:
        return self.planning.full_run

    @property
    def dry_run_plan(self) -> bool:
        return self.planning.dry_run_plan

    @property
    def limit(self) -> int:
        return self.planning.limit

    @property
    def offset(self) -> int:
        return self.planning.offset

    @property
    def page_size(self) -> int:
        return self.planning.page_size

    @property
    def sleep_between_fields(self) -> float:
        return self.planning.sleep_between_fields

    @property
    def max_templates_per_field(self) -> int:
        return self.planning.max_templates_per_field

    @property
    def max_templates_per_family(self) -> int:
        return self.planning.max_templates_per_family

    @property
    def field_template_batch_size(self) -> int:
        return self.planning.field_template_batch_size

    @property
    def legacy_similarity_penalty(self) -> int:
        return self.planning.legacy_similarity_penalty

    @property
    def disable_legacy_after(self) -> int:
        return self.planning.disable_legacy_after

    @property
    def template_disable_after(self) -> int:
        return self.planning.template_disable_after

    @property
    def top_fields_by_feedback(self) -> int:
        return self.planning.top_fields_by_feedback

    @property
    def stop_after_submittable(self) -> int:
        return self.planning.stop_after_submittable


class ExecutionConfigView:
    __slots__ = ()

    execution: ExecutionConfig

    @property
    def min_request_interval(self) -> float:
        return self.execution.min_request_interval

    @property
    def rate_limit_max_retries(self) -> int:
        return self.execution.rate_limit_max_retries

    @property
    def login_retries(self) -> int:
        return self.execution.login_retries

    @property
    def simulation_create_retries(self) -> int:
        return self.execution.simulation_create_retries

    @property
    def simulation_poll_retries(self) -> int:
        return self.execution.simulation_poll_retries

    @property
    def max_concurrent_simulations(self) -> int:
        return self.execution.max_concurrent_simulations

    @property
    def max_concurrent_creates(self) -> int:
        return self.execution.max_concurrent_creates

    @property
    def simulation_max_polls(self) -> int:
        return self.execution.simulation_max_polls

    @property
    def simulation_max_wait_seconds(self) -> float:
        return self.execution.simulation_max_wait_seconds

    @property
    def simulation_max_pending_cycles(self) -> int:
        return self.execution.simulation_max_pending_cycles

    @property
    def simulation_max_queue_seconds(self) -> float:
        return self.execution.simulation_max_queue_seconds

    @property
    def queue_busy_cooldown_seconds(self) -> float:
        return self.execution.queue_busy_cooldown_seconds

    @property
    def field_queue_busy_skip_after(self) -> int:
        return self.execution.field_queue_busy_skip_after

    @property
    def check_submit_retries(self) -> int:
        return self.execution.check_submit_retries


class QualityConfigView:
    __slots__ = ()

    quality: QualityConfig

    @property
    def min_sharpe(self) -> float:
        return self.quality.min_sharpe

    @property
    def min_fitness(self) -> float:
        return self.quality.min_fitness

    @property
    def min_turnover(self) -> float:
        return self.quality.min_turnover

    @property
    def max_turnover(self) -> float:
        return self.quality.max_turnover

    @property
    def max_weight(self) -> float:
        return self.quality.max_weight


class RuntimeFlagsConfigView:
    __slots__ = ()

    runtime_flags: RuntimeFlagsConfig

    @property
    def auto_update_blacklist(self) -> bool:
        return self.runtime_flags.auto_update_blacklist

    @property
    def verbose(self) -> bool:
        return self.runtime_flags.verbose

    @property
    def quiet(self) -> bool:
        return self.runtime_flags.quiet
