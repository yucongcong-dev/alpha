"""
启动与初始化编排模块。

本模块承接主入口中的前置阶段逻辑，包括：
- 字段过滤与优先级排序
- 运行产物清理
- 客户端创建与登录
- 运行上下文初始化
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import threading

from ..analysis.analysis_sync import ensure_analysis_synced
from ..analysis.feedback_history import build_historical_run_state, rebuild_historical_run_state
from ..api.client import BrainClient, WorkerClientFactory, login_with_retry
from ..cli.filters import load_run_filters_extended, setup_runtime_logging
from ..cli.run_config import build_run_config_snapshot
from ..config.application import ApplicationConfig
from ..config.models import DatasetExpressionPolicy
from ..config.runtime_values import get_runtime_config
from ..generators.fields import fetch_fields_with_cache, load_fields_cache
from ..generators.fingerprint import stable_fingerprint
from ..generators.payload import build_settings_fingerprint
from ..generators.templates.library_loader import load_template_library
from ..generators.templates.library_store import ensure_dataset_template_library
from ..io.common import resolve_datasets_root
from ..io.credentials import load_credentials
from ..io.output_paths import cleanup_legacy_sidecar_files
from ..models.domain import TemplateField, TemplateLibrary
from ..models.io_types import RunFilters, RunPaths
from ..models.runtime_options import (
    ApiClientOptions,
    BootstrapFieldOptions,
    BootstrapPathOptions,
    FieldFetchOptions,
    FieldSelectionOptions,
    RunConfigSnapshotOptions,
    TemplateBuildOptions,
)
from ..models.runtime_protocols import (
    ApiClientArgs,
    ClientFactoryLike,
    RunConfig,
    RuntimeConcurrencyArgs,
)
from ..policy.blacklist_context import set_active_datasets_root
from ..policy.blacklist_store import (
    ensure_template_blacklist_file,
    read_blacklist_payload,
    summarize_blacklist_payload,
)
from ..policy.expression import get_dataset_expression_policy
from ..runtime.concurrency import RuntimeConcurrencyState
from ..runtime.contexts import HistoricalRunState
from ..runtime.state import InitializedRunContext
from .bootstrap_cleanup import clean_runtime_artifacts as clean_runtime_artifacts
from .bootstrap_fields import prepare_fields_for_execution, resolve_field_selection
from .bootstrap_state import build_execution_state, refresh_pending_check_results
from .bootstrap_types import (
    ApiClientServices,
    BootstrapPaths,
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
    return assemble_initialized_run_context(
        client_factory=client_factory,
        prepared=prepared,
        execution_state=execution_state,
        runtime_state=concurrency.runtime_state,
        create_semaphore=concurrency.create_semaphore,
    )


logger = logging.getLogger(__name__)


def run_path_value(run_paths: RunPaths | None, attr: str) -> str:
    """从 RunPaths 读取路径属性。"""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def resolve_bootstrap_paths(
    path_options: BootstrapPathOptions,
    run_paths: RunPaths | None,
) -> BootstrapPaths:
    """Resolve all runtime-sensitive paths up front."""
    output_file = run_path_value(run_paths, "output") or path_options.output
    return BootstrapPaths(
        output_file=output_file,
        log_file=run_path_value(run_paths, "log_file"),
        datasets_root=run_path_value(run_paths, "datasets_root") or str(resolve_datasets_root()),
        template_library_file=(
            run_path_value(run_paths, "template_library_file") or path_options.template_library_file
        ),
        fields_cache_file=run_path_value(run_paths, "fields_cache_file")
        or path_options.fields_cache_file,
        feedback_output=run_path_value(run_paths, "feedback_output") or output_file,
        creds_file=run_path_value(run_paths, "creds_file") or path_options.creds_file,
        creds_key_file=run_path_value(run_paths, "creds_key_file") or path_options.creds_key_file,
    )


def build_effective_run_paths(
    path_options: BootstrapPathOptions,
    paths: BootstrapPaths,
    run_paths: RunPaths | None,
) -> RunPaths:
    """Build a minimal RunPaths snapshot even when the caller did not normalize paths."""
    if run_paths is not None:
        return run_paths
    return RunPaths(
        results_dir="",
        log_file=paths.log_file,
        state_file="",
        checkpoint_file="",
        datasets_root=paths.datasets_root,
        fields_cache_file=paths.fields_cache_file,
        template_library_file=paths.template_library_file,
        output=paths.output_file,
        feedback_output=paths.feedback_output,
        creds_file=paths.creds_file,
        creds_key_file=paths.creds_key_file,
        include_fields_file=path_options.include_fields_file,
        exclude_fields_file=path_options.exclude_fields_file,
        include_templates_file=path_options.include_templates_file,
        exclude_templates_file=path_options.exclude_templates_file,
    )


def prepare_runtime_outputs(
    run_config_options: RunConfigSnapshotOptions,
    path_options: BootstrapPathOptions,
    run_paths: RunPaths | None,
    paths: BootstrapPaths,
    *,
    services: RuntimeOutputServices,
) -> RunConfig:
    """Prepare logging/output side effects and capture the embedded run config."""
    effective_run_paths = build_effective_run_paths(path_options, paths, run_paths)
    if paths.log_file:
        services.setup_runtime_logging(paths.log_file)
    services.cleanup_legacy_sidecar_files(paths.output_file, verbose=True)
    services.ensure_analysis_synced(paths.output_file)
    run_config = services.build_run_config_snapshot(run_config_options, effective_run_paths)
    logger.info("[config] 运行配置将嵌入主结果文件")
    return run_config


def resolve_credentials(
    credentials: ResolvedCredentials,
    *,
    services: CredentialServices,
) -> tuple[str, str]:
    """Resolve credentials without mutating the runtime args object."""
    email, password = services.load_credentials(credentials)
    return str(email or ""), str(password or "")


def log_field_selection_stats(
    *,
    dataset_id: str,
    selection_options: FieldSelectionOptions,
    field_stats: dict[str, int],
    fields: list[TemplateField],
) -> None:
    """Emit field-filtering and ranking diagnostics."""
    top_fields_by_feedback, offset, limit = resolve_field_selection(selection_options)
    if field_stats["prefiltered_count"] > 0:
        logger.info(
            "[filter] 排序前因 include/exclude 规则过滤 %d 个字段",
            field_stats["prefiltered_count"],
        )
    metadata_filtered_count = (
        field_stats["low_coverage_count"]
        + field_stats["low_date_coverage_count"]
        + field_stats["low_alpha_count"]
        + field_stats["low_user_count"]
        + field_stats.get("high_alpha_count", 0)
        + field_stats.get("high_user_count", 0)
    )
    if metadata_filtered_count > 0:
        logger.info(
            "[filter] 排序前因官网字段指标过滤 %d 个字段 (coverage=%d, dateCoverage=%d, alphaCount=%d, userCount=%d, crowdedAlpha=%d, crowdedUser=%d)",
            metadata_filtered_count,
            field_stats["low_coverage_count"],
            field_stats["low_date_coverage_count"],
            field_stats["low_alpha_count"],
            field_stats["low_user_count"],
            field_stats.get("high_alpha_count", 0),
            field_stats.get("high_user_count", 0),
        )
    metadata_unknown_count = (
        field_stats.get("unknown_coverage_count", 0)
        + field_stats.get("unknown_date_coverage_count", 0)
        + field_stats.get("unknown_alpha_count", 0)
        + field_stats.get("unknown_user_count", 0)
    )
    if metadata_unknown_count > 0:
        logger.warning(
            "[filter] 官网字段指标缺失 %d 项，将保留字段但降低排序分数 "
            "(coverage=%d, dateCoverage=%d, alphaCount=%d, userCount=%d)",
            metadata_unknown_count,
            field_stats.get("unknown_coverage_count", 0),
            field_stats.get("unknown_date_coverage_count", 0),
            field_stats.get("unknown_alpha_count", 0),
            field_stats.get("unknown_user_count", 0),
        )
    if not fields:
        logger.error("[error] 数据集 %s 在字段过滤后没有可运行字段", dataset_id)
        return
    if top_fields_by_feedback > 0:
        logger.info("[focus] 限制运行到按反馈排序的前 %d 个字段", len(fields))
    logger.info(
        "[data] 当前上下文缓存共 %d 个字段，过滤后共 %d 个字段，优先级排序后共 %d 个字段，本次按 offset=%d limit=%d 取 %d 个字段",
        field_stats["cached_field_count"],
        field_stats["filtered_field_count"],
        field_stats["ranked_field_count"],
        offset,
        limit,
        len(fields),
    )
    logger.info("[data] 从数据集 %s 获取 %d 个字段", dataset_id, len(fields))


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
    refreshed_results, refreshed_count = refresh_pending_check_results(
        bootstrap_client,
        supporting_resources.historical_state.existing_results,
        retries=field_options.check_submit_retries,
    )
    if refreshed_count:
        supporting_resources = replace(
            supporting_resources,
            historical_state=rebuild_historical_run_state(
                supporting_resources.historical_state,
                refreshed_results,
                refresh_feedback=paths.feedback_output == paths.output_file,
            ),
        )
        logger.info(
            "[checksubmit-resume] refreshed %d historical pending results",
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

    effective_run_config = dict(run_config)
    expression_policy = supporting_resources.expression_policy
    effective_run_config["heuristic_policy"] = {
        "dataset_id": dataset_id,
        "policy_version": str(getattr(expression_policy, "policy_version", "unversioned")),
        "feedback_scope": str(getattr(expression_policy, "feedback_scope", "field_type")),
        "use_curated_heuristics": bool(expression_policy.use_curated_heuristics),
    }

    return PreparedBootstrapResources(
        template_library=supporting_resources.template_library,
        filters=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        use_dataset_heuristics=supporting_resources.expression_policy.use_curated_heuristics,
        template_library_fingerprint=supporting_services.stable_fingerprint(
            supporting_resources.template_library
        ),
        settings_fingerprint=supporting_services.build_settings_fingerprint(template_options),
        historical_state=supporting_resources.historical_state,
        fields=prepared_fields,
        run_config=effective_run_config,
    )


def create_and_login_client(
    email: str,
    password: str,
    args: ApiClientArgs,
    *,
    services: ApiClientServices,
) -> tuple[BrainClient, WorkerClientFactory]:
    """创建 Brain API 客户端并完成登录，同时创建工作线程客户端工厂。"""
    client_options = ApiClientOptions.from_args(args)
    http_backend = services.get_runtime_config().http.backend
    bootstrap_client = BrainClient(
        email,
        password,
        min_request_interval=client_options.min_request_interval,
        rate_limit_max_retries=client_options.rate_limit_max_retries,
        http_backend=http_backend,
    )
    services.login_with_retry(bootstrap_client, client_options.login_retries)
    client_factory = WorkerClientFactory(
        client_options,
        email,
        password,
        http_backend=http_backend,
    )
    return bootstrap_client, client_factory


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BootstrapLoadedResources:
    """Non-field bootstrap resources loaded before field fetch and ranking."""

    template_library: TemplateLibrary
    filters: RunFilters
    expression_policy: DatasetExpressionPolicy
    historical_state: HistoricalRunState


def load_bootstrap_supporting_resources(
    *,
    dataset_id: str,
    paths: BootstrapPaths,
    effective_run_paths: RunPaths,
    services: SupportingResourceServices,
) -> BootstrapLoadedResources:
    """Load template library, blacklist, filters, and historical feedback state."""
    return load_supporting_resources(
        dataset_id=dataset_id,
        paths=paths,
        effective_run_paths=effective_run_paths,
        services=services,
        repair_corrupt_summary=True,
        log_blacklist=True,
    )


def load_supporting_resources(
    *,
    dataset_id: str,
    paths: BootstrapPaths,
    effective_run_paths: RunPaths,
    services: SupportingResourceServices,
    repair_corrupt_summary: bool,
    log_blacklist: bool = True,
) -> BootstrapLoadedResources:
    """Load local template, filter, policy, and history resources for a run plan."""
    services.set_active_datasets_root(paths.datasets_root)
    template_library_file = services.ensure_dataset_template_library(
        paths.template_library_file, dataset_id
    )

    template_library = services.load_template_library(template_library_file)
    logger.info(
        "[templates] dataset=%s library=%s entries=%d",
        dataset_id,
        template_library_file,
        sum(len(items) for items in template_library.values()),
    )

    if log_blacklist:
        blacklist_path = services.ensure_template_blacklist_file(dataset_id)
        blacklist_payload = services.read_blacklist_payload(dataset_id)
        learned_count, rule_count = services.summarize_blacklist_payload(blacklist_payload)
        logger.info(
            "[blacklist] dataset=%s file=%s learned_templates=%d expression_rules=%d",
            dataset_id,
            blacklist_path,
            learned_count,
            rule_count,
        )

    return BootstrapLoadedResources(
        template_library=template_library,
        filters=services.load_run_filters_extended(effective_run_paths),
        expression_policy=services.get_dataset_expression_policy(dataset_id),
        historical_state=services.build_historical_run_state(
            paths.output_file,
            paths.feedback_output,
            repair_corrupt_summary=repair_corrupt_summary,
        ),
    )


def load_bootstrap_fields(
    *,
    dataset_id: str,
    bootstrap_client,
    paths: BootstrapPaths,
    field_fetch_options: FieldFetchOptions,
    services: FieldLoadingServices,
) -> list[TemplateField]:
    """Load cached fields and refresh from the upstream source when needed."""
    cached_fields = services.load_fields_cache(
        paths.fields_cache_file,
        dataset_id=dataset_id,
        region=field_fetch_options.region,
        universe=field_fetch_options.universe,
        instrument_type=field_fetch_options.instrument_type,
        delay=field_fetch_options.delay,
    )
    return services.fetch_fields_with_cache(
        bootstrap_client,
        field_fetch_options,
        paths.fields_cache_file,
        cached_fields,
    )
