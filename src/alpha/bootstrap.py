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
from pathlib import Path
import shutil
import threading

from .analysis.feedback import build_historical_run_state
from .api.client import BrainClient, WorkerClientFactory, login_with_retry
from .bootstrap_fields import prepare_fields_for_execution
from .bootstrap_state import build_execution_state
from .cli.constants import PROJECT_ROOT
from .cli.filters import load_run_filters_extended, setup_runtime_logging
from .cli.run_config import build_run_config_snapshot
from .config.policy import get_dataset_expression_policy
from .generators.fields import fetch_fields_with_cache, load_fields_cache
from .generators.settings import build_settings_fingerprint, stable_fingerprint
from .generators.templates import ensure_dataset_template_library, load_template_library
from .io.analysis_sync import ensure_analysis_synced
from .io.credentials import load_credentials
from .io.output_paths import cleanup_legacy_sidecar_files
from .models.io_types import RunPaths
from .models.runtime import (
    ApiClientArgs,
    ApiClientOptions,
    BootstrapRuntimeArgs,
    CleanRuntimeArgs,
    FieldFetchOptions,
    InitializedRunContext,
    RuntimeConcurrencyState,
)
from .policy import ensure_template_blacklist_file

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedCredentials:
    """凭证加载所需的最小只读输入。"""

    email: object
    password: object
    creds_file: object
    creds_key_file: object


def _run_path_value(run_paths: object | None, attr: str) -> str:
    """兼容 RunPaths 与历史 attr-style 对象的路径读取。"""
    if run_paths is None:
        return ""
    value = getattr(run_paths, attr, "")
    return str(value or "")


def clean_runtime_artifacts(
    args: CleanRuntimeArgs,
    *,
    project_root: Path = PROJECT_ROOT,
) -> int:
    """清理本地运行产物，默认保留加密凭据。"""
    targets: list[Path] = [
        project_root / "cache",
        project_root / "results",
        project_root / ".pytest_cache",
        project_root / ".mypy_cache",
        project_root / ".ruff_cache",
        project_root / ".coverage",
        project_root / "htmlcov",
    ]
    if args.include_credentials:
        targets.append(project_root / ".credentials")

    existing_targets = [target for target in targets if target.exists()]
    if not existing_targets:
        print("[clean] no runtime artifacts found")
        return 0

    for target in existing_targets:
        if args.dry_run_clean:
            print(f"[clean] would remove {target}")
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        print(f"[clean] removed {target}")

    if not args.include_credentials:
        print("[clean] credentials preserved (.credentials/)")
    return 0


def create_and_login_client(
    email: str, password: str, args: ApiClientArgs
) -> tuple[BrainClient, WorkerClientFactory]:
    """创建 Brain API 客户端并完成登录，同时创建工作线程客户端工厂。"""
    client_options = ApiClientOptions.from_args(args)
    bootstrap_client = BrainClient(
        email,
        password,
        min_request_interval=client_options.min_request_interval,
        rate_limit_max_retries=client_options.rate_limit_max_retries,
    )
    login_with_retry(bootstrap_client, client_options.login_retries)
    client_factory = WorkerClientFactory(client_options, email, password)
    return bootstrap_client, client_factory


