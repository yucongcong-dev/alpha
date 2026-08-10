"""模型数据类单元测试。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import time
from types import SimpleNamespace

import pytest

from alpha.config.application import ApplicationConfig
from alpha.config.application_sections import (
    DatasetConfig,
    ExecutionConfig,
    PlanningConfig,
    QualityConfig,
    SimulationConfig,
)
from alpha.models.domain import FailedCheck, FieldTestContext, FieldTestResult
from alpha.models.domain_serializers import serialize_field_test_result
from alpha.models.io_types import RunFilters, RunPaths
from alpha.models.runtime_options import (
    ApiClientOptions,
    BootstrapFieldOptions,
    FieldFetchOptions,
    FieldSelectionOptions,
    RunLoopOptions,
    SchedulerControlOptions,
)
from alpha.runtime.concurrency import RuntimeConcurrencyState
from alpha.runtime.contexts import HistoricalRunState
from alpha.runtime.result_ledger import ExecutionMetrics, ResultLedgerState
from alpha.runtime.state import ExecutionState


def _application_config(**overrides: object) -> ApplicationConfig:
    args = SimpleNamespace(**{"dataset_id": "test_dataset", **overrides})
    paths = RunPaths(
        results_dir="runs",
        log_file="run.log",
        state_file="state.json",
        checkpoint_file="interrupt.json",
        output=str(overrides.get("output", "")),
        template_library_file=str(overrides.get("template_library_file", "")),
        fields_cache_file=str(overrides.get("fields_cache_file", "")),
        creds_file=str(overrides.get("creds_file", "")),
        creds_key_file=str(overrides.get("creds_key_file", "")),
        include_fields_file=str(overrides.get("include_fields_file", "")),
        exclude_fields_file=str(overrides.get("exclude_fields_file", "")),
        include_templates_file=str(overrides.get("include_templates_file", "")),
        exclude_templates_file=str(overrides.get("exclude_templates_file", "")),
    )
    return ApplicationConfig.from_args(args, paths)


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
    """测试从权威 ApplicationConfig 提取窄配置。"""

    def test_api_client_options_from_config(self) -> None:
        config = _application_config(
            min_request_interval="0.25",
            rate_limit_max_retries="7",
            login_retries=3,
        )
        assert ApiClientOptions.from_config(config) == ApiClientOptions(
            min_request_interval=0.25,
            rate_limit_max_retries=7,
            login_retries=3,
        )

    def test_result_write_and_field_fetch_options_from_config(self) -> None:
        config = _application_config(
            dataset_id="model51",
            output="results.json",
            strategy_profile="refine",
            page_size="100",
            region="USA",
            universe="TOP1000",
            instrument_type="EQUITY",
            delay=2,
            top_fields_by_feedback="7",
            offset="3",
            limit="12",
            check_submission_retries="4",
        )
        assert FieldFetchOptions.from_config(config) == FieldFetchOptions(
            dataset_id="model51",
            page_size=100,
            region="USA",
            universe="TOP1000",
            instrument_type="EQUITY",
            delay=2,
        )
        assert BootstrapFieldOptions.from_config(config) == BootstrapFieldOptions(
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

    def test_scheduler_control_options_from_config(self) -> None:
        config = _application_config(
            queue_busy_cooldown_seconds="5.5",
            queue_busy_retry_limit="3",
            sleep_between_fields="0.25",
        )
        assert SchedulerControlOptions.from_config(config) == SchedulerControlOptions(
            queue_busy_cooldown_seconds=5.5,
            queue_busy_retry_limit=3,
            sleep_between_fields=0.25,
        )

    def test_run_loop_options_read_canonical_config_sections(self) -> None:
        config = _application_config(
            dataset_id="model51",
            instrument_type="EQUITY",
            region="USA",
            universe="TOP1000",
            delay=1,
            decay=6,
            simulation_poll_retries=4,
            simulation_max_wait_seconds=0.5,
            simulation_max_queue_seconds=0.75,
            min_sharpe=1.5,
        )

        options = RunLoopOptions.from_config(config)

        assert options.template_build.dataset_id == "model51"
        assert options.simulation_stage.instrument_type == "EQUITY"
        assert options.simulation_stage.decay == 6
        assert options.simulation_stage.simulation_poll_retries == 4
        assert options.simulation_stage.simulation_max_wait_seconds == 0.5
        assert options.simulation_stage.simulation_max_queue_seconds == 0.75
        assert options.simulation_stage.min_sharpe == 1.5


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("queue_busy_retry_limit", -1, "cannot be negative"),
        ("simulation_max_polls", 0, "must be positive"),
        ("simulation_max_wait_seconds", float("nan"), "must be finite"),
        ("max_concurrent_simulations", 0, "must be positive"),
    ],
)
def test_execution_config_rejects_invalid_numeric_ranges(
    field_name: str,
    value: int | float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ExecutionConfig.from_args(SimpleNamespace(**{field_name: value}))


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("dataset_id", "", "dataset_id cannot be empty"),
        ("region", "", "region cannot be empty"),
        ("universe", "", "universe cannot be empty"),
        ("instrument_type", "CRYPTO", "instrument_type must be one of"),
        ("delay", -1, "delay cannot be negative"),
    ],
)
def test_dataset_config_rejects_invalid_values(
    field_name: str,
    value: str | int,
    message: str,
) -> None:
    values: dict[str, object] = {
        "dataset_id": "pv1",
        "region": "USA",
        "universe": "TOP3000",
        "instrument_type": "EQUITY",
        "delay": 1,
    }
    values[field_name] = value

    with pytest.raises(ValueError, match=message):
        DatasetConfig.from_args(SimpleNamespace(**values))


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("decay", -1, "decay cannot be negative"),
        ("truncation", float("inf"), "truncation must be finite"),
        ("truncation", 1.01, "truncation must be between 0 and 1"),
        ("backfill_window", 0, "backfill_window must be positive"),
        ("neutralization", "NOT_A_MODE", "neutralization must be one of"),
        ("pasteurization", "MAYBE", "pasteurization must be one of"),
        ("unit_handling", "ON", "unit_handling must be one of"),
        ("language", "PYTHON", "language must be one of"),
        ("start_date", "2026-02-30", "start_date must use YYYY-MM-DD format"),
    ],
)
def test_simulation_config_rejects_invalid_values(
    field_name: str,
    value: str | int | float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        SimulationConfig.from_args(SimpleNamespace(**{field_name: value}))


def test_simulation_config_rejects_reversed_date_range() -> None:
    with pytest.raises(ValueError, match="start_date cannot be after end_date"):
        SimulationConfig.from_args(SimpleNamespace(start_date="2026-02-01", end_date="2026-01-31"))


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("max_total_simulations", -1, "cannot be negative"),
        ("limit", -1, "cannot be negative"),
        ("page_size", 0, "must be positive"),
        ("field_template_batch_size", 0, "must be positive"),
        ("sleep_between_fields", float("nan"), "must be finite"),
    ],
)
def test_planning_config_rejects_invalid_numeric_ranges(
    field_name: str,
    value: int | float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        PlanningConfig.from_args(SimpleNamespace(**{field_name: value}))


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("min_sharpe", -0.1, "cannot be negative"),
        ("max_turnover", 0.0, "must be positive"),
        ("max_weight", 2.0, "at most 1"),
        ("max_weight", float("inf"), "must be finite"),
    ],
)
def test_quality_config_rejects_invalid_numeric_ranges(
    field_name: str,
    value: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        QualityConfig.from_args(SimpleNamespace(**{field_name: value}))


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
        assert ledger.submittable_count == 1


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
                FailedCheck(name="LOW_SHARPE", value=-0.1),
                FailedCheck(name="LOW_FITNESS", value=-0.2),
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
