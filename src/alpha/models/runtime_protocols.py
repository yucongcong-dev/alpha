"""Runtime protocol and shared alias definitions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, Union

from .domain import FieldTestResult, TemplateCandidate
from .domain_types import FieldFeedbackSummary

TemplateFeedback = FieldFeedbackSummary
TemplateStats = dict[str, dict[str, int]]
RunConfig = dict[str, object]
BlacklistRuntimeStats = dict[str, dict[str, object]]


class ApiClientArgs(Protocol):
    min_request_interval: float
    rate_limit_max_retries: int
    login_retries: int


class TemplateBuildArgs(Protocol):
    dataset_id: str
    max_templates_per_field: int
    max_templates_per_family: int
    legacy_similarity_penalty: int
    template_disable_after: int
    disable_legacy_after: int
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
    start_date: str | None
    end_date: str | None
    template_library_file: str


class ResultWriteArgs(Protocol):
    dataset_id: str
    output: str
    auto_update_blacklist: bool


class CleanRuntimeArgs(Protocol):
    include_credentials: bool
    dry_run_clean: bool


class CredentialsArgs(Protocol):
    email: str | None
    password: str | None
    creds_file: str
    creds_key_file: str


class FieldFetchArgs(Protocol):
    dataset_id: str
    page_size: int
    region: str
    universe: str
    instrument_type: str
    delay: int


class FieldSelectionArgs(Protocol):
    top_fields_by_feedback: int
    offset: int
    limit: int


class RunConfigArgs(Protocol):
    dataset_id: str
    region: str
    universe: str
    instrument_type: str
    delay: int
    decay: int
    neutralization: str
    truncation: float
    nan_handling: str
    limit: int
    offset: int
    page_size: int
    sleep_between_fields: float
    max_templates_per_field: int
    max_templates_per_family: int
    field_template_batch_size: int
    legacy_similarity_penalty: int
    disable_legacy_after: int
    max_concurrent_simulations: int
    max_concurrent_creates: int
    simulation_create_retries: int
    simulation_poll_retries: int
    simulation_max_polls: int
    simulation_max_wait_seconds: float
    simulation_max_pending_cycles: int
    simulation_max_queue_seconds: float
    queue_busy_cooldown_seconds: float
    field_queue_busy_skip_after: int
    check_submit_retries: int

    rate_limit_max_retries: int
    login_retries: int
    min_request_interval: float
    template_disable_after: int
    top_fields_by_feedback: int
    stop_after_submittable: bool

    auto_update_blacklist: bool
    smoke_test: bool
    dry_run_plan: bool
    full_run: bool
    verbose: bool
    quiet: bool


class StopAfterSubmittableArgs(Protocol):
    stop_after_submittable: bool


class BootstrapRuntimeArgs(
    ApiClientArgs,
    CredentialsArgs,
    FieldFetchArgs,
    FieldSelectionArgs,
    RunConfigArgs,
    Protocol,
):
    output: str
    template_library_file: str
    fields_cache_file: str
    max_concurrent_simulations: int
    max_concurrent_creates: int
    email: str | None
    password: str | None
    include_fields_file: str
    exclude_fields_file: str
    include_templates_file: str
    exclude_templates_file: str


class SimulationSettingsArgs(Protocol):
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
    start_date: str | None
    end_date: str | None


class SimulationStageArgs(SimulationSettingsArgs, Protocol):
    simulation_create_retries: int
    simulation_poll_retries: int
    simulation_max_polls: int
    simulation_max_wait_seconds: float
    simulation_max_pending_cycles: int
    simulation_max_queue_seconds: float
    check_submit_retries: int

    min_sharpe: float
    min_fitness: float
    min_turnover: float
    max_turnover: float
    max_weight: float


class SchedulerRuntimeArgs(Protocol):
    queue_busy_cooldown_seconds: float
    field_queue_busy_skip_after: int
    sleep_between_fields: float
    dataset_id: str
    output: str
    auto_update_blacklist: bool


class RuntimeConcurrencyArgs(Protocol):
    max_concurrent_simulations: int
    max_concurrent_creates: int
    simulation_max_pending_cycles: int


class RunLoopArgs(
    TemplateBuildArgs,
    SimulationStageArgs,
    SchedulerRuntimeArgs,
    StopAfterSubmittableArgs,
    Protocol,
):
    dry_run_plan: bool
    field_template_batch_size: int


class ClientFactoryLike(Protocol):
    def get_client(self) -> object: ...


class SemaphoreLike(Protocol):
    def acquire(self, blocking: bool = True, timeout: float | None = -1) -> bool: ...

    def release(self) -> None: ...


TemplateSequence = Sequence[TemplateCandidate]
HistoricalResults = list[FieldTestResult]
