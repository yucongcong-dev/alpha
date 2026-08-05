"""Typed bootstrap data carriers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from threading import Semaphore
from typing import Protocol

from ..api.client import BrainClient
from ..config.models import DatasetExpressionPolicy
from ..config.runtime_values import RuntimeConfig
from ..generators.fields import DatasetFieldClient
from ..models.domain import TemplateField, TemplateLibrary
from ..models.io_types import RunFilters, RunPaths
from ..models.runtime_options import (
    FieldFetchOptions,
    FieldSelectionOptions,
    RunConfigSnapshotOptions,
)
from ..models.runtime_protocols import CredentialsArgs, RunConfig, SimulationSettingsArgs
from ..policy.types import BlacklistPayload
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import HistoricalRunState


class CleanupLegacySidecarFiles(Protocol):
    """Legacy output cleanup port with its keyword-only verbosity flag."""

    def __call__(self, output_path: str, *, verbose: bool = False) -> None: ...


class LoadFieldsCache(Protocol):
    """Field-cache loading port scoped by the complete dataset context."""

    def __call__(
        self,
        path: str,
        *,
        dataset_id: str,
        region: str,
        universe: str,
        instrument_type: str,
        delay: int,
    ) -> list[TemplateField]: ...


class FetchFieldsWithCache(Protocol):
    """Field fetch port; the client is intentionally structural at this boundary."""

    def __call__(
        self,
        client: DatasetFieldClient,
        options: FieldFetchOptions,
        fields_cache_file: str,
        cached_fields: Sequence[TemplateField],
    ) -> list[TemplateField]: ...


class PrepareFieldsForExecution(Protocol):
    """Field filtering and ranking port."""

    def __call__(
        self,
        fields: list[TemplateField],
        *,
        filters_dict: RunFilters,
        expression_policy: DatasetExpressionPolicy,
        historical_state: HistoricalRunState,
        selection_options: FieldSelectionOptions,
    ) -> tuple[list[TemplateField], dict[str, int]]: ...


class BuildHistoricalRunState(Protocol):
    """Historical-result loader with optional repair side effects."""

    def __call__(
        self,
        output_path: str,
        feedback_output_path: str,
        *,
        repair_corrupt_summary: bool = True,
    ) -> HistoricalRunState: ...


@dataclass(frozen=True)
class RuntimeOutputServices:
    """Side-effecting services used to prepare runtime outputs."""

    cleanup_legacy_sidecar_files: CleanupLegacySidecarFiles
    ensure_analysis_synced: Callable[[str], None]
    build_run_config_snapshot: Callable[[RunConfigSnapshotOptions, RunPaths], RunConfig]


@dataclass(frozen=True)
class SupportingResourceServices:
    """Services that load templates, policy, filters, and historical feedback."""

    set_active_datasets_root: Callable[[str], str]
    ensure_dataset_template_library: Callable[[str, str], str]
    ensure_template_blacklist_file: Callable[[str], str]
    load_template_library: Callable[[str], TemplateLibrary]
    read_blacklist_payload: Callable[[str], BlacklistPayload]
    summarize_blacklist_payload: Callable[[BlacklistPayload], tuple[int, int]]
    load_run_filters_extended: Callable[[RunPaths], RunFilters]
    get_dataset_expression_policy: Callable[[str], DatasetExpressionPolicy]
    stable_fingerprint: Callable[[object], str]
    build_settings_fingerprint: Callable[[SimulationSettingsArgs], str]
    build_historical_run_state: BuildHistoricalRunState


@dataclass(frozen=True)
class FieldLoadingServices:
    """Services used to load, refresh, filter, and rank dataset fields."""

    load_fields_cache: LoadFieldsCache
    fetch_fields_with_cache: FetchFieldsWithCache
    prepare_fields_for_execution: PrepareFieldsForExecution


@dataclass(frozen=True)
class CredentialServices:
    """Credential resolution services used during bootstrap."""

    load_credentials: Callable[[CredentialsArgs], tuple[str | None, str | None]]


@dataclass(frozen=True)
class ApiClientServices:
    """Runtime configuration and login services used to create API clients."""

    get_runtime_config: Callable[[], RuntimeConfig]
    login_with_retry: Callable[[BrainClient, int], None]


@dataclass(frozen=True)
class BootstrapServices:
    """Typed dependency bundle for the bootstrap orchestration boundary."""

    runtime_outputs: RuntimeOutputServices
    supporting_resources: SupportingResourceServices
    field_loading: FieldLoadingServices
    credentials: CredentialServices
    api_client: ApiClientServices


@dataclass(frozen=True)
class ResolvedCredentials:
    """凭证加载所需的最小只读输入。"""

    email: str | None
    password: str | None
    creds_file: str
    creds_key_file: str


@dataclass(frozen=True)
class BootstrapPaths:
    """初始化阶段使用的归一化路径快照。"""

    output_file: str
    log_file: str
    datasets_root: str
    template_library_file: str
    fields_cache_file: str
    feedback_output: str
    creds_file: str
    creds_key_file: str


@dataclass(frozen=True)
class PreparedBootstrapResources:
    """模板、过滤器、反馈和字段等初始化资源集合。"""

    template_library: TemplateLibrary
    filters: RunFilters
    expression_policy: DatasetExpressionPolicy
    use_dataset_heuristics: bool
    template_library_fingerprint: str
    settings_fingerprint: str
    historical_state: HistoricalRunState
    fields: list[TemplateField]
    run_config: RunConfig


@dataclass(frozen=True)
class RuntimeConcurrencyResources:
    """初始化阶段产出的并发调度资源。"""

    runtime_state: RuntimeConcurrencyState
    create_semaphore: Semaphore
