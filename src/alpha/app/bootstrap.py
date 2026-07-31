"""
启动与初始化编排模块。

本模块承接主入口中的前置阶段逻辑，包括：
- 字段过滤与优先级排序
- 运行产物清理
- 客户端创建与登录
- 运行上下文初始化
"""

from __future__ import annotations

import logging
import threading

from ..analysis.analysis_sync import ensure_analysis_synced
from ..analysis.feedback_history import build_historical_run_state
from ..api.client import BrainClient, WorkerClientFactory, login_with_retry
from ..cli.filters import load_run_filters_extended, setup_runtime_logging
from ..cli.run_config import build_run_config_snapshot
from ..config.application import ApplicationConfig
from ..config.runtime_values import get_runtime_config
from ..generators.fields import fetch_fields_with_cache, load_fields_cache
from ..generators.fingerprint import stable_fingerprint
from ..generators.payload import build_settings_fingerprint
from ..generators.templates.library_loader import load_template_library
from ..generators.templates.library_store import ensure_dataset_template_library
from ..io.credentials import load_credentials
from ..io.output_paths import cleanup_legacy_sidecar_files
from ..models.io_types import RunPaths
from ..models.runtime_options import BootstrapPathOptions
from ..models.runtime_protocols import (
    ApiClientArgs,
    ClientFactoryLike,
    RuntimeConcurrencyArgs,
)
from ..policy.blacklist_context import set_active_datasets_root
from ..policy.blacklist_store import (
    ensure_template_blacklist_file,
    read_blacklist_payload,
    summarize_blacklist_payload,
)
from ..policy.expression import get_dataset_expression_policy
from ..runtime.state import InitializedRunContext, RuntimeConcurrencyState
from .bootstrap_cleanup import clean_runtime_artifacts as clean_runtime_artifacts
from .bootstrap_field_selection import prepare_fields_for_execution
from .bootstrap_state import build_execution_state
from .bootstrap_steps import (
    create_and_login_client as _create_and_login_client,
)
from .bootstrap_steps import (
    prepare_bootstrap_resources as _prepare_bootstrap_resources,
)
from .bootstrap_steps import (
    prepare_runtime_outputs as _prepare_runtime_outputs,
)
from .bootstrap_steps import (
    resolve_bootstrap_paths as _resolve_bootstrap_paths,
)
from .bootstrap_steps import (
    resolve_credentials as _resolve_credentials,
)
from .bootstrap_types import (
    ApiClientServices,
    BootstrapServices,
    CredentialServices,
    FieldLoadingServices,
    PreparedBootstrapResources,
    ResolvedCredentials,
    RuntimeConcurrencyResources,
    RuntimeOutputServices,
    SupportingResourceServices,
)

logger = logging.getLogger(__name__)


def build_bootstrap_services() -> BootstrapServices:
    """Build bootstrap dependencies dynamically so test/runtime overrides stay effective."""
    return BootstrapServices(
        runtime_outputs=RuntimeOutputServices(
            setup_runtime_logging=setup_runtime_logging,
            cleanup_legacy_sidecar_files=cleanup_legacy_sidecar_files,
            ensure_analysis_synced=ensure_analysis_synced,
            build_run_config_snapshot=build_run_config_snapshot,
        ),
        supporting_resources=SupportingResourceServices(
            set_active_datasets_root=set_active_datasets_root,
            ensure_dataset_template_library=ensure_dataset_template_library,
            ensure_template_blacklist_file=ensure_template_blacklist_file,
            load_template_library=load_template_library,
            read_blacklist_payload=read_blacklist_payload,
            summarize_blacklist_payload=summarize_blacklist_payload,
            load_run_filters_extended=load_run_filters_extended,
            get_dataset_expression_policy=get_dataset_expression_policy,
            stable_fingerprint=stable_fingerprint,
            build_settings_fingerprint=build_settings_fingerprint,
            build_historical_run_state=build_historical_run_state,
        ),
        field_loading=FieldLoadingServices(
            load_fields_cache=load_fields_cache,
            fetch_fields_with_cache=fetch_fields_with_cache,
            prepare_fields_for_execution=prepare_fields_for_execution,
        ),
        credentials=CredentialServices(load_credentials=load_credentials),
        api_client=ApiClientServices(
            get_runtime_config=get_runtime_config,
            login_with_retry=login_with_retry,
        ),
    )


