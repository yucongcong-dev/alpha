"""
启动与初始化编排模块。

本模块承接主入口中的前置阶段逻辑，包括：
- 字段过滤与优先级排序
- 运行产物清理
- 客户端创建与登录
- 运行上下文初始化
"""

from __future__ import annotations

import argparse
from datetime import date
import logging
from math import log1p
from pathlib import Path
import shutil
import threading
from typing import Any

from .analysis.feedback import build_historical_run_state
from .analysis.stats import (
    field_priority,
    is_queue_timeout_result,
)
from .api.client import BrainClient, WorkerClientFactory, login_with_retry
from .cli.parser import (
    PROJECT_ROOT,
    build_run_config_snapshot,
    load_run_filters_extended,
    setup_runtime_logging,
)
from .config import (
    DatasetExpressionPolicy,
    SENTINEL_UNKNOWN,
    STATS_DEFAULT_SCORE,
    get_dataset_expression_policy,
)
from .generators.fields import fetch_fields_with_cache, load_fields_cache
from .generators.settings import build_settings_fingerprint, stable_fingerprint
from .generators.templates import ensure_dataset_template_library, load_template_library
from .io.credentials import load_credentials
from .io.output import (
    build_blacklist_runtime_stats,
    cleanup_legacy_sidecar_files,
    dump_results_incremental,
    ensure_analysis_synced,
    ensure_template_blacklist_file,
    initialize_results_journal,
    load_blacklisted_template_names,
)
from .models.base import (
    ExecutionState,
    HistoricalRunState,
    InitializedRunContext,
    RunFilters,
    RuntimeConcurrencyState,
)
from .utils.helpers import choose_field_name, first_non_empty, is_event_field_name

logger = logging.getLogger(__name__)


def _safe_int(value: Any) -> int:
    """宽松地把字段元数据转为 int，失败时返回 0。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    """宽松地把字段元数据转为 float，失败时返回 0.0。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_date_ordinal(value: Any) -> int:
    """把 YYYY-MM-DD 形式的日期字符串转换为 ordinal，失败时返回 0。"""
    if not value:
        return 0
    try:
        return date.fromisoformat(str(value)).toordinal()
    except (TypeError, ValueError):
        return 0


def populate_execution_metrics(execution_state: ExecutionState) -> None:
    """根据当前结果列表回填增量持久化所需的轻量计数。"""
    execution_state.unique_field_ids = {result.field_id for result in execution_state.results}
    execution_state.submittable_count = sum(
        1 for result in execution_state.results if result.submittable
    )
    execution_state.submitted_count = sum(1 for result in execution_state.results if result.submitted)
    execution_state.error_count = sum(1 for result in execution_state.results if result.status == "error")
    execution_state.queue_timeout_count = sum(
        1 for result in execution_state.results if is_queue_timeout_result(result)
    )


def _normalize_range(values: list[float]) -> list[float]:
    """对一组数做 min-max 归一化；常数列返回全 0。"""
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high <= low:
        return [0.0 for _ in values]
    span = high - low
    return [(value - low) / span for value in values]


