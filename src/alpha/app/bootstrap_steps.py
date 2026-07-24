"""Bootstrap step implementations behind the compatibility facade."""

from __future__ import annotations

import logging

from ..api.client import BrainClient, WorkerClientFactory
from ..io.common import resolve_blacklists_dir
from ..models.domain import TemplateField
from ..models.io_types import RunPaths
from ..models.runtime_options import ApiClientOptions, FieldFetchOptions
from ..models.runtime_protocols import (
    ApiClientArgs,
    BootstrapRuntimeArgs,
    ClientFactoryLike,
    RunConfig,
)
from .bootstrap_fields import resolve_field_selection
from .bootstrap_resource_loading import (
    load_bootstrap_fields,
    load_bootstrap_supporting_resources,
)
from .bootstrap_types import BootstrapPaths, PreparedBootstrapResources, ResolvedCredentials

logger = logging.getLogger(__name__)


def run_path_value(run_paths: RunPaths | None, attr: str) -> str:
    """从 RunPaths 读取路径属性。"""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def resolve_bootstrap_paths(
    args: BootstrapRuntimeArgs,
    run_paths: RunPaths | None,
) -> BootstrapPaths:
    """Resolve all runtime-sensitive paths up front."""
    output_file = run_path_value(run_paths, "output") or str(args.output)
    return BootstrapPaths(
        output_file=output_file,
        log_file=run_path_value(run_paths, "log_file"),
        blacklists_dir=run_path_value(run_paths, "blacklists_dir") or str(resolve_blacklists_dir()),
        template_library_file=(
            run_path_value(run_paths, "template_library_file") or str(args.template_library_file)
        ),
        fields_cache_file=run_path_value(run_paths, "fields_cache_file") or str(args.fields_cache_file),
        feedback_output=run_path_value(run_paths, "feedback_output") or output_file,
        creds_file=run_path_value(run_paths, "creds_file") or str(args.creds_file),
        creds_key_file=run_path_value(run_paths, "creds_key_file") or str(args.creds_key_file),
    )


def build_effective_run_paths(
    args: BootstrapRuntimeArgs,
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
        blacklists_dir=paths.blacklists_dir,
        fields_cache_file=paths.fields_cache_file,
        template_library_file=paths.template_library_file,
        output=paths.output_file,
        feedback_output=paths.feedback_output,
        creds_file=paths.creds_file,
        creds_key_file=paths.creds_key_file,
        include_fields_file=str(args.include_fields_file or ""),
        exclude_fields_file=str(args.exclude_fields_file or ""),
        include_templates_file=str(args.include_templates_file or ""),
        exclude_templates_file=str(args.exclude_templates_file or ""),
    )


def prepare_runtime_outputs(
    args: BootstrapRuntimeArgs,
    run_paths: RunPaths | None,
    paths: BootstrapPaths,
    *,
    setup_runtime_logging_fn,
    cleanup_legacy_sidecar_files_fn,
    ensure_analysis_synced_fn,
    build_run_config_snapshot_fn,
) -> RunConfig:
    """Prepare logging/output side effects and capture the embedded run config."""
    effective_run_paths = build_effective_run_paths(args, paths, run_paths)
    if paths.log_file:
        setup_runtime_logging_fn(paths.log_file)
    cleanup_legacy_sidecar_files_fn(paths.output_file, verbose=True)
    ensure_analysis_synced_fn(paths.output_file)
    run_config = build_run_config_snapshot_fn(args, effective_run_paths)
    logger.info("[config] 运行配置将嵌入主结果文件")
    return run_config


def resolve_credentials(
    args: BootstrapRuntimeArgs,
    paths: BootstrapPaths,
    *,
    load_credentials_fn,
) -> tuple[str, str]:
    """Resolve credentials without mutating the runtime args object."""
    credentials_args = ResolvedCredentials(
        email=args.email,
        password=args.password,
        creds_file=paths.creds_file,
        creds_key_file=paths.creds_key_file,
    )
    email, password = load_credentials_fn(credentials_args)
    return str(email or ""), str(password or "")


