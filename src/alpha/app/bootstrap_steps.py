"""Bootstrap step implementations behind the compatibility facade."""

from __future__ import annotations

from dataclasses import replace
import logging

from ..analysis.feedback_history import rebuild_historical_run_state
from ..api.client import BrainClient, WorkerClientFactory
from ..config.application import ApplicationConfig
from ..io.common import resolve_datasets_root
from ..models.domain import TemplateField
from ..models.io_types import RunPaths
from ..models.runtime_options import (
    ApiClientOptions,
    BootstrapPathOptions,
    FieldFetchOptions,
    FieldSelectionOptions,
)
from ..models.runtime_protocols import (
    ApiClientArgs,
    RunConfig,
)
from .bootstrap_field_ranking import resolve_field_selection
from .bootstrap_pending_checks import refresh_pending_check_results
from .bootstrap_resource_loading import (
    load_bootstrap_fields,
    load_bootstrap_supporting_resources,
)
from .bootstrap_types import (
    ApiClientServices,
    BootstrapPaths,
    CredentialServices,
    FieldLoadingServices,
    PreparedBootstrapResources,
    ResolvedCredentials,
    RuntimeOutputServices,
    SupportingResourceServices,
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
    args: ApplicationConfig,
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
    run_config = services.build_run_config_snapshot(args, effective_run_paths)
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
    args: ApplicationConfig,
    path_options: BootstrapPathOptions,
    paths: BootstrapPaths,
    bootstrap_client: BrainClient,
    *,
    run_config: RunConfig,
    run_paths: RunPaths | None,
    supporting_services: SupportingResourceServices,
    field_services: FieldLoadingServices,
) -> PreparedBootstrapResources | None:
    """Load template, feedback, and field resources needed to build the run context."""
    dataset_id = str(args.dataset_id)
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
        retries=int(getattr(args, "check_submit_retries", 1) or 1),
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
    field_fetch_options = FieldFetchOptions.from_args(args)
    fields = load_bootstrap_fields(
        dataset_id=dataset_id,
        bootstrap_client=bootstrap_client,
        paths=paths,
        field_fetch_options=field_fetch_options,
        services=field_services,
    )
    if not fields:
        logger.error("[error] 数据集 %s 未返回任何字段", args.dataset_id)
        return None

    field_selection_options = FieldSelectionOptions.from_args(args)
    prepared_fields, field_stats = field_services.prepare_fields_for_execution(
        list(fields),
        filters_dict=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        historical_state=supporting_resources.historical_state,
        selection_options=field_selection_options,
    )
    log_field_selection_stats(
        dataset_id=dataset_id,
        selection_options=field_selection_options,
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
        settings_fingerprint=supporting_services.build_settings_fingerprint(args),
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
