"""Bootstrap step implementations behind the compatibility facade."""

from __future__ import annotations

import logging
from typing import cast

from ..api.client import BrainClient, WorkerClientFactory
from ..config.models import DatasetExpressionPolicy
from ..models.domain import TemplateField, TemplateLibrary
from ..models.io_types import RunFilters, RunPaths
from ..models.runtime_options import ApiClientOptions, FieldFetchOptions
from ..models.runtime_protocols import (
    ApiClientArgs,
    BootstrapRuntimeArgs,
    ClientFactoryLike,
    CredentialsArgs,
    SimulationSettingsArgs,
)
from ..runtime import HistoricalRunState
from .bootstrap_types import BootstrapPaths, PreparedBootstrapResources, ResolvedCredentials

logger = logging.getLogger(__name__)


def count_template_library_items(template_library: TemplateLibrary) -> int:
    """Count concrete template entries across all field-type buckets."""
    return sum(len(items) for items in template_library.values())


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
        template_library_file=(
            run_path_value(run_paths, "template_library_file") or str(args.template_library_file)
        ),
        fields_cache_file=run_path_value(run_paths, "fields_cache_file") or str(args.fields_cache_file),
        feedback_output=run_path_value(run_paths, "feedback_output") or output_file,
        creds_file=run_path_value(run_paths, "creds_file") or str(args.creds_file),
        creds_key_file=run_path_value(run_paths, "creds_key_file") or str(args.creds_key_file),
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
) -> dict[str, object]:
    """Prepare logging/output side effects and capture the embedded run config."""
    if paths.log_file:
        setup_runtime_logging_fn(paths.log_file)
    cleanup_legacy_sidecar_files_fn(paths.output_file, verbose=True)
    ensure_analysis_synced_fn(paths.output_file)
    run_config = build_run_config_snapshot_fn(args, cast(RunPaths, run_paths))
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
        email=getattr(args, "email", None),
        password=getattr(args, "password", None),
        creds_file=paths.creds_file,
        creds_key_file=paths.creds_key_file,
    )
    return cast(tuple[str, str], load_credentials_fn(cast(CredentialsArgs, credentials_args)))


def log_field_selection_stats(
    args: BootstrapRuntimeArgs,
    field_stats: dict[str, int],
    fields: list[TemplateField],
) -> None:
    """Emit field-filtering and ranking diagnostics."""
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
    if cast(int, args.top_fields_by_feedback) > 0:
        logger.info("[focus] 限制运行到按反馈排序的前 %d 个字段", len(fields))
    logger.info(
        "[data] 当前上下文缓存共 %d 个字段，过滤后共 %d 个字段，优先级排序后共 %d 个字段，本次按 offset=%d limit=%d 取 %d 个字段",
        field_stats["cached_field_count"],
        field_stats["filtered_field_count"],
        field_stats["ranked_field_count"],
        args.offset,
        args.limit,
        len(fields),
    )
    logger.info("[data] 从数据集 %s 获取 %d 个字段", args.dataset_id, len(fields))


def prepare_bootstrap_resources(
    args: BootstrapRuntimeArgs,
    paths: BootstrapPaths,
    bootstrap_client: BrainClient,
    *,
    run_config: dict[str, object],
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
    dataset_id = cast(str, args.dataset_id)
    set_active_blacklists_dir_fn()
    template_library_file = ensure_dataset_template_library_fn(paths.template_library_file, dataset_id)
    blacklist_path = ensure_template_blacklist_file_fn(dataset_id)

    template_library = cast(TemplateLibrary, load_template_library_fn(template_library_file))
    logger.info(
        "[templates] dataset=%s library=%s entries=%d",
        dataset_id,
        template_library_file,
        count_template_library_items(template_library),
    )
    blacklist_payload = read_blacklist_payload_fn(dataset_id)
    learned_count, rule_count = summarize_blacklist_payload_fn(blacklist_payload)
    logger.info(
        "[blacklist] dataset=%s file=%s learned_templates=%d expression_rules=%d",
        dataset_id,
        blacklist_path,
        learned_count,
        rule_count,
    )
    filters_dict = cast(RunFilters, load_run_filters_extended_fn(cast(RunPaths, run_paths)))
    expression_policy = cast(
        DatasetExpressionPolicy,
        get_dataset_expression_policy_fn(dataset_id),
    )
    historical_state = cast(
        HistoricalRunState,
        build_historical_run_state_fn(paths.output_file, paths.feedback_output),
    )
    cached_fields = load_fields_cache_fn(
        paths.fields_cache_file,
        dataset_id=dataset_id,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
    )
    field_fetch_options = FieldFetchOptions.from_args(args)
    fields = fetch_fields_with_cache_fn(
        cast(object, bootstrap_client),
        field_fetch_options,
        paths.fields_cache_file,
        cached_fields,
    )
    if not fields:
        logger.error("[error] 数据集 %s 未返回任何字段", args.dataset_id)
        return None

    prepared_fields, field_stats = prepare_fields_for_execution_fn(
        list(fields),
        filters_dict=filters_dict,
        expression_policy=expression_policy,
        historical_state=historical_state,
        args=args,
    )
    prepared_fields = cast(list[TemplateField], prepared_fields)
    log_field_selection_stats(args, field_stats, prepared_fields)
    if not prepared_fields:
        return None
    if historical_state.existing_results:
        logger.info(
            "[resume] 从 %s 加载 %d 个历史结果",
            paths.output_file,
            len(historical_state.existing_results),
        )

    return PreparedBootstrapResources(
        template_library=template_library,
        filters=filters_dict,
        expression_policy=expression_policy,
        use_dataset_heuristics=expression_policy.use_curated_heuristics,
        template_library_fingerprint=stable_fingerprint_fn(template_library),
        settings_fingerprint=build_settings_fingerprint_fn(args),
        historical_state=historical_state,
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
    return bootstrap_client, cast(ClientFactoryLike, client_factory)
