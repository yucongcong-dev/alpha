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

import argparse
import logging
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
    setup_runtime_logging,
)

# 导入配置和模型
from .config import SENTINEL_UNKNOWN, use_fundamental6_heuristics

# 导入执行器
from .core import (
    build_pending_templates_for_field,
    drain_completed_futures,
    maybe_restore_runtime_concurrency,
    print_dry_run_plan,
    run_field_test_in_worker,
    should_skip_field,
    throttle_before_submission,
)

# 导入异常类
# 导入表达式构建
# 导入字段管理
from .generators.fields import (
    fetch_fields_with_cache,
    fields_cache_refresh_reason,
    load_fields_cache,
)

# 导入设置变体
from .generators.settings import (
    build_settings_fingerprint,
    stable_fingerprint,
)

# 导入模板库管理
from .generators.templates import load_template_library

# 导入凭证管理
from .io.credentials import load_credentials

# 导入输出模块
from .io.output import (
    cleanup_legacy_sidecar_files,
    ensure_analysis_synced,
)
from .models.base import (
    ExecutionState,
    RuntimeConcurrencyState,
    TemplateBuildContext,
)

# 导入公共工具
from .utils.helpers import choose_field_name, choose_field_type, first_non_empty

logger = logging.getLogger(__name__)

# ============================================================================
# 客户端创建和登录函数
# ============================================================================

def create_and_login_client(
    email: str,
    password: str,
    args: argparse.Namespace
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
) -> tuple[Any, ...]:
    """执行主流程的初始化阶段（步骤 2-19），返回所有需要的状态变量。

    Returns a tuple:
        (email, password, bootstrap_client, client_factory,
         template_library, filters_dict, use_dataset_heuristics,
         template_library_fingerprint, settings_fingerprint,
         feedback_output, historical_state, fields,
         execution_state, runtime_state, create_semaphore,
         run_config, output_file)
    """
    output_file = getattr(run_paths, 'output', None) or args.output
    log_file = getattr(run_paths, 'log_file', None)
    if log_file:
        setup_runtime_logging(log_file)

    cleanup_legacy_sidecar_files(output_file, verbose=True)
    ensure_analysis_synced(output_file)

    run_config = build_run_config_snapshot(args, run_paths)
    logger.info("[config] 运行配置将嵌入主结果文件")

    email, password = load_credentials(args)
    if not email or not password:
        logger.error("[error] 缺少凭证，无法继续")
        return (None,) * 18

    bootstrap_client, client_factory = create_and_login_client(email, password, args)

    template_library_file = getattr(run_paths, 'template_library_file', None) or args.template_library_file
    template_library = load_template_library(template_library_file)
    filters_dict = load_run_filters_extended(run_paths)
    use_dataset_heuristics = use_fundamental6_heuristics(args.dataset_id)
    template_library_fingerprint = stable_fingerprint(template_library)
    settings_fingerprint = build_settings_fingerprint(args)
    feedback_output = getattr(run_paths, 'feedback_output', None) or output_file
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
    cache_refresh_reason = fields_cache_refresh_reason(
        cached_fields,
        requested_limit=args.limit,
        requested_offset=args.offset,
        force_refresh=args.refresh_fields_cache,
    )
    fields = fetch_fields_with_cache(
        bootstrap_client, args, fields_cache_file, cached_fields, cache_refresh_reason,
    )
    if not fields:
        logger.error("[error] 数据集 %s 未返回任何字段", args.dataset_id)
        return (None,) * 18

    fields.sort(
        key=lambda item: (
            -field_priority(
                str(first_non_empty(item.get("id"), SENTINEL_UNKNOWN)),
                historical_state.field_feedback,
            ),
            choose_field_name(item),
        )
    )
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
        logger.info("[focus] 限制运行到按反馈排序的前 %d 个字段", len(fields))

    logger.info("[data] 从数据集 %s 获取 %d 个字段", args.dataset_id, len(fields))

    if historical_state.existing_results:
        logger.info(
            "[resume] 从 %s 加载 %d 个历史结果",
            output_file, len(historical_state.existing_results),
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
        email, password, bootstrap_client, client_factory,
        template_library, filters_dict, use_dataset_heuristics,
        template_library_fingerprint, settings_fingerprint,
        feedback_output, historical_state, fields,
        execution_state, runtime_state, create_semaphore,
        run_config, output_file,
    )


