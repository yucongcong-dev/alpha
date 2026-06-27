"""models/base.py 数据类单元测试"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import time

import pytest

from alpha.models.base import (
    ExecutionState,
    FieldTestContext,
    FieldTestResult,
    HistoricalRunState,
    RunFilters,
    RuntimeConcurrencyState,
)

# ============================================================================
# RuntimeConcurrencyState 测试
# ============================================================================


class TestRuntimeConcurrencyState:
    """测试运行时并发状态"""

    def test_default_values(self) -> None:
        state = RuntimeConcurrencyState()
        assert state.max_workers == 2
        assert state.runtime_max_workers == 2
        assert state.cooldown_until == 0.0
        assert not state.is_cooling_down()

    def test_is_cooling_down_active(self) -> None:
        state = RuntimeConcurrencyState(cooldown_until=time.monotonic() + 99999)
        assert state.is_cooling_down()

    def test_is_cooling_down_inactive_zero(self) -> None:
        state = RuntimeConcurrencyState(cooldown_until=0.0)
        assert not state.is_cooling_down()

    def test_can_restore_concurrency_yes(self) -> None:
        state = RuntimeConcurrencyState(max_workers=5, runtime_max_workers=1, cooldown_until=100.0)
        assert state.can_restore_concurrency()

    def test_can_restore_concurrency_no_when_cooling(self) -> None:
        state = RuntimeConcurrencyState(
            max_workers=5,
            runtime_max_workers=1,
            cooldown_until=time.monotonic() + 99999,
        )
        assert not state.can_restore_concurrency()

    def test_can_restore_concurrency_no_same_workers(self) -> None:
        state = RuntimeConcurrencyState(max_workers=5, runtime_max_workers=5, cooldown_until=100.0)
        assert not state.can_restore_concurrency()


# ============================================================================
# ExecutionState 测试
# ============================================================================


class TestExecutionState:
    """测试执行状态"""

    def test_default_state_is_empty(self) -> None:
        state = ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        )
        assert state.results == []
        assert state.attempted_keys == set()
        assert state.template_stats == {}
        assert state.pending_futures == {}
        assert state.field_queue_busy_counts == {}
        assert state.skipped_fields_due_to_queue == set()
        assert state.last_submission_at == 0.0

    def test_custom_values(self) -> None:
        state = ExecutionState(
            results=[{"id": "alpha1"}],
            attempted_keys={"key1"},
            template_stats={"tmpl": {"count": 1}},
            pending_futures={},
            field_queue_busy_counts={"f1": 2},
            skipped_fields_due_to_queue={"f2"},
            last_submission_at=123.0,
        )
        assert len(state.results) == 1
        assert "key1" in state.attempted_keys
        assert state.template_stats["tmpl"]["count"] == 1
        assert state.field_queue_busy_counts["f1"] == 2
        assert "f2" in state.skipped_fields_due_to_queue
        assert state.last_submission_at == 123.0


# ============================================================================
# FieldTestResult 测试
# ============================================================================


class TestFieldTestResult:
    """测试字段测试结果"""

    def test_submittable_result(self) -> None:
        result = FieldTestResult(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="ts_mean_20",
            expression="rank(ts_mean(sales, 20))",
            status="simulated",
            submittable=True,
        )
        assert result.submittable
        assert result.status == "simulated"
        assert result.field_id == "sales"

    def test_failed_result_with_checks(self) -> None:
        result = FieldTestResult(
            field_id="x",
            field_type="VECTOR",
            field_name="x",
            template_name="ts_delta",
            expression="ts_delta(x, 5)",
            submittable=False,
            failed_checks=[
                {"name": "LOW_SHARPE", "value": -0.1},
                {"name": "LOW_FITNESS", "value": -0.2},
            ],
        )
        assert not result.submittable
        assert len(result.failed_checks) == 2


# ============================================================================
# FieldTestContext 测试
# ============================================================================


class TestFieldTestContext:
    """测试字段测试上下文"""

    def test_full_context(self) -> None:
        ctx = FieldTestContext(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="ts_mean_20",
            expression="rank(ts_mean(sales, 20))",
            settings_fingerprint="abc123",
            template_library_fingerprint="def456",
        )
        assert ctx.field_id == "sales"
        assert ctx.field_type == "MATRIX"
        assert ctx.settings_fingerprint == "abc123"

    def test_minimal_context(self) -> None:
        ctx = FieldTestContext(
            field_id="x",
            field_type="VECTOR",
            field_name="x",
            template_name="x",
            expression="x",
        )
        assert ctx.field_id == "x"
        assert ctx.settings_fingerprint == ""
        assert ctx.template_library_fingerprint == ""


# ============================================================================
# HistoricalRunState 测试
# ============================================================================


class TestHistoricalRunState:
    """测试历史运行状态"""

    def test_empty_state(self) -> None:
        state = HistoricalRunState()
        assert state.existing_results == []
        assert state.attempted_keys == set()
        assert state.field_feedback == {}
        assert state.template_stats == {}

    def test_with_results(self) -> None:
        state = HistoricalRunState(
            existing_results=[{"id": "alpha1", "submittable": True}],
            attempted_keys={"alpha1"},
            field_feedback={"sales": 0.5},
            template_stats={"ts_mean_20": {"count": 1, "submittable": 1}},
        )
        assert len(state.existing_results) == 1
        assert "alpha1" in state.attempted_keys
        assert state.field_feedback["sales"] == 0.5


# ============================================================================
# RunFilters 测试
# ============================================================================


class TestRunFilters:
    """测试运行过滤器（不可变）"""

    def test_default_filters(self) -> None:
        filters = RunFilters()
        assert filters.include_fields == set()
        assert filters.exclude_fields == set()
        assert filters.include_templates == set()
        assert filters.exclude_templates == set()

    def test_custom_filters(self) -> None:
        filters = RunFilters(
            include_fields={"sales", "profit"},
            exclude_fields={"dummy"},
            include_templates={"ts_mean"},
            exclude_templates={"ts_rank"},
        )
        assert "sales" in filters.include_fields
        assert "dummy" in filters.exclude_fields

    def test_frozen_filters_immutable(self) -> None:
        filters = RunFilters(include_fields={"a"})
        with pytest.raises(FrozenInstanceError):
            filters.include_fields = {"b"}
