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
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Tuple

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
from .config import use_fundamental6_heuristics

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

# ============================================================================
# 客户端创建和登录函数
# ============================================================================

def create_and_login_client(
    email: str,
    password: str,
    args: argparse.Namespace
) -> Tuple[BrainClient, WorkerClientFactory]:
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
# 主入口函数
# ============================================================================

def main() -> int:
    """
    主入口函数，编排凭证加载、字段发现、候选测试与结果持久化的主流程。

    这是 Alpha 测试系统的核心函数，负责协调所有模块完成测试流程。
    主流程包括：

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

    Returns:
        int: 退出状态码。
            - 0: 正常完成
            - 1: 发生错误
            - 130: 用户中断（Ctrl+C）

    Example:
        >>> exit_code = main()
        >>> print(exit_code)
        0

    Note:
        - 支持 Ctrl+C 中断
        - 支持干运行模式（只打印计划）
        - 支持续跑（加载历史结果）
        - 支持并发测试
        - 结果实时持久化，避免中断丢失
    """
    # 主流程：
    # 1. 加载凭证
    # 2. 认证登录
    # 3. 获取数据集字段
    # 4. 对每个字段-模板候选进行独立模拟/检查/提交
    # 5. 持久化 JSON 结果报告

    # 步骤 1：解析命令行参数
    args = parse_args()

    # 步骤 2：标准化路径
    run_paths = normalize_args_paths(args)

    # 清理旧版边车文件
    output_file = getattr(run_paths, 'output', None) or args.output
    cleanup_legacy_sidecar_files(output_file, verbose=True)

    # 步骤 3：设置运行时日志
    log_file = getattr(run_paths, 'log_file', None)
    if log_file:
        setup_runtime_logging(log_file)

    # 确保分析文件同步
    ensure_analysis_synced(output_file)

    # 步骤 4：构建运行配置快照
    run_config = build_run_config_snapshot(args, run_paths)
    print("[config] 运行配置将嵌入主结果文件", flush=True)

    # 步骤 5：加载凭证
    email, password = load_credentials(args)
    if not email or not password:
        print("[error] 缺少凭证，无法继续", file=sys.stderr, flush=True)
        return 1

    # 步骤 6：创建并登录客户端
    bootstrap_client, client_factory = create_and_login_client(email, password, args)

    # 步骤 7：加载模板库
    template_library_file = getattr(run_paths, 'template_library_file', None) or args.template_library_file
    template_library = load_template_library(template_library_file)

    # 步骤 8：加载过滤器
    filters_dict = load_run_filters_extended(run_paths)

    # 步骤 9：判断是否使用数据集启发式规则
    use_dataset_heuristics = use_fundamental6_heuristics(args.dataset_id)

    # 步骤 10：生成模板库指纹
    template_library_fingerprint = stable_fingerprint(template_library)

    # 步骤 11：生成设置指纹
    settings_fingerprint = build_settings_fingerprint(args)

    # 步骤 12：确定反馈输出文件
    feedback_output = getattr(run_paths, 'feedback_output', None) or output_file

    # 步骤 13：构建历史运行状态
    historical_state = build_historical_run_state(output_file, feedback_output)

    # 步骤 14：加载字段缓存
    fields_cache_file = args.fields_cache_file
    cached_fields = load_fields_cache(
        fields_cache_file,
        dataset_id=args.dataset_id,
        region=args.region,
        universe=args.universe,
        instrument_type=args.instrument_type,
        delay=args.delay,
    )

    # 步骤 15：判断是否需要刷新缓存
    cache_refresh_reason = fields_cache_refresh_reason(
        cached_fields,
        requested_limit=args.limit,
        requested_offset=args.offset,
        force_refresh=args.refresh_fields_cache,
    )

    # 步骤 16：获取字段（带缓存）
    fields = fetch_fields_with_cache(
        bootstrap_client,
        args,
        fields_cache_file,
        cached_fields,
        cache_refresh_reason,
    )

    if not fields:
        print(f"[error] 数据集 {args.dataset_id} 未返回任何字段", file=sys.stderr, flush=True)
        return 1

    # 步骤 17：按反馈分数排序字段
    fields.sort(
        key=lambda item: (
            -field_priority(
                str(first_non_empty(item.get("id"), "UNKNOWN")),
                historical_state.field_feedback
            ),
            choose_field_name(item),
        )
    )

    # 步骤 18：如果指定了按反馈筛选，只保留前 N 个字段
    if args.top_fields_by_feedback > 0:
        focused_fields = [
            field
            for field in fields
            if field_priority(
                str(first_non_empty(field.get("id"), "UNKNOWN")),
                historical_state.field_feedback
            ) > -999.0
        ]
        fields = focused_fields[: args.top_fields_by_feedback]
        print(
            f"[focus] 限制运行到按反馈排序的前 {len(fields)} 个字段",
            flush=True,
        )

    print(f"[data] 从数据集 {args.dataset_id} 获取 {len(fields)} 个字段", flush=True)

    # 步骤 19：打印历史结果信息
    if historical_state.existing_results:
        print(
            f"[resume] 从 {output_file} 加载 {len(historical_state.existing_results)} 个历史结果",
            flush=True,
        )

    # 步骤 20：初始化执行状态
    execution_state = ExecutionState(
        results=list(historical_state.existing_results),
        attempted_keys=set(historical_state.attempted_keys),
        template_stats=dict(historical_state.template_stats),
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
    )

    # 步骤 21：初始化并发状态
    max_workers = max(1, args.max_concurrent_simulations)
    runtime_state = RuntimeConcurrencyState(
        max_workers=max_workers,
        runtime_max_workers=max_workers,
    )
    max_create_workers = max(1, args.max_concurrent_creates)
    create_semaphore = threading.Semaphore(max_create_workers)

    print(f"[config] max_concurrent_simulations={max_workers}", flush=True)
    print(f"[config] max_concurrent_creates={max_create_workers}", flush=True)
    print(f"[config] simulation_max_pending_cycles={args.simulation_max_pending_cycles}", flush=True)

    # 步骤 22：干运行模式处理
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
        return 0

    # 步骤 23：构建模板构建上下文（收敛 11 个参数为 1 个）
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

    # 步骤 24：启动线程池执行器
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 步骤 25：遍历字段
        for field_index, field in enumerate(fields, start=1):
            # 检查是否达到目标可提交数量
            if should_stop_after_submittable(args, execution_state.results):
                print(
                    f"[stop] 达到 stop-after-submittable={args.stop_after_submittable}",
                    flush=True,
                )
                break

            field_id = str(first_non_empty(field.get("id"), "UNKNOWN"))
            field_name = choose_field_name(field)
            field_type = choose_field_type(field)

            # 检查是否应该跳过该字段
            if should_skip_field(
                field_id,
                field_name,
                filters_dict,
                execution_state.skipped_fields_due_to_queue,
            ):
                continue

            # 步骤 26：为字段构建待执行模板队列
            pending_templates, disabled_templates, template_count = build_pending_templates_for_field(
                template_build_ctx,
                field,
                template_stats=execution_state.template_stats,
                attempted_keys=execution_state.attempted_keys,
                prior_results=execution_state.results,
            )

            print(
                f"[progress] 字段 {field_index}/{len(fields)} field_id={field_id} "
                f"templates={template_count} pending={len(pending_templates)} disabled={disabled_templates}",
                flush=True,
            )

            # 步骤 26：遍历模板
            for template_index, (template_name, expression, priority, settings_variant, variant_fingerprint) in enumerate(pending_templates, start=1):
                # 检查是否达到目标可提交数量
                if should_stop_after_submittable(args, execution_state.results):
                    print(
                        f"[stop] 达到 stop-after-submittable={args.stop_after_submittable}",
                        flush=True,
                    )
                    break

                # 检查字段是否因队列拥塞被跳过
                if field_id in execution_state.skipped_fields_due_to_queue:
                    print(f"[skip] field={field_id} 队列拥塞后停止剩余模板", flush=True)
                    break

                # 恢复运行时并发度
                maybe_restore_runtime_concurrency(runtime_state)

                # 等待有空闲工作线程
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

                print(
                    f"[progress] field={field_id} template {template_index}/{len(pending_templates)} "
                    f"name={template_name} priority={priority} queued={len(execution_state.pending_futures) + 1}/{runtime_state.runtime_max_workers} "
                    f"settings={variant_fingerprint}",
                    flush=True,
                )

                # 步骤 27：提交前节流
                throttle_before_submission(args, execution_state)

                # 步骤 28：提交任务到执行器
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

        # 步骤 29：处理剩余的待处理任务
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

    # 步骤 30：完成的任务已实时持久化，避免重复写入
    print(
        f"[done] 测试完成：tested={len(execution_state.results)} "
        f"submittable={current_submittable_count(execution_state.results)} "
        f"errors={sum(1 for r in execution_state.results if r.status == 'error')}",
        flush=True,
    )

    return 0


# ============================================================================
# 程序入口点
# ============================================================================

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[abort] 用户中断", file=sys.stderr)
        raise SystemExit(130) from None
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from None
