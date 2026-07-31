"""Typed sections and compatibility views for application configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast, overload

_T = TypeVar("_T")


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


class SectionField(Generic[_T]):
    """Read-only descriptor forwarding one flat compatibility field to a section."""

    __slots__ = ("field_name", "section_name")

    def __init__(self, section_name: str, field_name: str = "") -> None:
        self.section_name = section_name
        self.field_name = field_name

    def __set_name__(self, _owner: type[object], name: str) -> None:
        if not self.field_name:
            self.field_name = name

    @overload
    def __get__(self, instance: None, owner: type[object] | None = None) -> SectionField[_T]: ...

    @overload
    def __get__(self, instance: object, owner: type[object] | None = None) -> _T: ...

    def __get__(
        self,
        instance: object | None,
        owner: type[object] | None = None,
    ) -> SectionField[_T] | _T:
        if instance is None:
            return self
        section = getattr(instance, self.section_name)
        return cast(_T, getattr(section, self.field_name))
