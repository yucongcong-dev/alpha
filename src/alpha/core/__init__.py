
from __future__ import annotations
"""
核心执行业务包

包含 Alpha 测试的核心执行逻辑，分为三个子模块：
- executor: 高层协调，负责任务队列构建和干运行计划
- simulation: 模拟生命周期管理，负责单个模拟任务的创建、轮询、检查和提交
- scheduler: 并发调度与拥塞控制，负责动态调整并发数和任务节流
"""

from .executor import (
    build_pending_templates_for_field,
    print_dry_run_plan,
    should_skip_expression_by_history,
    should_skip_field,
)
from .scheduler import (
    apply_congestion_cooldown,
    drain_completed_futures,
    handle_completed_future,
    maybe_restore_runtime_concurrency,
    register_queue_busy_field,
    throttle_before_submission,
)
from .simulation import (
    build_failure_result,
    checksubmit_with_retry,
    create_simulation_with_retry,
    extract_alpha_id,
    extract_checks,
    extract_failed_checks,
    is_submittable_from_checks,
    poll_simulation_with_retry,
    run_field_test,
    run_field_test_in_worker,
    submit_with_retry,
    summarize_failure,
)

__all__ = [
    "apply_congestion_cooldown",
    "build_failure_result",
    "build_pending_templates_for_field",
    "checksubmit_with_retry",
    "create_simulation_with_retry",
    "drain_completed_futures",
    "extract_alpha_id",
    "extract_checks",
    "extract_failed_checks",
    "handle_completed_future",
    "is_submittable_from_checks",
    "maybe_restore_runtime_concurrency",
    "poll_simulation_with_retry",
    "print_dry_run_plan",
    "register_queue_busy_field",
    "run_field_test",
    "run_field_test_in_worker",
    "should_skip_expression_by_history",
    "should_skip_field",
    "submit_with_retry",
    "summarize_failure",
    "throttle_before_submission",
]
