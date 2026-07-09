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
from typing import cast

from ..analysis.feedback_history import build_historical_run_state
from ..api.client import BrainClient, WorkerClientFactory, login_with_retry
from ..cli.filters import load_run_filters_extended, setup_runtime_logging
from ..cli.run_config import build_run_config_snapshot
from ..config.runtime_values import get_runtime_config
from ..generators.fields import fetch_fields_with_cache, load_fields_cache
from ..generators.fingerprint import stable_fingerprint
from ..generators.payload import build_settings_fingerprint
from ..generators.templates import ensure_dataset_template_library, load_template_library
from ..analysis.analysis_sync import ensure_analysis_synced
from ..io.credentials import load_credentials
from ..io.output_paths import cleanup_legacy_sidecar_files
from ..models.domain import TemplateField, TemplateLibrary
from ..models.io_types import RunFilters, RunPaths
from ..models.runtime_protocols import (
    ApiClientArgs,
    BootstrapRuntimeArgs,
    ClientFactoryLike,
    CredentialsArgs,
    SimulationSettingsArgs,
)
from ..policy import ensure_template_blacklist_file
from ..policy.blacklist_context import set_active_blacklists_dir
from ..policy.blacklist_store import read_blacklist_payload, summarize_blacklist_payload
from ..policy.expression import get_dataset_expression_policy
from ..runtime import InitializedRunContext, RuntimeConcurrencyState
from .bootstrap_cleanup import clean_runtime_artifacts as clean_runtime_artifacts
from .bootstrap_fields import prepare_fields_for_execution
from .bootstrap_state import build_execution_state
from .bootstrap_steps import (
    create_and_login_client as _create_and_login_client,
    prepare_bootstrap_resources as _prepare_bootstrap_resources,
    prepare_runtime_outputs as _prepare_runtime_outputs,
    resolve_bootstrap_paths as _resolve_bootstrap_paths,
    resolve_credentials as _resolve_credentials,
)
from .bootstrap_types import BootstrapPaths, PreparedBootstrapResources

logger = logging.getLogger(__name__)


def resolve_bootstrap_paths(
    args: BootstrapRuntimeArgs,
    run_paths: RunPaths | None,
) -> BootstrapPaths:
    return _resolve_bootstrap_paths(args, run_paths)


def prepare_runtime_outputs(
    args: BootstrapRuntimeArgs,
    run_paths: RunPaths | None,
    paths: BootstrapPaths,
) -> dict[str, object]:
    return _prepare_runtime_outputs(
        args,
        run_paths,
        paths,
        setup_runtime_logging_fn=setup_runtime_logging,
        cleanup_legacy_sidecar_files_fn=cleanup_legacy_sidecar_files,
        ensure_analysis_synced_fn=ensure_analysis_synced,
        build_run_config_snapshot_fn=build_run_config_snapshot,
    )


def resolve_credentials(
    args: BootstrapRuntimeArgs,
    paths: BootstrapPaths,
) -> tuple[str, str]:
    return _resolve_credentials(
        args,
        paths,
        load_credentials_fn=load_credentials,
    )


def prepare_bootstrap_resources(
    args: BootstrapRuntimeArgs,
    paths: BootstrapPaths,
    bootstrap_client: BrainClient,
    *,
    run_config: dict[str, object],
    run_paths: RunPaths | None,
) -> PreparedBootstrapResources | None:
    return _prepare_bootstrap_resources(
        args,
        paths,
        bootstrap_client,
        run_config=run_config,
        run_paths=run_paths,
        set_active_blacklists_dir_fn=set_active_blacklists_dir,
        ensure_dataset_template_library_fn=ensure_dataset_template_library,
        ensure_template_blacklist_file_fn=ensure_template_blacklist_file,
        load_template_library_fn=load_template_library,
        read_blacklist_payload_fn=read_blacklist_payload,
        summarize_blacklist_payload_fn=summarize_blacklist_payload,
        load_run_filters_extended_fn=load_run_filters_extended,
        get_dataset_expression_policy_fn=get_dataset_expression_policy,
        stable_fingerprint_fn=stable_fingerprint,
        build_settings_fingerprint_fn=build_settings_fingerprint,
        build_historical_run_state_fn=build_historical_run_state,
        load_fields_cache_fn=load_fields_cache,
        fetch_fields_with_cache_fn=fetch_fields_with_cache,
        prepare_fields_for_execution_fn=prepare_fields_for_execution,
    )


def create_and_login_client(
    email: str, password: str, args: ApiClientArgs
) -> tuple[BrainClient, WorkerClientFactory]:
    return cast(
        tuple[BrainClient, WorkerClientFactory],
        _create_and_login_client(
            email,
            password,
            args,
            get_runtime_config_fn=get_runtime_config,
            login_with_retry_fn=login_with_retry,
        ),
    )


def initialize_run_context(
    args: BootstrapRuntimeArgs,
    run_paths: RunPaths | None,
) -> InitializedRunContext | None:
    """执行主流程的初始化阶段，返回结构化运行上下文。"""
    paths = resolve_bootstrap_paths(args, run_paths)
    run_config = prepare_runtime_outputs(args, run_paths, paths)
    email, password = resolve_credentials(args, paths)
    if not email or not password:
        logger.error("[error] 缺少凭证，无法继续")
        return None

    bootstrap_client, client_factory = create_and_login_client(email, password, args)
    prepared = prepare_bootstrap_resources(
        args,
        paths,
        bootstrap_client,
        run_config=run_config,
        run_paths=run_paths,
    )
    if prepared is None:
        return None

    execution_state = build_execution_state(
        dataset_id=cast(str, args.dataset_id),
        output_file=paths.output_file,
        historical_state=prepared.historical_state,
        settings_fingerprint=prepared.settings_fingerprint,
        template_library_fingerprint=prepared.template_library_fingerprint,
        run_config=prepared.run_config,
        blacklists_dir="",
    )

    max_workers = max(1, cast(int, args.max_concurrent_simulations))
    runtime_state = RuntimeConcurrencyState(
        max_workers=max_workers,
        runtime_max_workers=max_workers,
    )
    max_create_workers = max(1, cast(int, args.max_concurrent_creates))
    create_semaphore = threading.Semaphore(max_create_workers)

    logger.info("[config] max_concurrent_simulations=%d", max_workers)
    logger.info("[config] max_concurrent_creates=%d", max_create_workers)
    logger.info("[config] simulation_max_pending_cycles=%d", args.simulation_max_pending_cycles)

    return InitializedRunContext(
        client_factory=cast(ClientFactoryLike, client_factory),
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