def initialize_run_context(
    args: BootstrapRuntimeArgs,
    run_paths: RunPaths | object | None,
) -> InitializedRunContext | None:
    """执行主流程的初始化阶段，返回结构化运行上下文。"""
    output_file = _run_path_value(run_paths, "output") or args.output
    log_file = _run_path_value(run_paths, "log_file")
    if log_file:
        setup_runtime_logging(log_file)

    cleanup_legacy_sidecar_files(output_file, verbose=True)
    ensure_analysis_synced(output_file)

    run_config = build_run_config_snapshot(args, run_paths)
    logger.info("[config] 运行配置将嵌入主结果文件")

    template_library_file = (
        _run_path_value(run_paths, "template_library_file") or args.template_library_file
    )
    template_library_file = ensure_dataset_template_library(template_library_file, args.dataset_id)
    ensure_template_blacklist_file(args.dataset_id)

    creds_file = _run_path_value(run_paths, "creds_file") or args.creds_file
    creds_key_file = _run_path_value(run_paths, "creds_key_file") or args.creds_key_file
    if hasattr(args, "creds_file"):
        args.creds_file = creds_file
    if hasattr(args, "creds_key_file"):
        args.creds_key_file = creds_key_file
    credentials_args = ResolvedCredentials(
        email=getattr(args, "email", None),
        password=getattr(args, "password", None),
        creds_file=creds_file,
        creds_key_file=creds_key_file,
    )
    email, password = load_credentials(credentials_args)
    if not email or not password:
        logger.error("[error] 缺少凭证，无法继续")
        return None

    bootstrap_client, client_factory = create_and_login_client(email, password, args)

    template_library = load_template_library(template_library_file)
    filters_dict = load_run_filters_extended(run_paths)
    expression_policy = get_dataset_expression_policy(args.dataset_id)
    use_dataset_heuristics = expression_policy.use_curated_heuristics
    template_library_fingerprint = stable_fingerprint(template_library)
    settings_fingerprint = build_settings_fingerprint(args)
    feedback_output = _run_path_value(run_paths, "feedback_output") or output_file
    historical_state = build_historical_run_state(output_file, feedback_output)

    fields_cache_file = _run_path_value(run_paths, "fields_cache_file") or args.fields_cache_file
    cached_fields = load_fields_cache(
        fields_cache_file,
        dataset_id=args.dataset_id,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
    )
    field_fetch_options = FieldFetchOptions.from_args(args)
    fields = fetch_fields_with_cache(
        bootstrap_client,
        field_fetch_options,
        fields_cache_file,
        cached_fields,
    )
    if not fields:
        logger.error("[error] 数据集 %s 未返回任何字段", args.dataset_id)
        return None

    fields, field_stats = prepare_fields_for_execution(
        list(fields),
        filters_dict=filters_dict,
        expression_policy=expression_policy,
        historical_state=historical_state,
        args=args,
    )
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
    )
    if metadata_filtered_count > 0:
        logger.info(
            "[filter] 排序前因官网字段指标过滤 %d 个字段 (coverage=%d, dateCoverage=%d, alphaCount=%d, userCount=%d)",
            metadata_filtered_count,
            field_stats["low_coverage_count"],
            field_stats["low_date_coverage_count"],
            field_stats["low_alpha_count"],
            field_stats["low_user_count"],
        )
    if not fields:
        logger.error("[error] 数据集 %s 在字段过滤后没有可运行字段", args.dataset_id)
        return None
    if args.top_fields_by_feedback > 0:
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
        return None

    logger.info("[data] 从数据集 %s 获取 %d 个字段", args.dataset_id, len(fields))

    if historical_state.existing_results:
        logger.info(
            "[resume] 从 %s 加载 %d 个历史结果",
            output_file,
            len(historical_state.existing_results),
        )

    execution_state = build_execution_state(
        dataset_id=args.dataset_id,
        output_file=output_file,
        historical_state=historical_state,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        run_config=run_config,
    )

    max_workers = max(1, args.max_concurrent_simulations)
    runtime_state = RuntimeConcurrencyState(
        max_workers=max_workers,
        runtime_max_workers=max_workers,
    )
    max_create_workers = max(1, args.max_concurrent_creates)
    create_semaphore = threading.Semaphore(max_create_workers)

    logger.info("[config] max_concurrent_simulations=%d", max_workers)
    logger.info("[config] max_concurrent_creates=%d", max_create_workers)
    logger.info("[config] simulation_max_pending_cycles=%d", args.simulation_max_pending_cycles)

    return InitializedRunContext(
        client_factory=client_factory,
        template_library=template_library,
        filters=filters_dict,
        expression_policy=expression_policy,
        use_dataset_heuristics=use_dataset_heuristics,
        template_library_fingerprint=template_library_fingerprint,
        settings_fingerprint=settings_fingerprint,
        historical_state=historical_state,
        fields=fields,
        execution_state=execution_state,
        runtime_state=runtime_state,
        create_semaphore=create_semaphore,
        run_config=run_config,
    )