def prepare_fields_for_execution(
    fields: list[dict[str, Any]],
    *,
    filters_dict: RunFilters,
    expression_policy: DatasetExpressionPolicy,
    historical_state: HistoricalRunState,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """对字段做过滤、排序并最终应用 offset/limit。"""
    cached_field_count = len(fields)
    filtered_fields: list[dict[str, Any]] = []
    prefiltered_count = 0
    low_coverage_count = 0
    low_date_coverage_count = 0
    low_alpha_count = 0
    low_user_count = 0

    for field in fields:
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        field_name = choose_field_name(field)
        is_event_field = is_event_field_name(field_name, expression_policy.event_field_prefixes)
        min_coverage = (
            expression_policy.event_field_min_coverage
            if is_event_field and expression_policy.event_field_min_coverage > 0
            else expression_policy.field_min_coverage
        )
        min_date_coverage = (
            expression_policy.event_field_min_date_coverage
            if is_event_field and expression_policy.event_field_min_date_coverage > 0
            else expression_policy.field_min_date_coverage
        )
        min_alpha_count = (
            expression_policy.event_field_min_alpha_count
            if is_event_field and expression_policy.event_field_min_alpha_count > 0
            else expression_policy.field_min_alpha_count
        )
        min_user_count = (
            expression_policy.event_field_min_user_count
            if is_event_field and expression_policy.event_field_min_user_count > 0
            else expression_policy.field_min_user_count
        )
        if (
            filters_dict.include_fields
            and field_id not in filters_dict.include_fields
            and field_name not in filters_dict.include_fields
        ):
            prefiltered_count += 1
            continue
        if field_id in filters_dict.exclude_fields or field_name in filters_dict.exclude_fields:
            prefiltered_count += 1
            continue
        if _safe_float(field.get("coverage")) < min_coverage:
            low_coverage_count += 1
            continue
        if _safe_float(field.get("dateCoverage")) < min_date_coverage:
            low_date_coverage_count += 1
            continue
        if _safe_int(field.get("alphaCount")) < min_alpha_count:
            low_alpha_count += 1
            continue
        if _safe_int(field.get("userCount")) < min_user_count:
            low_user_count += 1
            continue
        filtered_fields.append(field)

    fields = filtered_fields
    if not fields:
        return [], {
            "cached_field_count": cached_field_count,
            "filtered_field_count": 0,
            "ranked_field_count": 0,
            "prefiltered_count": prefiltered_count,
            "low_coverage_count": low_coverage_count,
            "low_date_coverage_count": low_date_coverage_count,
            "low_alpha_count": low_alpha_count,
            "low_user_count": low_user_count,
        }

    coverage_values = [_safe_float(field.get("coverage")) for field in fields]
    date_coverage_values = [_safe_float(field.get("dateCoverage")) for field in fields]
    alpha_validation_values = [log1p(_safe_int(field.get("alphaCount"))) for field in fields]
    user_validation_values = [log1p(_safe_int(field.get("userCount"))) for field in fields]
    recency_values = [_safe_date_ordinal(field.get("dateCreated")) for field in fields]
    theme_values = [float(len(field.get("themes") or [])) for field in fields]

    norm_coverage_values = _normalize_range(coverage_values)
    norm_date_coverage_values = _normalize_range(date_coverage_values)
    norm_alpha_validation_values = _normalize_range(alpha_validation_values)
    norm_user_validation_values = _normalize_range(user_validation_values)
    norm_recency_values = _normalize_range([float(value) for value in recency_values])
    norm_theme_values = _normalize_range(theme_values)

    field_metadata_scores: dict[str, float] = {}
    for idx, field in enumerate(fields):
        field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
        validation_score = (
            expression_policy.field_coverage_weight * norm_coverage_values[idx]
            + expression_policy.field_date_coverage_weight * norm_date_coverage_values[idx]
            + expression_policy.field_alpha_validation_weight * norm_alpha_validation_values[idx]
            + expression_policy.field_user_validation_weight * norm_user_validation_values[idx]
            + expression_policy.field_recency_weight * norm_recency_values[idx]
            + expression_policy.field_theme_bonus_weight * norm_theme_values[idx]
        )
        crowding_penalty = (
            expression_policy.field_alpha_crowding_penalty_weight * norm_alpha_validation_values[idx]
            + expression_policy.field_user_crowding_penalty_weight * norm_user_validation_values[idx]
        )
        field_metadata_scores[field_id] = validation_score - crowding_penalty

    def field_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        field_id = str(first_non_empty(item.get("id"), SENTINEL_UNKNOWN))
        field_name = choose_field_name(item)
        feedback = historical_state.field_feedback.get(field_id)
        priority = field_priority(field_id, historical_state.field_feedback)
        is_promising_seen = (
            feedback is not None and priority >= expression_policy.promising_field_min_priority
        )
        is_unexplored = feedback is None
        preferred_rank = expression_policy.preferred_field_order.get(field_name, 999)
        is_preferred_direction = preferred_rank < 999
        is_overtested_weak = (
            field_name in expression_policy.overtested_weak_fields and feedback is not None
        )
        metadata_score = field_metadata_scores.get(field_id, 0.0)
        effective_priority = priority
        if is_unexplored:
            effective_priority = min(
                expression_policy.promising_field_min_priority - 0.01,
                max(
                    metadata_score
                    + (
                        expression_policy.field_preferred_unexplored_bonus
                        if is_preferred_direction
                        else 0.0
                    ),
                    STATS_DEFAULT_SCORE,
                ),
            )
        elif priority > STATS_DEFAULT_SCORE:
            effective_priority = priority + metadata_score
        return (
            -int(is_promising_seen),
            int(is_overtested_weak),
            -effective_priority,
            -int(is_preferred_direction),
            preferred_rank,
            -int(is_unexplored),
            -metadata_score,
            -_safe_float(item.get("coverage")),
            -_safe_float(item.get("dateCoverage")),
            field_name,
        )

    fields.sort(key=field_sort_key)
    if args.top_fields_by_feedback > 0:
        focused_fields = [
            field
            for field in fields
            if field_priority(
                str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
                historical_state.field_feedback,
            )
            > -999.0
        ]
        fields = focused_fields[: args.top_fields_by_feedback]

    ranked_field_count = len(fields)
    if args.offset > 0:
        fields = fields[args.offset :]
    if args.limit > 0:
        fields = fields[: args.limit]

    return fields, {
        "cached_field_count": cached_field_count,
        "filtered_field_count": len(filtered_fields),
        "ranked_field_count": ranked_field_count,
        "prefiltered_count": prefiltered_count,
        "low_coverage_count": low_coverage_count,
        "low_date_coverage_count": low_date_coverage_count,
        "low_alpha_count": low_alpha_count,
        "low_user_count": low_user_count,
    }


def clean_runtime_artifacts(
    args: argparse.Namespace,
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
    email: str, password: str, args: argparse.Namespace
) -> tuple[BrainClient, WorkerClientFactory]:
    """创建 Brain API 客户端并完成登录，同时创建工作线程客户端工厂。"""
    bootstrap_client = BrainClient(
        email,
        password,
        min_request_interval=args.min_request_interval,
        rate_limit_max_retries=args.rate_limit_max_retries,
    )
    login_with_retry(bootstrap_client, args.login_retries)
    client_factory = WorkerClientFactory(args, email, password)
    return bootstrap_client, client_factory


def initialize_run_context(
    args: argparse.Namespace,
    run_paths: Any,
) -> InitializedRunContext | None:
    """执行主流程的初始化阶段，返回结构化运行上下文。"""
    output_file = getattr(run_paths, "output", None) or args.output
    log_file = getattr(run_paths, "log_file", None)
    if log_file:
        setup_runtime_logging(log_file)

    cleanup_legacy_sidecar_files(output_file, verbose=True)
    ensure_analysis_synced(output_file)

    run_config = build_run_config_snapshot(args, run_paths)
    logger.info("[config] 运行配置将嵌入主结果文件")

    template_library_file = (
        getattr(run_paths, "template_library_file", None) or args.template_library_file
    )
    template_library_file = ensure_dataset_template_library(template_library_file, args.dataset_id)
    ensure_template_blacklist_file(args.dataset_id)

    email, password = load_credentials(args)
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
    feedback_output = getattr(run_paths, "feedback_output", None) or output_file
    historical_state = build_historical_run_state(output_file, feedback_output)

    fields_cache_file = args.fields_cache_file
    cached_fields = load_fields_cache(
        fields_cache_file,
        dataset_id=args.dataset_id,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
    )
    fields = fetch_fields_with_cache(
        bootstrap_client,
        args,
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

    execution_state = ExecutionState(
        results=list(historical_state.existing_results),
        attempted_keys=set(historical_state.attempted_keys),
        template_stats=dict(historical_state.template_stats),
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )
    populate_execution_metrics(execution_state)
    execution_state.persisted_result_count = initialize_results_journal(
        output_file,
        execution_state.results,
    )
    execution_state.blacklist_runtime_stats = build_blacklist_runtime_stats(
        execution_state.results,
    )
    execution_state.blacklisted_template_names = load_blacklisted_template_names(args.dataset_id)
    execution_state.persisted_result_count = dump_results_incremental(
        output_file,
        args.dataset_id,
        [],
        persisted_result_count=execution_state.persisted_result_count,
        tested=len(execution_state.results),
        unique_fields_tested=len(execution_state.unique_field_ids),
        submittable_count=execution_state.submittable_count,
        submitted_count=execution_state.submitted_count,
        error_count=execution_state.error_count,
        queue_timeout_count=execution_state.queue_timeout_count,
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