def log_field_selection_stats(
    args: BootstrapRuntimeArgs,
    field_stats: dict[str, int],
    fields: list[TemplateField],
) -> None:
    """Emit field-filtering and ranking diagnostics."""
    top_fields_by_feedback, offset, limit = resolve_field_selection(args)
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
    if not fields:
        logger.error("[error] 数据集 %s 在字段过滤后没有可运行字段", args.dataset_id)
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
    logger.info("[data] 从数据集 %s 获取 %d 个字段", args.dataset_id, len(fields))


def prepare_bootstrap_resources(
    args: BootstrapRuntimeArgs,
    paths: BootstrapPaths,
    bootstrap_client: BrainClient,
    *,
    run_config: RunConfig,
    run_paths: RunPaths | None,
    set_active_blacklists_dir_fn,
    ensure_dataset_template_library_fn,
    ensure_template_blacklist_file_fn,
    load_template_library_fn,
    read_blacklist_payload_fn,
    summarize_blacklist_payload_fn,
    load_run_filters_extended_fn,
    get_dataset_expression_policy_fn,
    stable_fingerprint_fn,
    build_settings_fingerprint_fn,
    build_historical_run_state_fn,
    load_fields_cache_fn,
    fetch_fields_with_cache_fn,
    prepare_fields_for_execution_fn,
) -> PreparedBootstrapResources | None:
    """Load template, feedback, and field resources needed to build the run context."""
    dataset_id = str(args.dataset_id)
    effective_run_paths = build_effective_run_paths(args, paths, run_paths)
    supporting_resources = load_bootstrap_supporting_resources(
        dataset_id=dataset_id,
        paths=paths,
        effective_run_paths=effective_run_paths,
        set_active_blacklists_dir_fn=set_active_blacklists_dir_fn,
        ensure_dataset_template_library_fn=ensure_dataset_template_library_fn,
        ensure_template_blacklist_file_fn=ensure_template_blacklist_file_fn,
        load_template_library_fn=load_template_library_fn,
        read_blacklist_payload_fn=read_blacklist_payload_fn,
        summarize_blacklist_payload_fn=summarize_blacklist_payload_fn,
        load_run_filters_extended_fn=load_run_filters_extended_fn,
        get_dataset_expression_policy_fn=get_dataset_expression_policy_fn,
        build_historical_run_state_fn=build_historical_run_state_fn,
    )
    field_fetch_options = FieldFetchOptions.from_args(args)
    fields = load_bootstrap_fields(
        dataset_id=dataset_id,
        bootstrap_client=bootstrap_client,
        paths=paths,
        field_fetch_options=field_fetch_options,
        load_fields_cache_fn=load_fields_cache_fn,
        fetch_fields_with_cache_fn=fetch_fields_with_cache_fn,
    )
    if not fields:
        logger.error("[error] 数据集 %s 未返回任何字段", args.dataset_id)
        return None

    prepared_fields, field_stats = prepare_fields_for_execution_fn(
        list(fields),
        filters_dict=supporting_resources.filters,
        expression_policy=supporting_resources.expression_policy,
        historical_state=supporting_resources.historical_state,
        args=args,
    )
    log_field_selection_stats(args, field_stats, prepared_fields)
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
        template_library_fingerprint=stable_fingerprint_fn(supporting_resources.template_library),
        settings_fingerprint=build_settings_fingerprint_fn(args),
        historical_state=supporting_resources.historical_state,
        fields=prepared_fields,
        run_config=run_config,
    )


def create_and_login_client(
    email: str,
    password: str,
    args: ApiClientArgs,
    *,
    get_runtime_config_fn,
    login_with_retry_fn,
) -> tuple[BrainClient, ClientFactoryLike]:
    """创建 Brain API 客户端并完成登录，同时创建工作线程客户端工厂。"""
    client_options = ApiClientOptions.from_args(args)
    http_backend = get_runtime_config_fn().http.backend
    bootstrap_client = BrainClient(
        email,
        password,
        min_request_interval=client_options.min_request_interval,
        rate_limit_max_retries=client_options.rate_limit_max_retries,
        http_backend=http_backend,
    )
    login_with_retry_fn(bootstrap_client, client_options.login_retries)
    client_factory = WorkerClientFactory(
        client_options,
        email,
        password,
        http_backend=http_backend,
    )
    return bootstrap_client, client_factory
