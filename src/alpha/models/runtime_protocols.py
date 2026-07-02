"""Runtime protocol and shared alias definitions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, Union

from .domain import FieldFeedbackSummary, FieldTestResult, TemplateCandidate

TemplateField = dict[str, Any]
TemplateFeedback = FieldFeedbackSummary
TemplateStats = dict[str, dict[str, int]]
RunConfig = dict[str, Any]
BlacklistRuntimeStats = dict[str, dict[str, Any]]


class ApiClientArgs(Protocol):
    min_request_interval: object
    rate_limit_max_retries: object
    login_retries: object


class TemplateBuildArgs(Protocol):
    dataset_id: object
    max_templates_per_field: object
    max_templates_per_family: object
    legacy_similarity_penalty: object
    template_disable_after: object
    disable_legacy_after: object
    region: object
    universe: object
    instrument_type: object
    delay: object
    decay: object
    neutralization: object
    truncation: object
    pasteurization: object
    unit_handling: object
    nan_handling: object
    language: object
    start_date: object
    end_date: object


class ResultWriteArgs(Protocol):
    dataset_id: object
    output: object
    auto_update_blacklist: object


class CleanRuntimeArgs(Protocol):
    include_credentials: object
    dry_run_clean: object


class CredentialsArgs(Protocol):
    email: object
    password: object
    creds_file: object
    creds_key_file: object


class FieldFetchArgs(Protocol):
    dataset_id: object
    page_size: object
    region: object
    universe: object
    instrument_type: object
    delay: object


class FieldSelectionArgs(Protocol):
    top_fields_by_feedback: object
    offset: object
    limit: object


class RunConfigArgs(Protocol):
    dataset_id: object
    region: object
    universe: object
    instrument_type: object
    delay: object
    decay: object
    neutralization: object
    truncation: object
    nan_handling: object
    limit: object
    offset: object
    page_size: object
    sleep_between_fields: object
    max_templates_per_field: object
    max_templates_per_family: object
    field_template_batch_size: object
    legacy_similarity_penalty: object
    disable_legacy_after: object
    max_concurrent_simulations: object
    max_concurrent_creates: object
    simulation_create_retries: object
    simulation_poll_retries: object
    simulation_max_polls: object
    simulation_max_wait_seconds: object
    simulation_max_pending_cycles: object
    simulation_max_queue_seconds: object
    queue_busy_cooldown_seconds: object
    field_queue_busy_skip_after: object
    check_submit_retries: object
    submit_retries: object
    rate_limit_max_retries: object
    login_retries: object
    min_request_interval: object
    template_disable_after: object
    top_fields_by_feedback: object
    stop_after_submittable: object
    submit: object
    auto_update_blacklist: object
    smoke_test: object
    dry_run_plan: object
    full_run: object
    verbose: object
    quiet: object


class StopAfterSubmittableArgs(Protocol):
    stop_after_submittable: object


class BootstrapRuntimeArgs(
    ApiClientArgs,
    CredentialsArgs,
    FieldFetchArgs,
    FieldSelectionArgs,
    RunConfigArgs,
    Protocol,
):
    output: object
    template_library_file: object
    fields_cache_file: object
    max_concurrent_simulations: object
    max_concurrent_creates: object


class SimulationSettingsArgs(Protocol):
    instrument_type: object
    region: object
    universe: object
    delay: object
    decay: object
    neutralization: object
    truncation: object
    pasteurization: object
    unit_handling: object
    nan_handling: object
    language: object
    start_date: object
    end_date: object


class SimulationStageArgs(SimulationSettingsArgs, Protocol):
    simulation_create_retries: object
    simulation_poll_retries: object
    simulation_max_polls: object
    simulation_max_wait_seconds: object
    simulation_max_pending_cycles: object
    simulation_max_queue_seconds: object
    check_submit_retries: object
    submit_retries: object
    submit: object
    min_sharpe: object
    min_fitness: object
    min_turnover: object
    max_turnover: object
    max_weight: object


class SchedulerRuntimeArgs(Protocol):
    queue_busy_cooldown_seconds: object
    field_queue_busy_skip_after: object
    sleep_between_fields: object
    dataset_id: object
    output: object
    auto_update_blacklist: object


class RunLoopArgs(SimulationStageArgs, SchedulerRuntimeArgs, StopAfterSubmittableArgs, Protocol):
    dry_run_plan: object
    field_template_batch_size: object


class ClientFactoryLike(Protocol):
    def create_client(self) -> object: ...


class SemaphoreLike(Protocol):
    def acquire(self, blocking: bool = True, timeout: float | None = -1) -> bool: ...

    def release(self) -> None: ...


PendingFutureLike = Union[dict[str, object], object]
TemplateSequence = Sequence[TemplateCandidate]
HistoricalResults = list[FieldTestResult]