def create_and_login_client(
    email: str,
    password: str,
    args: ApiClientArgs,
    *,
    services: ApiClientServices | None = None,
) -> tuple[BrainClient, WorkerClientFactory]:
    """兼容导出：创建 Brain API 客户端并完成登录。"""
    active_services = services or ApiClientServices(
        get_runtime_config=get_runtime_config,
        login_with_retry=login_with_retry,
    )
    return _create_and_login_client(
        email,
        password,
        args,
        services=active_services,
    )


def build_runtime_concurrency(
    args: RuntimeConcurrencyArgs,
) -> RuntimeConcurrencyResources:
    """Build runtime concurrency state and semaphore from narrow concurrency args."""
    max_workers = max(1, int(args.max_concurrent_simulations or 0))
    runtime_state = RuntimeConcurrencyState(
        max_workers=max_workers,
        runtime_max_workers=max_workers,
    )
    max_create_workers = max(1, int(args.max_concurrent_creates or 0))
    create_semaphore = threading.Semaphore(max_create_workers)
    logger.info("[config] max_concurrent_simulations=%d", max_workers)
    logger.info("[config] max_concurrent_creates=%d", max_create_workers)
    logger.info("[config] simulation_max_pending_cycles=%d", args.simulation_max_pending_cycles)
    return RuntimeConcurrencyResources(
        runtime_state=runtime_state,
        create_semaphore=create_semaphore,
    )


def assemble_initialized_run_context(
    *,
    client_factory: ClientFactoryLike,
    prepared: PreparedBootstrapResources,
    execution_state,
    runtime_state: RuntimeConcurrencyState,
    create_semaphore: threading.Semaphore,
) -> InitializedRunContext:
    """Assemble the final initialized run context from prepared bootstrap parts."""
    return InitializedRunContext(
        client_factory=client_factory,
        template_library=prepared.template_library,
        filters=prepared.filters,
        expression_policy=prepared.expression_policy,
        use_dataset_heuristics=prepared.use_dataset_heuristics,
        template_library_fingerprint=prepared.template_library_fingerprint,
        settings_fingerprint=prepared.settings_fingerprint,
        historical_state=prepared.historical_state,
        fields=prepared.fields,
        execution_state=execution_state,
        runtime_state=runtime_state,
        create_semaphore=create_semaphore,
        run_config=prepared.run_config,
    )


def initialize_run_context(
    args: ApplicationConfig,
    run_paths: RunPaths | None,
) -> InitializedRunContext | None:
    """执行主流程的初始化阶段，返回结构化运行上下文。"""
    services = build_bootstrap_services()
    path_options = BootstrapPathOptions.from_args(args)
    paths = _resolve_bootstrap_paths(path_options, run_paths)
    run_config = _prepare_runtime_outputs(
        args,
        path_options,
        run_paths,
        paths,
        services=services.runtime_outputs,
    )
    email, password = _resolve_credentials(
        ResolvedCredentials(
            email=args.email,
            password=args.password,
            creds_file=paths.creds_file,
            creds_key_file=paths.creds_key_file,
        ),
        services=services.credentials,
    )
    if not email or not password:
        logger.error("[error] 缺少凭证，无法继续")
        return None

    bootstrap_client, client_factory = create_and_login_client(
        email,
        password,
        args,
        services=services.api_client,
    )
    try:
        prepared = _prepare_bootstrap_resources(
            args,
            path_options,
            paths,
            bootstrap_client,
            run_config=run_config,
            run_paths=run_paths,
            supporting_services=services.supporting_resources,
            field_services=services.field_loading,
        )
    finally:
        close = getattr(bootstrap_client, "close", None)
        if callable(close):
            close()
    if prepared is None:
        return None

    execution_state = build_execution_state(
        dataset_id=str(args.dataset_id),
        output_file=paths.output_file,
        historical_state=prepared.historical_state,
        settings_fingerprint=prepared.settings_fingerprint,
        template_library_fingerprint=prepared.template_library_fingerprint,
        run_config=prepared.run_config,
        datasets_root=paths.datasets_root,
    )

    concurrency = build_runtime_concurrency(args)
    return assemble_initialized_run_context(
        client_factory=client_factory,
        prepared=prepared,
        execution_state=execution_state,
        runtime_state=concurrency.runtime_state,
        create_semaphore=concurrency.create_semaphore,
    )