# ============================================================================
# 执行循环：线程池 + 字段遍历 + 结果持久化
# ============================================================================

def _run_field_test_loop(
    args: argparse.Namespace,
    client_factory: WorkerClientFactory,
    template_library: Any,
    filters_dict: Any,
    use_dataset_heuristics: bool,
    template_library_fingerprint: str,
    settings_fingerprint: str,
    historical_state: Any,
    fields: list[dict[str, Any]],
    execution_state: ExecutionState,
    runtime_state: RuntimeConcurrencyState,
    create_semaphore: threading.Semaphore,
    run_config: dict[str, Any],
) -> None:
    """线程池中遍历字段并提交模拟任务，实时消费结果。

    包含干运行检查、模板构建上下文创建、
    双重循环（字段 × 模板）和结果排空逻辑。
    """
    max_workers = runtime_state.max_workers

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
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for field_index, field in enumerate(fields, start=1):
            if should_stop_after_submittable(args, execution_state.results):
                logger.info(
                    "[stop] 达到 stop-after-submittable=%d", args.stop_after_submittable,
                )
                break

            field_id = str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN))
            field_name = choose_field_name(field)
            field_type = choose_field_type(field)

            if should_skip_field(
                field_id, field_name, filters_dict,
                execution_state.skipped_fields_due_to_queue,
            ):
                continue

            pending_templates, disabled_templates, template_count = build_pending_templates_for_field(
                template_build_ctx,
                field,
                template_stats=execution_state.template_stats,
                attempted_keys=execution_state.attempted_keys,
                prior_results=execution_state.results,
            )

            logger.info(
                "[progress] 字段 %d/%d field_id=%s templates=%d pending=%d disabled=%d",
                field_index, len(fields), field_id, template_count,
                len(pending_templates), disabled_templates,
            )

            for template_index, (template_name, expression, priority, settings_variant, variant_fingerprint) in enumerate(pending_templates, start=1):
                if should_stop_after_submittable(args, execution_state.results):
                    logger.info(
                        "[stop] 达到 stop-after-submittable=%d", args.stop_after_submittable,
                    )
                    break

                if field_id in execution_state.skipped_fields_due_to_queue:
                    logger.info("[skip] field=%s 队列拥塞后停止剩余模板", field_id)
                    break

                maybe_restore_runtime_concurrency(runtime_state)

                while len(execution_state.pending_futures) >= runtime_state.runtime_max_workers:
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
                    if field_id in execution_state.skipped_fields_due_to_queue:
                        break

                logger.info(
                    "[progress] field=%s template %d/%d name=%s priority=%d queued=%d/%d settings=%s",
                    field_id, template_index, len(pending_templates), template_name,
                    priority, len(execution_state.pending_futures) + 1,
                    runtime_state.runtime_max_workers, variant_fingerprint,
                )

                throttle_before_submission(args, execution_state)

                future = executor.submit(
                    run_field_test_in_worker,
                    client_factory,
                    args,
                    field,
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
                    "expression": expression,
                    "settings_fingerprint": variant_fingerprint,
                }

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

    logger.info(
        "[done] 测试完成：tested=%d submittable=%d errors=%d",
        len(execution_state.results),
        current_submittable_count(execution_state.results),
        sum(1 for r in execution_state.results if r.status == 'error'),
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
    run_paths = normalize_args_paths(args)

    (
        email, password, bootstrap_client, client_factory,
        template_library, filters_dict, use_dataset_heuristics,
        template_library_fingerprint, settings_fingerprint,
        feedback_output, historical_state, fields,
        execution_state, runtime_state, create_semaphore,
        run_config, output_file,
    ) = _initialize(args, run_paths)

    if not email or not password or not fields:
        return 1

    _run_field_test_loop(
        args=args,
        client_factory=client_factory,
        template_library=template_library,
        filters_dict=filters_dict,
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
