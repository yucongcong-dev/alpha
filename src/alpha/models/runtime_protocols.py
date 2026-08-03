"""Runtime protocol and shared alias definitions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..api.client import BrainClient

from .domain import FieldTestResult, TemplateCandidate
from .domain_types import FieldFeedbackSummary

TemplateFeedback = FieldFeedbackSummary
TemplateStats = dict[str, dict[str, Any]]
RunConfig = dict[str, object]
BlacklistRuntimeStats = dict[str, dict[str, object]]


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


class ResultWriteArgs(Protocol):
    @property
    def dataset_id(self) -> str: ...

    @property
    def output(self) -> str: ...

    @property
    def auto_update_blacklist(self) -> bool: ...


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


class PlanningRuntimeArgs(Protocol):
    @property
    def limit(self) -> int: ...

    @property
    def offset(self) -> int: ...

    @property
    def page_size(self) -> int: ...

    @property
    def sleep_between_fields(self) -> float: ...

    @property
    def max_templates_per_field(self) -> int: ...

    @property
    def max_templates_per_family(self) -> int: ...

    @property
    def field_template_batch_size(self) -> int: ...

    @property
    def legacy_similarity_penalty(self) -> int: ...

    @property
    def top_fields_by_feedback(self) -> int: ...

    @property
    def stop_after_submittable(self) -> int: ...


class FieldSelectionArgs(Protocol):
    @property
    def top_fields_by_feedback(self) -> int: ...

    @property
    def offset(self) -> int: ...

    @property
    def limit(self) -> int: ...


class CheckSubmitRetryArgs(Protocol):
    @property
    def check_submit_retries(self) -> int: ...


class BootstrapFieldArgs(
    FieldFetchArgs,
    FieldSelectionArgs,
    CheckSubmitRetryArgs,
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
    def check_submit_retries(self) -> int: ...


class SchedulerControlArgs(Protocol):
    @property
    def queue_busy_cooldown_seconds(self) -> float: ...

    @property
    def field_queue_busy_skip_after(self) -> int: ...

    @property
    def sleep_between_fields(self) -> float: ...


class RuntimeModeArgs(Protocol):
    @property
    def auto_update_blacklist(self) -> bool: ...

    @property
    def smoke_test(self) -> bool: ...

    @property
    def dry_run_plan(self) -> bool: ...

    @property
    def full_run(self) -> bool: ...

    @property
    def verbose(self) -> bool: ...

    @property
    def quiet(self) -> bool: ...


class BootstrapRuntimeArgs(
    CredentialsArgs,
    DatasetIdentityArgs,
    SimulationSettingsArgs,
    TemplateSelectionArgs,
    PlanningRuntimeArgs,
    RuntimeConcurrencyArgs,
    SimulationRetryArgs,
    SchedulerControlArgs,
    ApiClientArgs,
    RuntimeModeArgs,
    Protocol,
):
    @property
    def output(self) -> str: ...

    @property
    def fields_cache_file(self) -> str: ...

    @property
    def include_fields_file(self) -> str: ...

    @property
    def exclude_fields_file(self) -> str: ...

    @property
    def include_templates_file(self) -> str: ...

    @property
    def exclude_templates_file(self) -> str: ...


# Deprecated compatibility alias; active application code uses ApplicationConfig.
RunConfigArgs = BootstrapRuntimeArgs


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


class RunLoopArgs(
    TemplateBuildArgs,
    SimulationStageArgs,
    SchedulerRuntimeArgs,
    Protocol,
):
    @property
    def field_template_batch_size(self) -> int: ...

    @property
    def stop_after_submittable(self) -> int: ...


class ClientFactoryLike(Protocol):
    def get_client(self) -> BrainClient: ...

    def close(self) -> None: ...


class SemaphoreLike(Protocol):
    def acquire(self, blocking: bool = True, timeout: float | None = -1) -> bool: ...

    def release(self) -> None: ...


TemplateSequence = Sequence[TemplateCandidate]
HistoricalResults = list[FieldTestResult]
