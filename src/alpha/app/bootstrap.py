"""
启动与初始化编排模块。

本模块承接主入口中的前置阶段逻辑，包括：
- 字段过滤与优先级排序
- 运行产物清理
- 客户端创建与登录
- 运行上下文初始化
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import threading
from typing import cast

from ..analysis.feedback_history import build_historical_run_state
from ..api.client import BrainClient, WorkerClientFactory, login_with_retry
from ..cli.filters import load_run_filters_extended, setup_runtime_logging
from ..cli.run_config import build_run_config_snapshot
from ..config.models import DatasetExpressionPolicy
from ..generators.fields import DatasetFieldClient, fetch_fields_with_cache, load_fields_cache
from ..generators.fingerprint import stable_fingerprint
from ..generators.payload import build_settings_fingerprint
from ..generators.templates import ensure_dataset_template_library, load_template_library
from ..analysis.analysis_sync import ensure_analysis_synced
from ..io.credentials import load_credentials
from ..io.output_paths import cleanup_legacy_sidecar_files
from ..models.domain import TemplateField, TemplateLibrary
from ..models.io_types import RunFilters, RunPaths
from ..models.runtime import (
    ApiClientArgs,
    ApiClientOptions,
    BootstrapRuntimeArgs,
    ClientFactoryLike,
    CredentialsArgs,
    FieldFetchOptions,
    HistoricalRunState,
    InitializedRunContext,
    RuntimeConcurrencyState,
    SimulationSettingsArgs,
)
from ..policy import ensure_template_blacklist_file
from ..policy.blacklist_context import set_active_blacklists_dir
from ..policy.blacklist_store import read_blacklist_payload, summarize_blacklist_payload
from ..policy.expression import get_dataset_expression_policy
from .bootstrap_cleanup import clean_runtime_artifacts as clean_runtime_artifacts
from .bootstrap_fields import prepare_fields_for_execution
from .bootstrap_state import build_execution_state

logger = logging.getLogger(__name__)


def _count_template_library_items(template_library: TemplateLibrary) -> int:
    """Count concrete template entries across all field-type buckets."""
    return sum(len(items) for items in template_library.values())


@dataclass(frozen=True)
class ResolvedCredentials:
    """凭证加载所需的最小只读输入。"""

    email: object
    password: object
    creds_file: object
    creds_key_file: object


@dataclass(frozen=True)
class BootstrapPaths:
    """初始化阶段使用的归一化路径快照。"""

    output_file: str
    log_file: str
    template_library_file: str
    fields_cache_file: str
    feedback_output: str
    creds_file: str
    creds_key_file: str


@dataclass(frozen=True)
class PreparedBootstrapResources:
    """模板、过滤器、反馈和字段等初始化资源集合。"""

    template_library: object
    filters: object
    expression_policy: object
    use_dataset_heuristics: bool
    template_library_fingerprint: str
    settings_fingerprint: str
    historical_state: object
    fields: list[TemplateField]
    run_config: dict[str, object]


def _run_path_value(run_paths: RunPaths | None, attr: str) -> str:
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
    output_file = _run_path_value(run_paths, "output") or str(args.output)
    return BootstrapPaths(
        output_file=output_file,
        log_file=_run_path_value(run_paths, "log_file"),
        template_library_file=(
            _run_path_value(run_paths, "template_library_file") or str(args.template_library_file)
        ),
        fields_cache_file=_run_path_value(run_paths, "fields_cache_file") or str(args.fields_cache_file),
        feedback_output=_run_path_value(run_paths, "feedback_output") or output_file,
        creds_file=_run_path_value(run_paths, "creds_file") or str(args.creds_file),
        creds_key_file=_run_path_value(run_paths, "creds_key_file") or str(args.creds_key_file),
    )


def prepare_runtime_outputs(
    args: BootstrapRuntimeArgs,
    run_paths: RunPaths | None,
    paths: BootstrapPaths,
) -> dict[str, object]:
    """Prepare logging/output side effects and capture the embedded run config."""
    if paths.log_file:
        setup_runtime_logging(paths.log_file)
    cleanup_legacy_sidecar_files(paths.output_file, verbose=True)
    ensure_analysis_synced(paths.output_file)
    run_config = build_run_config_snapshot(args, cast(RunPaths, run_paths))
    logger.info("[config] 运行配置将嵌入主结果文件")
    return run_config


def resolve_credentials(
    args: BootstrapRuntimeArgs,
    paths: BootstrapPaths,
) -> tuple[str, str]:
    """Resolve credentials without mutating the runtime args object."""
    credentials_args = ResolvedCredentials(
        email=getattr(args, "email", None),
        password=getattr(args, "password", None),
        creds_file=paths.creds_file,
        creds_key_file=paths.creds_key_file,
    )
    return cast(tuple[str, str], load_credentials(cast(CredentialsArgs, credentials_args)))


def prepare_bootstrap_resources(
    args: BootstrapRuntimeArgs,
    paths: BootstrapPaths,
    bootstrap_client: BrainClient,
    *,
    run_config: dict[str, object],
    run_paths: RunPaths | None,
) -> PreparedBootstrapResources | None:
    """Load template, feedback, and field resources needed to build the run context."""
    dataset_id = cast(str, args.dataset_id)
    set_active_blacklists_dir()
    template_library_file = ensure_dataset_template_library(paths.template_library_file, dataset_id)
    blacklist_path = ensure_template_blacklist_file(dataset_id)

    template_library = load_template_library(template_library_file)
    logger.info(
        "[templates] dataset=%s library=%s entries=%d",
        dataset_id,
        template_library_file,
        _count_template_library_items(cast(TemplateLibrary, template_library)),
    )
    blacklist_payload = read_blacklist_payload(dataset_id)
    learned_count, rule_count = summarize_blacklist_payload(blacklist_payload)
    logger.info(
        "[blacklist] dataset=%s file=%s learned_templates=%d expression_rules=%d",
        dataset_id,
        blacklist_path,
        learned_count,
        rule_count,
    )
    filters_dict = load_run_filters_extended(cast(RunPaths, run_paths))
    expression_policy = get_dataset_expression_policy(dataset_id)
    use_dataset_heuristics = expression_policy.use_curated_heuristics
    template_library_fingerprint = stable_fingerprint(template_library)
    settings_fingerprint = build_settings_fingerprint(cast(SimulationSettingsArgs, args))
    historical_state = build_historical_run_state(paths.output_file, paths.feedback_output)

    cached_fields = load_fields_cache(
        paths.fields_cache_file,
        dataset_id=dataset_id,
        region=cast(str, args.region),
        universe=cast(str, args.universe),
        instrument_type=cast(str, args.instrument_type),
        delay=cast(int, args.delay),
    )
    field_fetch_options = FieldFetchOptions.from_args(args)
    fields = fetch_fields_with_cache(
        cast(DatasetFieldClient, bootstrap_client),
        field_fetch_options,
        paths.fields_cache_file,
        cached_fields,
    )
    if not fields:
        logger.error("[error] 数据集 %s 未返回任何字段", args.dataset_id)
        return None

    prepared_fields, field_stats = prepare_fields_for_execution(
        list(fields),
        filters_dict=filters_dict,
        expression_policy=expression_policy,
        historical_state=historical_state,
        args=args,
    )
    _log_field_selection_stats(args, field_stats, prepared_fields)
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
        use_dataset_heuristics=use_dataset_heuristics,
        template_library_fingerprint=template_library_fingerprint,
        settings_fingerprint=settings_fingerprint,
        historical_state=historical_state,
        fields=prepared_fields,
        run_config=run_config,
    )


def _log_field_selection_stats(
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
    if not fields:
        logger.error(
            "[error] 数据集 %s 在优先级排序后 offset=%d limit=%d 下没有可运行字段",
            args.dataset_id,
            args.offset,
            args.limit,
        )
        return
    logger.info("[data] 从数据集 %s 获取 %d 个字段", args.dataset_id, len(fields))


def create_and_login_client(
    email: str, password: str, args: ApiClientArgs
) -> tuple[BrainClient, WorkerClientFactory]:
    """创建 Brain API 客户端并完成登录，同时创建工作线程客户端工厂。"""
    from ..config.getters import get_http_backend

    client_options = ApiClientOptions.from_args(args)
    http_backend = get_http_backend()
    bootstrap_client = BrainClient(
        email,
        password,
        min_request_interval=client_options.min_request_interval,
        rate_limit_max_retries=client_options.rate_limit_max_retries,
        http_backend=http_backend,
    )
    login_with_retry(bootstrap_client, client_options.login_retries)
    client_factory = WorkerClientFactory(client_options, email, password, http_backend=http_backend)
    return bootstrap_client, client_factory


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
        template_library=cast(TemplateLibrary, prepared.template_library),
        filters=cast(RunFilters, prepared.filters),
        expression_policy=cast(DatasetExpressionPolicy, prepared.expression_policy),
        use_dataset_heuristics=prepared.use_dataset_heuristics,
        template_library_fingerprint=prepared.template_library_fingerprint,
        settings_fingerprint=prepared.settings_fingerprint,
        historical_state=cast(HistoricalRunState, prepared.historical_state),
        fields=prepared.fields,
        execution_state=execution_state,
        runtime_state=runtime_state,
        create_semaphore=create_semaphore,
        run_config=prepared.run_config,
    )
