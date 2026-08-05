"""
启动与初始化编排模块。

本模块承接主入口中的前置阶段逻辑，包括：
- 字段过滤与优先级排序
- 运行产物清理
- 客户端创建与登录
- 运行上下文初始化
"""

from __future__ import annotations

from dataclasses import replace
import logging

from ..analysis.analysis_sync import ensure_analysis_synced
from ..analysis.feedback_history import build_historical_run_state, rebuild_historical_run_state
from ..analysis.feedback_run_index import persist_feedback_run_index
from ..analysis.result_identity import result_identity
from ..api.client import BrainClient, login_with_retry
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
from ..models.runtime_options import (
    BootstrapFieldOptions,
    BootstrapPathOptions,
    RunConfigSnapshotOptions,
    TemplateBuildOptions,
)
from ..models.runtime_protocols import RunConfig
from ..policy.blacklist_context import set_active_datasets_root
from ..policy.blacklist_store import (
    ensure_template_blacklist_file,
    read_blacklist_payload,
    read_blacklist_staging_payload,
    summarize_blacklist_payload,
)
from ..policy.expression import get_dataset_expression_policy
from ..runtime.state import InitializedRunContext
from .bootstrap_cleanup import clean_runtime_artifacts as clean_runtime_artifacts
from .bootstrap_clients import create_and_login_client, resolve_credentials
from .bootstrap_field_resources import load_bootstrap_fields, log_field_selection_stats
from .bootstrap_fields import prepare_fields_for_execution
from .bootstrap_run_context import assemble_initialized_run_context, build_runtime_concurrency
from .bootstrap_runtime_outputs import (
    build_effective_run_paths,
    prepare_runtime_outputs,
    resolve_bootstrap_paths,
)
from .bootstrap_state import (
    build_execution_state,
    persist_reconciled_historical_results,
    refresh_pending_check_results,
)
from .bootstrap_supporting_resources import load_bootstrap_supporting_resources
from .bootstrap_types import (
    ApiClientServices,
    BootstrapPaths,
    BootstrapServices,
    CredentialServices,
    FieldLoadingServices,
    PreparedBootstrapResources,
    ResolvedCredentials,
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
            read_blacklist_staging_payload=read_blacklist_staging_payload,
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


def initialize_run_context(
    args: ApplicationConfig,
    run_paths: RunPaths | None,
) -> InitializedRunContext | None:
    """执行主流程的初始化阶段，返回结构化运行上下文。"""
    services = build_bootstrap_services()
    path_options = BootstrapPathOptions.from_args(args)
    field_options = BootstrapFieldOptions.from_args(args)
    run_config_options = RunConfigSnapshotOptions.from_args(args)
    template_options = TemplateBuildOptions.from_args(args)
    paths = resolve_bootstrap_paths(path_options, run_paths)
    run_config = prepare_runtime_outputs(
        run_config_options,
        path_options,
        run_paths,
        paths,
        services=services.runtime_outputs,
    )
    email, password = resolve_credentials(
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
    run_context: InitializedRunContext | None = None
    try:
        try:
            prepared = prepare_bootstrap_resources(
                path_options,
                field_options,
                template_options,
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
        run_context = assemble_initialized_run_context(
            client_factory=client_factory,
            prepared=prepared,
            execution_state=execution_state,
            runtime_state=concurrency.runtime_state,
            create_semaphore=concurrency.create_semaphore,
        )
        return run_context
    finally:
        if run_context is None:
            close_factory = getattr(client_factory, "close", None)
            if callable(close_factory):
                close_factory()


def prepare_bootstrap_resources(
    path_options: BootstrapPathOptions,
    field_options: BootstrapFieldOptions,
    template_options: TemplateBuildOptions,
    paths: BootstrapPaths,
    bootstrap_client: BrainClient,
    *,
    run_config: RunConfig,
    run_paths: RunPaths | None,
    supporting_services: SupportingResourceServices,
    field_services: FieldLoadingServices,
) -> PreparedBootstrapResources | None:
    """Load template, feedback, and field resources needed to build the run context."""
    dataset_id = field_options.dataset_id
    effective_run_paths = build_effective_run_paths(path_options, paths, run_paths)
    supporting_resources = load_bootstrap_supporting_resources(
        dataset_id=dataset_id,
        paths=paths,
        effective_run_paths=effective_run_paths,
        services=supporting_services,
    )
    expression_policy = supporting_resources.expression_policy
    effective_run_config = dict(run_config)
    effective_run_config["heuristic_policy"] = {
        "dataset_id": dataset_id,
        "policy_version": str(getattr(expression_policy, "policy_version", "unversioned")),
        "feedback_scope": str(getattr(expression_policy, "feedback_scope", "field_type")),
        "use_curated_heuristics": bool(expression_policy.use_curated_heuristics),
    }
    template_library_fingerprint = supporting_services.stable_fingerprint(
        supporting_resources.template_library
    )
    settings_fingerprint = supporting_services.build_settings_fingerprint(template_options)
    historical_state = supporting_resources.historical_state
    existing_results = historical_state.existing_results
    feedback_results = historical_state.feedback_results
    refreshed_feedback_results, refreshed_count = refresh_pending_check_results(
        bootstrap_client,
        feedback_results,
        retries=field_options.check_submission_retries,
    )
    if refreshed_feedback_results != feedback_results:
        refreshed_by_identity = {
            result_identity(result): result for result in refreshed_feedback_results
        }
        refreshed_existing_results = [
            refreshed_by_identity.get(result_identity(result), result)
            for result in existing_results
        ]
        refreshed_state = replace(
            historical_state,
            feedback_results=refreshed_feedback_results,
        )
        supporting_resources = replace(
            supporting_resources,
            historical_state=rebuild_historical_run_state(
                refreshed_state,
                refreshed_existing_results,
            ),
        )
        if refreshed_existing_results != existing_results:
            persist_reconciled_historical_results(
                output_file=paths.output_file,
                dataset_id=dataset_id,
                results=refreshed_existing_results,
                settings_fingerprint=settings_fingerprint,
                template_library_fingerprint=template_library_fingerprint,
                run_config=effective_run_config,
            )
        feedback_output = str(getattr(paths, "feedback_output", "") or "")
        if feedback_output and feedback_output != paths.output_file:
            persist_reconciled_historical_results(
                output_file=feedback_output,
                dataset_id=dataset_id,
                results=refreshed_feedback_results,
                settings_fingerprint=settings_fingerprint,
                template_library_fingerprint=template_library_fingerprint,
                run_config=effective_run_config,
            )
            persist_feedback_run_index(feedback_output)
        if refreshed_count:
            logger.info(
                "[check-submission-resume] refreshed %d historical pending results",
                refreshed_count,
            )
    fields = load_bootstrap_fields(
        dataset_id=dataset_id,
        bootstrap_client=bootstrap_client,
        paths=paths,
        field_fetch_options=field_options.fetch,
        services=field_services,
    )
    if not fields:
        logger.error("[error] 数据集 %s 未返回任何字段", dataset_id)
        return None

    prepared_fields, field_stats = field_services.prepare_fields_for_execution(
        list(fields),
        filters_dict=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        historical_state=supporting_resources.historical_state,
        selection_options=field_options.selection,
    )
    log_field_selection_stats(
        dataset_id=dataset_id,
        selection_options=field_options.selection,
        field_stats=field_stats,
        fields=prepared_fields,
    )
    if not prepared_fields:
        return None
    if supporting_resources.historical_state.existing_results:
        logger.info(
            "[resume] 从 %s 加载 %d 个历史结果",
            paths.output_file,
            len(supporting_resources.historical_state.existing_results),
        )

    return PreparedBootstrapResources(
        template_library=supporting_resources.template_library,
        filters=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        use_dataset_heuristics=supporting_resources.expression_policy.use_curated_heuristics,
        template_library_fingerprint=template_library_fingerprint,
        settings_fingerprint=settings_fingerprint,
        historical_state=supporting_resources.historical_state,
        fields=prepared_fields,
        run_config=effective_run_config,
    )
