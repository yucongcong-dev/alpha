"""Runtime argument protocol definitions."""

from __future__ import annotations

from typing import Protocol


class DatasetIdentityArgs(Protocol):
    @property
    def dataset_id(self) -> str: ...


class MarketScopeArgs(Protocol):
    @property
    def region(self) -> str: ...

    @property
    def universe(self) -> str: ...

    @property
    def instrument_type(self) -> str: ...

    @property
    def delay(self) -> int: ...


class ApiClientArgs(Protocol):
    @property
    def min_request_interval(self) -> float: ...

    @property
    def rate_limit_max_retries(self) -> int: ...

    @property
    def login_retries(self) -> int: ...


class TemplateSelectionArgs(Protocol):
    @property
    def max_templates_per_field(self) -> int: ...

    @property
    def max_templates_per_family(self) -> int: ...

    @property
    def legacy_similarity_penalty(self) -> int: ...

    @property
    def template_library_file(self) -> str: ...


class SimulationSettingsArgs(MarketScopeArgs, Protocol):
    @property
    def decay(self) -> int: ...

    @property
    def neutralization(self) -> str: ...

    @property
    def truncation(self) -> float: ...

    @property
    def pasteurization(self) -> str: ...

    @property
    def unit_handling(self) -> str: ...

    @property
    def nan_handling(self) -> str: ...

    @property
    def max_trade(self) -> str: ...

    @property
    def language(self) -> str: ...

    @property
    def start_date(self) -> str | None: ...

    @property
    def end_date(self) -> str | None: ...


class TemplateBuildArgs(
    DatasetIdentityArgs,
    SimulationSettingsArgs,
    TemplateSelectionArgs,
    Protocol,
):
    pass


class CleanRuntimeArgs(Protocol):
    @property
    def include_credentials(self) -> bool: ...

    @property
    def dry_run_clean(self) -> bool: ...


class CredentialsArgs(Protocol):
    @property
    def email(self) -> str | None: ...

    @property
    def password(self) -> str | None: ...

    @property
    def creds_file(self) -> str: ...

    @property
    def creds_key_file(self) -> str: ...


class BootstrapPathArgs(Protocol):
    @property
    def output(self) -> str: ...

    @property
    def template_library_file(self) -> str: ...

    @property
    def fields_cache_file(self) -> str: ...

    @property
    def creds_file(self) -> str: ...

    @property
    def creds_key_file(self) -> str: ...

    @property
    def include_fields_file(self) -> str: ...

    @property
    def exclude_fields_file(self) -> str: ...

    @property
    def include_templates_file(self) -> str: ...

    @property
    def exclude_templates_file(self) -> str: ...


class FieldFetchArgs(DatasetIdentityArgs, MarketScopeArgs, Protocol):
    @property
    def page_size(self) -> int: ...


class RunSettingsArgs(Protocol):
    @property
    def decay(self) -> int: ...

    @property
    def neutralization(self) -> str: ...

    @property
    def truncation(self) -> float: ...

    @property
    def nan_handling(self) -> str: ...

    @property
    def max_trade(self) -> str: ...


class FieldSelectionArgs(Protocol):
    @property
    def top_fields_by_feedback(self) -> int: ...

    @property
    def offset(self) -> int: ...

    @property
    def limit(self) -> int: ...


class CheckSubmissionRetryArgs(Protocol):
    @property
    def check_submission_retries(self) -> int: ...


class BootstrapFieldArgs(
    FieldFetchArgs,
    FieldSelectionArgs,
    CheckSubmissionRetryArgs,
    Protocol,
):
    pass


class RuntimeConcurrencyArgs(Protocol):
    @property
    def max_concurrent_simulations(self) -> int: ...

    @property
    def max_concurrent_creates(self) -> int: ...

    @property
    def simulation_max_pending_cycles(self) -> int: ...


class SimulationRetryArgs(Protocol):
    @property
    def simulation_create_retries(self) -> int: ...

    @property
    def simulation_poll_retries(self) -> int: ...

    @property
    def simulation_max_polls(self) -> int: ...

    @property
    def simulation_max_wait_seconds(self) -> float: ...

    @property
    def simulation_max_pending_cycles(self) -> int: ...

    @property
    def simulation_max_queue_seconds(self) -> float: ...

    @property
    def check_submission_retries(self) -> int: ...


class SchedulerControlArgs(Protocol):
    @property
    def queue_busy_cooldown_seconds(self) -> float: ...

    @property
    def queue_busy_retry_limit(self) -> int: ...

    @property
    def sleep_between_fields(self) -> float: ...

    @property
    def max_total_simulations(self) -> int: ...


class QualityThresholdArgs(Protocol):
    @property
    def min_sharpe(self) -> float: ...

    @property
    def min_fitness(self) -> float: ...

    @property
    def min_turnover(self) -> float: ...

    @property
    def max_turnover(self) -> float: ...

    @property
    def max_weight(self) -> float: ...


class SimulationStageArgs(
    SimulationSettingsArgs,
    SimulationRetryArgs,
    QualityThresholdArgs,
    Protocol,
):
    pass


class SchedulerRuntimeArgs(
    DatasetIdentityArgs,
    SchedulerControlArgs,
    Protocol,
):
    @property
    def output(self) -> str: ...

    @property
    def auto_update_blacklist(self) -> bool: ...
