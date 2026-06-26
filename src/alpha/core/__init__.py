# -*- coding: utf-8 -*-
"""
核心执行业务包

包含 Alpha 测试的核心执行逻辑，分为三个子模块：
- executor: 高层协调，负责任务队列构建和干运行计划
- simulation: 模拟生命周期管理，负责单个模拟任务的创建、轮询、检查和提交
- scheduler: 并发调度与拥塞控制，负责动态调整并发数和任务节流
"""

from .executor import (
    build_pending_templates_for_field,
    should_skip_expression_by_history,
    should_skip_field,
    print_dry_run_plan,
)

from .simulation import (
    extract_alpha_id,
    extract_checks,
    extract_failed_checks,
    is_submittable_from_checks,
    summarize_failure,
    create_simulation_with_retry,
    poll_simulation_with_retry,
    checksubmit_with_retry,
    submit_with_retry,
    build_failure_result,
    run_field_test,
    run_field_test_in_worker,
)

from .scheduler import (
    handle_completed_future,
    maybe_restore_runtime_concurrency,
    register_queue_busy_field,
    apply_congestion_cooldown,
    throttle_before_submission,
    drain_completed_futures,
)

__all__ = [
    "build_pending_templates_for_field",
    "should_skip_expression_by_history",
    "should_skip_field",
    "print_dry_run_plan",
    "extract_alpha_id",
    "extract_checks",
    "extract_failed_checks",
    "is_submittable_from_checks",
    "summarize_failure",
    "create_simulation_with_retry",
    "poll_simulation_with_retry",
    "checksubmit_with_retry",
    "submit_with_retry",
    "build_failure_result",
    "run_field_test",
    "run_field_test_in_worker",
    "handle_completed_future",
    "maybe_restore_runtime_concurrency",
    "register_queue_busy_field",
    "apply_congestion_cooldown",
    "throttle_before_submission",
    "drain_completed_futures",
]
