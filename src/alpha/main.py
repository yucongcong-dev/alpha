"""
主入口模块

本模块是 Alpha 测试系统的主入口点，负责编排整个测试流程，
包括凭证加载、客户端创建、字段获取、模板测试和结果持久化。

模块内容：
    - create_and_login_client(email, password, args) -> Tuple[BrainClient, WorkerClientFactory]: 创建并登录客户端
    - main() -> int: 主入口函数
    1. 解析命令行参数
    2. 加载凭证
    3. 创建并登录客户端
    4. 加载模板库和过滤器
    5. 获取字段列表（带缓存）
    6. 构建历史运行状态
    7. 启动多线程执行器
    8. 遍历字段和模板组合
    9. 调用 run_field_test_in_worker
    10. 处理完成的任务
    11. 保存结果
    12. 打印汇总统计
"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date
import logging
from math import log1p
from pathlib import Path
import shutil
import threading
import time
from typing import Any

# 导入历史迭代优化
from .analysis.feedback import (
    build_historical_run_state,
    should_stop_after_submittable,
)

# 导入分析模块
from .analysis.stats import (
    current_submittable_count,
    field_priority,
)

# 导入 API 客户端
from .api.client import (
    BrainClient,
    WorkerClientFactory,
    login_with_retry,
)

# 导入 CLI 模块
from .cli.parser import (
    build_run_config_snapshot,
    load_run_filters_extended,
    normalize_args_paths,
    parse_args,
    PROJECT_ROOT,
    setup_runtime_logging,
)

# 导入配置和模型
from .config import (
    SENTINEL_UNKNOWN,
    STATS_DEFAULT_SCORE,
    get_dataset_expression_policy,
)

# 导入执行器
from .core import (
    build_pending_templates_for_field,
    delete_pipeline_state,
    drain_completed_futures,
    load_pipeline_state,
    maybe_restore_runtime_concurrency,
    print_dry_run_plan,
    run_field_test_in_worker,
    save_checkpoint,
    save_pipeline_state,
    should_skip_field,
    throttle_before_submission,
)

# 导入异常类
# 导入表达式构建
# 导入字段管理
from .generators.fields import (
    fetch_fields_with_cache,
    load_fields_cache,
)

# 导入设置变体
from .generators.settings import (
    build_settings_fingerprint,
    stable_fingerprint,
)

# 导入模板库管理
from .generators.templates import ensure_dataset_template_library, load_template_library

# 导入凭证管理
from .io.credentials import load_credentials

# 导入输出模块
from .io.output import (
    cleanup_legacy_sidecar_files,
    ensure_analysis_synced,
    ensure_template_blacklist_file,
)
from .models.base import (
    ExecutionState,
    RuntimeConcurrencyState,
    TemplateBuildContext,
)

# 导入公共工具
from .utils.helpers import choose_field_name, choose_field_type, first_non_empty

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
    filters_dict: Any,
    expression_policy: Any,
    historical_state: Any,
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
        if _safe_float(field.get("coverage")) < expression_policy.field_min_coverage:
            low_coverage_count += 1
            continue
        if _safe_float(field.get("dateCoverage")) < expression_policy.field_min_date_coverage:
            low_date_coverage_count += 1
            continue
        if _safe_int(field.get("alphaCount")) < expression_policy.field_min_alpha_count:
            low_alpha_count += 1
            continue
        if _safe_int(field.get("userCount")) < expression_policy.field_min_user_count:
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
    """清理本地运行产物，默认保留加密凭据。
    Clean local runtime artifacts while preserving encrypted credentials by default.
    """
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

# ============================================================================
# 客户端创建和登录函数
# ============================================================================


def create_and_login_client(
    email: str, password: str, args: argparse.Namespace
) -> tuple[BrainClient, WorkerClientFactory]:
    """
    创建 Brain API 客户端并完成登录，同时创建工作线程客户端工厂。

    创建一个主客户端用于获取字段等初始化操作，以及一个客户端工厂
    用于为每个工作线程提供独立的已登录客户端。

    Args:
        email (str): WorldQuant Brain 账号的邮箱地址。
        password (str): WorldQuant Brain 账号的密码。
        args (argparse.Namespace): 命令行参数对象，包含以下属性：
            - min_request_interval: 最小请求间隔
            - rate_limit_max_retries: 速率限制重试次数
            - login_retries: 登录重试次数

    Returns:
        Tuple[BrainClient, WorkerClientFactory]: 返回一个元组，包含两个元素：
            - bootstrap_client: 主客户端，用于初始化操作
            - client_factory: 工作线程客户端工厂

    Example:
        >>> client, factory = create_and_login_client("user@example.com", "password", args)
        >>> print(client.email)
        user@example.com
        >>> # factory 可用于工作线程获取独立客户端

    Note:
        - 主客户端和工厂客户端使用相同的凭证
        - 主客户端用于字段获取等不需要高并发的操作
        - 工厂客户端用于并发模拟测试
        - 登录使用 login_with_retry 进行重试
    """
    # 创建主客户端
    bootstrap_client = BrainClient(
        email,
        password,
        min_request_interval=args.min_request_interval,
        rate_limit_max_retries=args.rate_limit_max_retries,
    )

    # 登录主客户端
    login_with_retry(bootstrap_client, args.login_retries)

    # 创建工作线程客户端工厂
    client_factory = WorkerClientFactory(args, email, password)

    return bootstrap_client, client_factory


# ============================================================================
# 初始化函数：设置凭证、客户端、模板、字段与历史状态
# ============================================================================


def _initialize(
    args: argparse.Namespace,
    run_paths: Any,
) -> tuple[Any, ...] | None:
    """执行主流程的初始化阶段（步骤 2-19），返回所有需要的状态变量。

    成功时返回包含 18 个值的元组，失败时返回 None。

    Returns:
        tuple or None: 成功时为包含所有状态变量的元组，失败时为 None。
    """
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

    # --- 字段加载与排序 ---
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

    # --- 执行状态初始化 ---
    execution_state = ExecutionState(
        results=list(historical_state.existing_results),
        attempted_keys=set(historical_state.attempted_keys),
        template_stats=dict(historical_state.template_stats),
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
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

    return (
        email,
        password,
        bootstrap_client,
        client_factory,
        template_library,
        filters_dict,
        expression_policy,
        use_dataset_heuristics,
        template_library_fingerprint,
        settings_fingerprint,
        feedback_output,
        historical_state,
        fields,
        execution_state,
        runtime_state,
        create_semaphore,
        run_config,
        output_file,
    )


# ============================================================================
# 执行循环：线程池 + 字段遍历 + 结果持久化
# ============================================================================


def _run_field_test_loop(
    args: argparse.Namespace,
    client_factory: WorkerClientFactory,
    template_library: Any,
    filters_dict: Any,
    expression_policy: Any,
    use_dataset_heuristics: bool,
    template_library_fingerprint: str,
    settings_fingerprint: str,
    historical_state: Any,
    fields: list[dict[str, Any]],
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    create_semaphore: threading.Semaphore,
    run_config: dict[str, Any],
    run_paths: Any = None,
) -> None:
    """线程池中遍历字段并提交模拟任务，实时消费结果。

    包含干运行检查、模板构建上下文创建、
    双重循环（字段 × 模板）和结果排空逻辑。
    支持断点续传：从 state_file 恢复进度并周期性保存。
    """
    state_file = getattr(run_paths, "state_file", "") if run_paths is not None else ""
    checkpoint_file = getattr(run_paths, "checkpoint_file", "") if run_paths is not None else ""
    max_workers = runtime_state.max_workers
    field_template_batch_size = max(0, int(getattr(args, "field_template_batch_size", 0) or 0))

    # --- 断点续传：恢复上次进度 ---
    resumed_index = 0
    if state_file:
        resumed_index = load_pipeline_state(
            state_file,
            runtime_state=runtime_state,
            execution_state=execution_state,
        )
        if resumed_index > 0:
            logger.info(
                "[resume] 从字段索引 %d/%d 附近继续 (优先从该位置恢复，但不会丢掉更早字段)",
                resumed_index + 1,
                len(fields),
            )
            fields = fields[resumed_index:] + fields[:resumed_index]

    # 干运行检查
    if args.dry_run_plan:
        print_dry_run_plan(
            args=args,
            fields=fields,
            filters=filters_dict,
            template_library=template_library,
            historical_state=historical_state,
            execution_state=execution_state,
            use_dataset_heuristics=use_dataset_heuristics,
        )
        return

    # 模板构建上下文
    template_build_ctx = TemplateBuildContext(
        args=args,
        all_fields=fields,
        template_library=template_library,
        field_feedback=historical_state.field_feedback,
        global_failed_check_counts=historical_state.global_failed_check_counts,
        include_templates=filters_dict.include_templates,
        exclude_templates=filters_dict.exclude_templates,
        use_dataset_heuristics=use_dataset_heuristics,
        expression_policy=expression_policy,
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        last_field_id = ""
        try:
            round_index = 0
            while True:
                round_index += 1
                progressed_this_round = False
                if field_template_batch_size > 0:
                    logger.info(
                        "[schedule] round=%d breadth-first batch_size=%d fields=%d",
                        round_index,
                        field_template_batch_size,
                        len(fields),
                    )
                for field_index, field in enumerate(fields, start=1):
                    if should_stop_after_submittable(args, execution_state.results):
                        logger.info(
                            "[stop] 达到 stop-after-submittable=%d",
                            args.stop_after_submittable,
                        )
                        break

                    field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
                    last_field_id = field_id
                    field_name = choose_field_name(field)
                    field_type = choose_field_type(field)

                    if should_skip_field(
                        field_id,
                        field_name,
                        filters_dict,
                        execution_state.skipped_fields_due_to_queue,
                    ):
                        continue

                    pending_templates, disabled_templates, template_count = (
                        build_pending_templates_for_field(
                            template_build_ctx,
                            field,
                            template_stats=execution_state.template_stats,
                            attempted_keys=execution_state.attempted_keys,
                            prior_results=execution_state.results,
                        )
                    )

                    logger.debug(
                        "[progress] 字段 %d/%d field_id=%s templates=%d pending=%d disabled=%d",
                        field_index,
                        len(fields),
                        field_id,
                        template_count,
                        len(pending_templates),
                        disabled_templates,
                    )

                    if field_template_batch_size > 0:
                        scheduled_templates = pending_templates[:field_template_batch_size]
                        deferred_templates = max(0, len(pending_templates) - len(scheduled_templates))
                    else:
                        scheduled_templates = pending_templates
                        deferred_templates = 0
                    if scheduled_templates:
                        progressed_this_round = True
                    if deferred_templates > 0:
                        logger.debug(
                            "[schedule] field=%s round=%d dispatch=%d deferred=%d",
                            field_id,
                            round_index,
                            len(scheduled_templates),
                            deferred_templates,
                        )

                    for template_index, (
                        template_name,
                        template_family,
                        expression,
                        priority,
                        settings_variant,
                        variant_fingerprint,
                    ) in enumerate(scheduled_templates, start=1):
                        if should_stop_after_submittable(args, execution_state.results):
                            logger.info(
                                "[stop] 达到 stop-after-submittable=%d",
                                args.stop_after_submittable,
                            )
                            break

                        if field_id in execution_state.skipped_fields_due_to_queue:
                            logger.warning(
                                "[skip] field=%s 队列拥塞后停止剩余模板", field_id
                            )
                            break

                        maybe_restore_runtime_concurrency(runtime_state)

                        while len(execution_state.pending_futures) >= runtime_state.runtime_max_workers:
                            done, _ = wait(
                                set(execution_state.pending_futures), return_when=FIRST_COMPLETED
                            )
                            drain_completed_futures(
                                completed_futures=list(done),
                                execution_state=execution_state,
                                args=args,
                                settings_fingerprint=settings_fingerprint,
                                template_library_fingerprint=template_library_fingerprint,
                                run_config=run_config,
                                runtime_state=runtime_state,
                            )
                            if field_id in execution_state.skipped_fields_due_to_queue:
                                break

                        logger.debug(
                            "[progress] field=%s template %d/%d name=%s priority=%d queued=%d/%d settings=%s",
                            field_id,
                            template_index,
                            len(scheduled_templates),
                            template_name,
                            priority,
                            len(execution_state.pending_futures) + 1,
                            runtime_state.runtime_max_workers,
                            variant_fingerprint,
                        )

                        throttle_before_submission(args, execution_state)

                        field_with_template = dict(field)
                        field_with_template["template_family"] = template_family
                        future = executor.submit(
                            run_field_test_in_worker,
                            client_factory,
                            args,
                            field_with_template,
                            template_name,
                            expression,
                            variant_fingerprint,
                            template_library_fingerprint,
                            settings_variant,
                            create_semaphore,
                        )

                        execution_state.last_submission_at = time.monotonic()
                        execution_state.pending_futures[future] = {
                            "field_id": field_id,
                            "field_name": field_name,
                            "field_type": field_type,
                            "template_name": template_name,
                            "template_family": template_family,
                            "expression": expression,
                            "settings_fingerprint": variant_fingerprint,
                        }

                    # 字段处理完成（含已跳过字段），保存中间状态
                    if state_file:
                        completed_index = resumed_index + field_index
                        save_pipeline_state(
                            state_file,
                            completed_field_index=completed_index,
                            execution_state=execution_state,
                            runtime_state=runtime_state,
                            field_id=field_id,
                        )

                if field_template_batch_size <= 0 or should_stop_after_submittable(
                    args, execution_state.results
                ):
                    break
                if not progressed_this_round:
                    logger.info("[schedule] no pending templates remain after round=%d", round_index)
                    break

            # 排空剩余任务
            while execution_state.pending_futures:
                done, _ = wait(set(execution_state.pending_futures), return_when=FIRST_COMPLETED)
                drain_completed_futures(
                    completed_futures=list(done),
                    execution_state=execution_state,
                    args=args,
                    settings_fingerprint=settings_fingerprint,
                    template_library_fingerprint=template_library_fingerprint,
                    run_config=run_config,
                    runtime_state=runtime_state,
                )
                # 排空后实时保存状态
                if state_file:
                    completed_index = resumed_index + len(fields)
                    save_pipeline_state(
                        state_file,
                        completed_field_index=completed_index,
                        execution_state=execution_state,
                        runtime_state=runtime_state,
                        field_id=last_field_id,
                    )
        except KeyboardInterrupt:
            # 用户中断时保存检查点（含待处理任务元数据）
            if checkpoint_file:
                save_checkpoint(
                    checkpoint_file,
                    execution_state=execution_state,
                    runtime_state=runtime_state,
                    field_id=last_field_id or "",
                    remaining_fields=max(0, len(fields)),
                    reason="KeyboardInterrupt",
                )
            raise
        except Exception:
            # 异常时保存崩溃检查点
            if checkpoint_file:
                save_checkpoint(
                    checkpoint_file,
                    execution_state=execution_state,
                    runtime_state=runtime_state,
                    field_id=last_field_id or "",
                    remaining_fields=max(0, len(fields)),
                    reason="Exception",
                )
            raise

    logger.info(
        "[done] 测试完成：tested=%d submittable=%d errors=%d",
        len(execution_state.results),
        current_submittable_count(execution_state.results),
        sum(1 for r in execution_state.results if r.status == "error"),
    )


# ============================================================================
# 主入口函数
# ============================================================================


def main() -> int:
    """
    主入口函数，编排凭证加载、字段发现、候选测试与结果持久化的主流程。

    分为两个阶段：
    1. _initialize(): 参数解析、凭证、客户端、模板、字段、历史状态
    2. _run_field_test_loop(): 线程池中遍历字段、提交模拟、实时持久化

    Returns:
        int: 退出状态码（0=正常, 1=错误, 130=用户中断）。
    """
    args = parse_args()

    if args.command == "clean":
        return clean_runtime_artifacts(args)

    run_paths = normalize_args_paths(args)

    init_result = _initialize(args, run_paths)
    if init_result is None:
        return 1

    (
        _email,
        _password,
        _bootstrap_client,
        client_factory,
        template_library,
        filters_dict,
        expression_policy,
        use_dataset_heuristics,
        template_library_fingerprint,
        settings_fingerprint,
        _feedback_output,
        historical_state,
        fields,
        execution_state,
        runtime_state,
        create_semaphore,
        run_config,
        _output_file,
    ) = init_result

    _run_field_test_loop(
        args=args,
        client_factory=client_factory,
        template_library=template_library,
        filters_dict=filters_dict,
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
        run_paths=run_paths,
    )

    # 运行完成，清理中间状态文件
    delete_pipeline_state(getattr(run_paths, "state_file", ""))

    return 0


# ============================================================================
# 程序入口点
# ============================================================================

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.warning("[abort] 用户中断")
        raise SystemExit(130) from None
    except Exception as exc:
        logger.error("[error] %s", exc)
        raise SystemExit(1) from None
