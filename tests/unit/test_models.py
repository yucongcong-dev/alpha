"""模型数据类单元测试。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import time

import pytest

from alpha.models.domain import FieldTestContext, FieldTestResult
from alpha.models.domain_serializers import serialize_field_test_result
from alpha.models.io_types import RunFilters
from alpha.models.runtime import (
    ExecutionMetrics,
    ExecutionState,
    HistoricalRunState,
    ResultLedgerState,
    RuntimeConcurrencyState,
)
from alpha.models.runtime_options import (
    ApiClientOptions,
    BootstrapFieldOptions,
    FieldFetchOptions,
    FieldSelectionOptions,
    ResultWriteOptions,
    RunConfigSnapshotOptions,
    RunLoopOptions,
    SchedulerControlOptions,
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
            region = "USA"
            universe = "TOP3000"
            instrument_type = "EQUITY"
            delay = 1
            decay = 7
            neutralization = "SUBINDUSTRY"
            truncation = 0.08
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
            auto_update_blacklist_mode = "staging"
            strategy_profile = "refine"
            page_size = "100"
            region = "USA"
            universe = "TOP1000"
            instrument_type = "EQUITY"
            delay = 2
            top_fields_by_feedback = "7"
            offset = "3"
            limit = "12"
            check_submission_retries = "4"

        assert ResultWriteOptions.from_args(_Args()) == ResultWriteOptions(
            dataset_id="model51",
            output_path="results.json",
            auto_update_blacklist=True,
            auto_update_blacklist_mode="staging",
        )
        assert FieldFetchOptions.from_args(_Args()) == FieldFetchOptions(
            dataset_id="model51",
            page_size=100,
            region="USA",
            universe="TOP1000",
            instrument_type="EQUITY",
            delay=2,
        )
        assert BootstrapFieldOptions.from_args(_Args()) == BootstrapFieldOptions(
            dataset_id="model51",
            check_submission_retries=4,
            fetch=FieldFetchOptions(
                dataset_id="model51",
                page_size=100,
                region="USA",
                universe="TOP1000",
                instrument_type="EQUITY",
                delay=2,
            ),
            selection=FieldSelectionOptions(
                top_fields_by_feedback=7,
                offset=3,
                limit=12,
            ),
        )
        snapshot_options = RunConfigSnapshotOptions.from_args(_Args())
        assert snapshot_options.run_name == "default"
        assert snapshot_options.dataset_id == "model51"
        assert snapshot_options.page_size == 100
        assert snapshot_options.check_submission_retries == 4
        assert snapshot_options.auto_update_blacklist is True
        assert snapshot_options.auto_update_blacklist_mode == "staging"
        assert snapshot_options.strategy_profile == "refine"

    def test_scheduler_control_options_from_args(self) -> None:
        class _Args:
            queue_busy_cooldown_seconds = "5.5"
            queue_busy_retry_limit = "3"
            sleep_between_fields = "0.25"
            stop_after_submittable = "2"

        assert SchedulerControlOptions.from_args(_Args()) == SchedulerControlOptions(
            queue_busy_cooldown_seconds=5.5,
            queue_busy_retry_limit=3,
            sleep_between_fields=0.25,
            stop_after_submittable=2,
        )

    def test_run_loop_options_from_args(self) -> None:
        class _Args:
            dataset_id = "fundamental6"
            output = "results.json"
            auto_update_blacklist = True
            region = "USA"
            universe = "TOP1000"
            instrument_type = "EQUITY"
            delay = 1
            decay = 6
            neutralization = "SUBINDUSTRY"
            truncation = 0.08
            pasteurization = "ON"
            unit_handling = "VERIFY"
            nan_handling = "OFF"
            max_trade = "OFF"
            language = "FASTEXPR"
            start_date = None
            end_date = None
            simulation_create_retries = 2
            simulation_poll_retries = 3
            simulation_max_polls = 4
            simulation_max_wait_seconds = 5
            simulation_max_pending_cycles = 6
            simulation_max_queue_seconds = 7
            check_submission_retries = 8
            min_sharpe = 1.25
            min_fitness = 1.0
            min_turnover = 0.01
            max_turnover = 0.7
            max_weight = 0.1
            max_templates_per_field = 9
            max_templates_per_family = 10
            legacy_similarity_penalty = 11
            template_library_file = "templates.json"
            include_fields_file = ""
            include_templates_file = ""
            queue_busy_cooldown_seconds = 12
            queue_busy_retry_limit = 13
            sleep_between_fields = 0.25
            stop_after_submittable = 14
            field_template_batch_size = "15"
            full_run = True

        options = RunLoopOptions.from_args(_Args())

        assert options.field_template_batch_size == 15
        assert options.template_build.template_library_file == "templates.json"
        assert options.simulation_stage.check_submission_retries == 8
        assert options.result_write.output_path == "results.json"
        assert options.scheduler.stop_after_submittable == 14
        assert options.full_run is True


# ============================================================================
# ExecutionState 测试
# ============================================================================


class TestExecutionState:
    """测试执行状态"""

    def test_default_state_is_empty(self) -> None:
        state = ExecutionState.create()
        assert state.result_ledger.results == []
        assert state.attempted_keys == set()
        assert state.template_stats == {}
        assert state.future_queue.pending_futures == {}
        assert state.queue_retry_state.retry_counts == {}
        assert state.last_submission_at == 0.0

    def test_custom_values(self) -> None:
        result = FieldTestResult(
            field_id="alpha1",
            field_type="MATRIX",
            field_name="alpha1",
            template_name="tpl",
            status="simulated",
        )
        attempted_key = ("field_1", "tpl", "rank(field_1)", "settings")
        state = ExecutionState.create(
            initial_results=[result],
            attempted_keys={attempted_key},
            template_stats={"tmpl": {"count": 1}},
            last_submission_at=123.0,
        )
        assert len(state.result_ledger.results) == 1
        assert attempted_key in state.attempted_keys
        assert state.template_stats["tmpl"]["count"] == 1
        assert state.last_submission_at == 123.0

    def test_result_ledger_export_and_metrics(self) -> None:
        result = FieldTestResult(
            field_id="field_1",
            field_type="MATRIX",
            field_name="field_1",
            template_name="tpl",
            status="simulated",
            submittable=True,
            expression="rank(field_1)",
        )
        ledger = ResultLedgerState(results=[result])

        assert isinstance(ledger.metrics, ExecutionMetrics)
        assert ledger.current_run_submittable_count == 1


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
            template_role="default_seed",
            template_activation_scope="broad",
            expression="rank(ts_mean(sales, 20))",
            status="simulated",
            submittable=True,
        )
        assert result.submittable
        assert result.status == "simulated"
        assert result.field_id == "sales"
        assert serialize_field_test_result(result)["template_role"] == "default_seed"
        assert serialize_field_test_result(result)["template_activation_scope"] == "broad"

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
