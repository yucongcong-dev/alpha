"""models/base.py 数据类单元测试"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import time

import pytest

from alpha.models.base import (
    ApiClientOptions,
    ExecutionState,
    FieldFetchOptions,
    FieldTestContext,
    FieldTestResult,
    HistoricalRunState,
    ResultWriteOptions,
    RunFilters,
    RuntimeConcurrencyState,
    TemplateBuildOptions,
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
        state = RuntimeConcurrencyState(
            max_workers=5,
            runtime_max_workers=1,
            cooldown_until=max(0.001, time.monotonic() / 2),
        )
        assert state.can_restore_concurrency()

    def test_can_restore_concurrency_no_when_cooling(self) -> None:
        state = RuntimeConcurrencyState(
            max_workers=5,
            runtime_max_workers=1,
            cooldown_until=time.monotonic() + 99999,
        )
        assert not state.can_restore_concurrency()

    def test_can_restore_concurrency_no_same_workers(self) -> None:
        state = RuntimeConcurrencyState(
            max_workers=5,
            runtime_max_workers=5,
            cooldown_until=max(0.001, time.monotonic() / 2),
        )
        assert not state.can_restore_concurrency()


class TestRuntimeOptionBuilders:
    """测试从 args-like 对象提取窄配置。"""

    def test_api_client_options_from_args(self) -> None:
        class _Args:
            min_request_interval = "0.25"
            rate_limit_max_retries = "7"
            login_retries = 3

        assert ApiClientOptions.from_args(_Args()) == ApiClientOptions(
            min_request_interval=0.25,
            rate_limit_max_retries=7,
            login_retries=3,
        )

    def test_template_build_options_from_args(self) -> None:
        class _Args:
            dataset_id = "fundamental6"
            max_templates_per_field = "8"
            max_templates_per_family = 2
            legacy_similarity_penalty = "4"
            template_disable_after = 5
            disable_legacy_after = 6
            region = "USA"
            universe = "TOP3000"
            instrument_type = "EQUITY"
            delay = "1"
            decay = "7"
            neutralization = "SUBINDUSTRY"
            truncation = "0.08"
            pasteurization = "OFF"
            unit_handling = "VERIFY"
            nan_handling = "OFF"
            language = "FASTEXPR"
            start_date = "2020-01-01"
            end_date = "2020-12-31"

        options = TemplateBuildOptions.from_args(_Args())

        assert options.dataset_id == "fundamental6"
        assert options.max_templates_per_field == 8
        assert options.max_templates_per_family == 2
        assert options.truncation == 0.08
        assert options.start_date == "2020-01-01"
        assert options.end_date == "2020-12-31"

    def test_result_write_and_field_fetch_options_from_args(self) -> None:
        class _Args:
            dataset_id = "model51"
            output = "results.json"
            auto_update_blacklist = True
            page_size = "100"
            region = "USA"
            universe = "TOP1000"
            instrument_type = "EQUITY"
            delay = "2"

        assert ResultWriteOptions.from_args(_Args()) == ResultWriteOptions(
            dataset_id="model51",
            output_path="results.json",
            auto_update_blacklist=True,
        )
        assert FieldFetchOptions.from_args(_Args()) == FieldFetchOptions(
            dataset_id="model51",
            page_size=100,
            region="USA",
            universe="TOP1000",
            instrument_type="EQUITY",
            delay=2,
        )


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
