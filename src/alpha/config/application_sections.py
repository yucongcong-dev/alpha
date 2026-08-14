"""Typed sections for application configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import re
from typing import Any

from .settings_spec import section_args
from .strategy_profiles import normalize_strategy_profile

_INSTRUMENT_TYPES = frozenset({"EQUITY", "FUTURES"})
_PLATFORM_OPTION_PATTERN = re.compile(r"[A-Z][A-Z0-9_]*")
_ON_OFF_VALUES = frozenset({"ON", "OFF"})
_UNIT_HANDLING_VALUES = frozenset({"VERIFY", "OFF"})
_LANGUAGES = frozenset({"FASTEXPR"})


def _value(args: object, name: str, default: Any = None) -> Any:
    return getattr(args, name, default)


@dataclass(frozen=True, slots=True, kw_only=True)
class CredentialsConfig:
    email: str | None
    password: str | None

    @classmethod
    def from_args(cls, args: object) -> CredentialsConfig:
        return cls(
            email=_value(args, "email"),
            password=_value(args, "password"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DatasetConfig:
    dataset_id: str
    region: str
    universe: str
    instrument_type: str
    delay: int

    def __post_init__(self) -> None:
        for field_name in ("dataset_id", "region", "universe"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be empty")
        if self.instrument_type not in _INSTRUMENT_TYPES:
            raise ValueError(f"instrument_type must be one of {sorted(_INSTRUMENT_TYPES)}")
        if self.delay < 0:
            raise ValueError("delay cannot be negative")

    @classmethod
    def from_args(cls, args: object) -> DatasetConfig:
        return cls(
            dataset_id=str(_value(args, "dataset_id", "") or ""),
            **section_args("dataset", args),
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

    def __post_init__(self) -> None:
        if self.decay < 0:
            raise ValueError("decay cannot be negative")
        if not math.isfinite(self.truncation):
            raise ValueError("truncation must be finite")
        if not 0 <= self.truncation <= 1:
            raise ValueError("truncation must be between 0 and 1")
        if self.backfill_window <= 0:
            raise ValueError("backfill_window must be positive")

        allowed_values = {
            "nan_handling": _ON_OFF_VALUES,
            "pasteurization": _ON_OFF_VALUES,
            "unit_handling": _UNIT_HANDLING_VALUES,
            "max_trade": _ON_OFF_VALUES,
            "language": _LANGUAGES,
        }
        for field_name, choices in allowed_values.items():
            if getattr(self, field_name) not in choices:
                raise ValueError(f"{field_name} must be one of {sorted(choices)}")
        if not _PLATFORM_OPTION_PATTERN.fullmatch(self.neutralization):
            raise ValueError("neutralization must be an uppercase platform option")

        parsed_dates: dict[str, date] = {}
        for field_name in ("start_date", "end_date"):
            value = getattr(self, field_name)
            if value is None:
                continue
            try:
                parsed_dates[field_name] = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"{field_name} must use YYYY-MM-DD format") from exc
        if (
            "start_date" in parsed_dates
            and "end_date" in parsed_dates
            and parsed_dates["start_date"] > parsed_dates["end_date"]
        ):
            raise ValueError("start_date cannot be after end_date")

    @classmethod
    def from_args(cls, args: object) -> SimulationConfig:
        return cls(**section_args("simulation", args))


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
    max_new_simulations: int
    field_template_batch_size: int
    similarity_penalty: int
    top_fields_by_feedback: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.sleep_between_fields):
            raise ValueError("sleep_between_fields must be finite")
        for field_name in (
            "limit",
            "offset",
            "max_templates_per_field",
            "max_templates_per_family",
            "max_new_simulations",
            "similarity_penalty",
            "top_fields_by_feedback",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if self.page_size <= 0:
            raise ValueError("page_size must be positive")
        if self.sleep_between_fields < 0:
            raise ValueError("sleep_between_fields cannot be negative")
        if self.field_template_batch_size <= 0:
            raise ValueError("field_template_batch_size must be positive")

    @classmethod
    def from_args(cls, args: object) -> PlanningConfig:
        return cls(**section_args("planning", args))


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
    queue_busy_retry_limit: int
    check_submission_retries: int

    def __post_init__(self) -> None:
        numeric_values = {
            field_name: getattr(self, field_name)
            for field_name in (
                "min_request_interval",
                "rate_limit_max_retries",
                "login_retries",
                "simulation_create_retries",
                "simulation_poll_retries",
                "max_concurrent_simulations",
                "max_concurrent_creates",
                "simulation_max_polls",
                "simulation_max_wait_seconds",
                "simulation_max_pending_cycles",
                "simulation_max_queue_seconds",
                "queue_busy_cooldown_seconds",
                "queue_busy_retry_limit",
                "check_submission_retries",
            )
        }
        for field_name, value in numeric_values.items():
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite")

        for field_name in (
            "min_request_interval",
            "rate_limit_max_retries",
            "login_retries",
            "simulation_create_retries",
            "simulation_poll_retries",
            "queue_busy_cooldown_seconds",
            "queue_busy_retry_limit",
            "check_submission_retries",
        ):
            if numeric_values[field_name] < 0:
                raise ValueError(f"{field_name} cannot be negative")

        for field_name in (
            "max_concurrent_simulations",
            "max_concurrent_creates",
            "simulation_max_polls",
            "simulation_max_wait_seconds",
            "simulation_max_pending_cycles",
            "simulation_max_queue_seconds",
        ):
            if numeric_values[field_name] <= 0:
                raise ValueError(f"{field_name} must be positive")

    @classmethod
    def from_args(cls, args: object) -> ExecutionConfig:
        return cls(**section_args("execution", args))


@dataclass(frozen=True, slots=True, kw_only=True)
class PendingCheckRefreshConfig:
    """Bounded polling controls used by the check-submissions command."""

    refresh_limit: int
    max_refresh_seconds: float
    max_workers: int

    def __post_init__(self) -> None:
        if self.refresh_limit < 0:
            raise ValueError("pending_check_limit cannot be negative")
        if not math.isfinite(self.max_refresh_seconds) or self.max_refresh_seconds <= 0:
            raise ValueError("pending_check_max_seconds must be positive and finite")
        if self.max_workers <= 0:
            raise ValueError("pending_check_workers must be positive")

    @classmethod
    def from_args(cls, args: object) -> PendingCheckRefreshConfig:
        return cls(
            refresh_limit=int(_value(args, "pending_check_limit", 0) or 0),
            max_refresh_seconds=float(_value(args, "pending_check_max_seconds", 900.0)),
            max_workers=int(_value(args, "pending_check_workers", 1) or 1),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class QualityConfig:
    min_sharpe: float
    min_fitness: float
    min_turnover: float
    max_turnover: float
    max_weight: float

    def __post_init__(self) -> None:
        for field_name in (
            "min_sharpe",
            "min_fitness",
            "min_turnover",
            "max_turnover",
            "max_weight",
        ):
            value = getattr(self, field_name)
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite")
        for field_name in ("min_sharpe", "min_fitness", "min_turnover"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if self.max_turnover <= 0:
            raise ValueError("max_turnover must be positive")
        if self.min_turnover > self.max_turnover:
            raise ValueError("min_turnover cannot exceed max_turnover")
        if not 0 < self.max_weight <= 1:
            raise ValueError("max_weight must be greater than 0 and at most 1")

    @classmethod
    def from_args(cls, args: object) -> QualityConfig:
        return cls(**section_args("quality", args))


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeFlagsConfig:
    strategy_profile: str
    verbose: bool
    quiet: bool

    @classmethod
    def from_args(cls, args: object) -> RuntimeFlagsConfig:
        values = section_args("runtime_flags", args)
        values["strategy_profile"] = normalize_strategy_profile(values["strategy_profile"])
        return cls(**values)
