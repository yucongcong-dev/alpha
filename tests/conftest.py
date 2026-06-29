"""
pytest 共享 fixtures 和配置。

提供测试套件中复用的 fixtures，消除各测试文件中的重复 setup。
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from alpha.models.base import (
    ExecutionState,
    FieldTestContext,
    FieldTestResult,
    RuntimeConcurrencyState,
)

# ============================================================================
# 常量定义
# ============================================================================

FAR_FUTURE_SECONDS = 99999
"""用于模拟"遥远的未来冷却时间"的常量。"""

ASSERT_ALMOST_EQUAL_DELTA = 0.5
"""assertAlmostEqual 的默认浮点精度容差。"""

DEFAULT_COOLDOWN_SECONDS = 180
"""默认拥塞冷却秒数。"""

FAILURE_TRUNCATION_LIMIT = 300
"""summarize_failure 的 JSON 截断上限。"""

FAILED_CHECKS_DISPLAY_CAP = 5
"""summarize_failure 中失败检查项显示上限。"""


# ============================================================================
# Mock args 工厂
# ============================================================================


class MockArgs:
    """
    带类型约束的 argparse.Namespace 替代品。

    相比 MagicMock，此类只接受预定义属性，防止拼写错误导致静默创建新属性。
    用于 scheduler/simulation 测试中需要 args 参数的场景。
    """

    def __init__(self, **kwargs: Any) -> None:
        self._allowed = set(kwargs.keys())
        for key, value in kwargs.items():
            object.__setattr__(self, key, value)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_allowed" or name in self._allowed:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(
                f"MockArgs does not accept attribute '{name}'. Allowed: {sorted(self._allowed)}"
            )


@pytest.fixture
def scheduler_args() -> MockArgs:
    """scheduler 测试的标准 mock args，包含拥塞/节流相关配置。"""
    return MockArgs(
        queue_busy_cooldown_seconds=DEFAULT_COOLDOWN_SECONDS,
        field_queue_busy_skip_after=3,
        sleep_between_fields=2.0,
        simulation_create_retries=3,
        simulation_poll_retries=3,
        simulation_max_polls=100,
        simulation_max_wait_seconds=600.0,
        simulation_max_pending_cycles=10,
        simulation_max_queue_seconds=60.0,
        check_submit_retries=3,
        submit_retries=3,
        submit=False,
        output="results",
        dataset_id="fundamental6",
    )


# ============================================================================
# 状态对象 fixtures
# ============================================================================


def _make_execution_state(last_submission_at: float = 0.0) -> ExecutionState:
    """ExecutionState 工厂：除 last_submission_at 外其他字段均为空。"""
    return ExecutionState(
        results=[],
        attempted_keys=set(),
        template_stats={},
        pending_futures={},
        field_queue_busy_counts={},
        skipped_fields_due_to_queue=set(),
        last_submission_at=last_submission_at,
    )


@pytest.fixture
def empty_execution_state() -> ExecutionState:
    """空的 ExecutionState，所有集合/字典为空，last_submission_at 为 0.0。"""
    return _make_execution_state()


@pytest.fixture
def execution_state_after_submit() -> ExecutionState:
    """模拟已提交一次的 ExecutionState，last_submission_at 为 0.5 秒前。"""
    return _make_execution_state(max(0.001, time.monotonic() - 0.5))


@pytest.fixture
def execution_state_long_ago_submit() -> ExecutionState:
    """模拟很久前提交的 ExecutionState，last_submission_at 为 5 秒前。"""
    return _make_execution_state(time.monotonic() - 5.0)


@pytest.fixture
def runtime_state_max_workers_5() -> RuntimeConcurrencyState:
    """max_workers=5 的 RuntimeConcurrencyState。"""
    return RuntimeConcurrencyState(max_workers=5, runtime_max_workers=5)


@pytest.fixture
def runtime_state_cooling_down() -> RuntimeConcurrencyState:
    """正在冷却中的 RuntimeConcurrencyState（runtime=1, 冷却到很远的未来）。"""
    return RuntimeConcurrencyState(
        max_workers=5,
        runtime_max_workers=1,
        cooldown_until=time.monotonic() + FAR_FUTURE_SECONDS,
    )


@pytest.fixture
def runtime_state_cooldown_expired() -> RuntimeConcurrencyState:
    """冷却已过期的 RuntimeConcurrencyState。"""
    expired_positive_deadline = max(0.001, time.monotonic() / 2)
    return RuntimeConcurrencyState(
        max_workers=5,
        runtime_max_workers=1,
        cooldown_until=expired_positive_deadline,
    )


# ============================================================================
# FieldTestContext fixtures
# ============================================================================


@pytest.fixture
def basic_test_context() -> FieldTestContext:
    """标准 MATRIX 字段的 FieldTestContext。"""
    return FieldTestContext(
        field_id="sales",
        field_type="MATRIX",
        field_name="sales",
        template_name="ts_mean_20",
        expression="rank(ts_mean(sales, 20))",
        settings_fingerprint="abc123",
        template_library_fingerprint="def456",
    )


@pytest.fixture
def minimal_test_context() -> FieldTestContext:
    """最小参数的 FieldTestContext（无 fingerprint）。"""
    return FieldTestContext(
        field_id="x",
        field_type="VECTOR",
        field_name="x",
        template_name="x",
        expression="x",
    )


# ============================================================================
# FieldTestResult fixtures
# ============================================================================


@pytest.fixture
def sample_field_test_result() -> FieldTestResult:
    """标准 FieldTestResult 样本。"""
    return FieldTestResult(
        field_id="sales",
        field_type="MATRIX",
        field_name="sales",
        template_name="ts_mean_20",
        status="simulated",
        submittable=True,
        expression="rank(ts_mean(sales, 20))",
    )


@pytest.fixture
def failed_field_test_result() -> FieldTestResult:
    """带失败检查的 FieldTestResult 样本。"""
    return FieldTestResult(
        field_id="sales",
        field_type="MATRIX",
        field_name="sales",
        template_name="ts_mean_20",
        expression="rank(ts_mean(sales, 20))",
        submittable=False,
        failed_checks=[
            {"name": "LOW_SHARPE", "value": -0.1},
            {"name": "LOW_FITNESS", "value": -0.2},
        ],
    )


# ============================================================================
# 计数/集合 fixtures
# ============================================================================


@pytest.fixture
def empty_counts_and_skipped() -> tuple[dict[str, int], set[str]]:
    """空的 field_queue_busy_counts 和 skipped_fields_due_to_queue。"""
    return {}, set()
