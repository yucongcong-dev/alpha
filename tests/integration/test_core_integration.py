"""
核心模块集成测试

测试 core 包中各模块之间的真实协作流程，包括：
- simulation ↔ scheduler 的拥塞信号传递
- executor ↔ simulation 的历史跳过逻辑
- 数据类在跨模块场景中的一致性
- drain_completed_futures 的完整编排流程
"""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

from alpha.core.executor import should_skip_expression_by_history, should_skip_field
from alpha.core.scheduler import (
    apply_congestion_cooldown,
    drain_completed_futures,
    handle_completed_future,
    register_queue_busy_field,
)
from alpha.core.simulation import build_failure_result, summarize_failure
from alpha.models.base import (
    ExecutionState,
    FieldTestContext,
    FieldTestResult,
    FutureCompletionContext,
    RunFilters,
    RuntimeConcurrencyState,
    TemplateBuildContext,
)
from alpha.utils.helpers import first_non_empty
from tests.conftest import MockArgs

# ============================================================================
# simulation ↔ scheduler 拥塞信号传递测试
# ============================================================================


class TestCongestionSignalPropagation:
    """
    测试 simulation 失败 → scheduler 拥塞检测 → 冷却应用的完整信号链。

    这是核心集成场景：当 simulation 返回特定的拥塞错误时，
    scheduler 应该能检测到并应用拥塞冷却。
    """

    CONGESTION_MESSAGES: ClassVar[list[str]] = [
        "CONCURRENT_SIMULATION_LIMIT_EXCEEDED",
        "queued too long for resource",
        "rate limited - please slow down",
    ]

    def test_queue_budget_sets_field_id(
        self,
        scheduler_args: MockArgs,
    ) -> None:
        """queue budget 消息应设置 queue_busy_field_id（而非 congestion_detected）。"""
        future = MagicMock()
        future.result.return_value = FieldTestResult(
            field_id="test_field",
            field_type="MATRIX",
            field_name="test",
            template_name="test_tpl",
            status="error",
            submittable=False,
            expression="rank(test)",
            message="queue budget exceeded",
            failed_stage="simulation",
        )
        completion_ctx = FutureCompletionContext(
            args=scheduler_args,
            settings_fingerprint="abc",
            template_library_fingerprint="def",
            run_config={"key": "val"},
        )
        execution_state = ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={
                future: {
                    "field_id": "test_field",
                    "field_type": "MATRIX",
                    "field_name": "test",
                    "template_name": "test_tpl",
                    "expression": "rank(test)",
                    "settings_fingerprint": "abc",
                }
            },
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        )

        with (
            patch("alpha.core.scheduler.dump_results_incremental"),
        ):
            _stats, congestion_detected, queue_busy_field_id = handle_completed_future(
                future,
                completion_ctx=completion_ctx,
                execution_state=execution_state,
            )

        assert congestion_detected is False
        assert queue_busy_field_id == "test_field"
        assert len(execution_state.results) == 1

    @pytest.mark.parametrize("congestion_msg", CONGESTION_MESSAGES)
    def test_congestion_detected_from_failure_message(
        self,
        congestion_msg: str,
        scheduler_args: MockArgs,
    ) -> None:
        """
        验证三种拥塞消息都能被 handle_completed_future 正确检测。
        """
        future = MagicMock()
        future.result.return_value = FieldTestResult(
            field_id="test_field",
            field_type="MATRIX",
            field_name="test",
            template_name="test_tpl",
            status="error",
            submittable=False,
            expression="rank(test)",
            message=congestion_msg,
            failed_stage="simulation",
        )

        completion_ctx = FutureCompletionContext(
            args=scheduler_args,
            settings_fingerprint="abc",
            template_library_fingerprint="def",
            run_config={"key": "val"},
        )

        execution_state = ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={
                future: {
                    "field_id": "test_field",
                    "field_type": "MATRIX",
                    "field_name": "test",
                    "template_name": "test_tpl",
                    "expression": "rank(test)",
                    "settings_fingerprint": "abc",
                }
            },
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        )

        with (
            patch("alpha.core.scheduler.dump_results_incremental"),
        ):
            _stats, congestion_detected, _queue_busy_field_id = handle_completed_future(
                future,
                completion_ctx=completion_ctx,
                execution_state=execution_state,
            )

        assert congestion_detected is True
        assert len(execution_state.results) == 1


class TestQueueBusyFieldRegistration:
    """
    测试队列拥塞字段的注册、跳过与 cooling 联动。

    验证 register_queue_busy_field 和 apply_congestion_cooldown
    在不同条件下的协作行为。
    """

    def test_register_and_cool_in_sequence(
        self,
        scheduler_args: MockArgs,
        runtime_state_max_workers_5: RuntimeConcurrencyState,
    ) -> None:
        """字段反复拥塞 → 加入跳过集合 → 应用冷却。"""
        counts: dict[str, int] = {}
        skipped: set[str] = set()

        # 反复注册同一字段
        for _ in range(scheduler_args.field_queue_busy_skip_after):
            register_queue_busy_field("busy_field", scheduler_args, counts, skipped)

        assert "busy_field" in skipped
        assert counts["busy_field"] == scheduler_args.field_queue_busy_skip_after

        # 检测到拥塞后应用冷却
        apply_congestion_cooldown(scheduler_args, runtime_state_max_workers_5)
        assert runtime_state_max_workers_5.runtime_max_workers == 1
        assert runtime_state_max_workers_5.is_cooling_down()

    def test_different_fields_independent_skip(
        self,
        scheduler_args: MockArgs,
    ) -> None:
        """不同字段的拥塞计数互不影响。"""
        counts: dict[str, int] = {}
        skipped: set[str] = set()

        args = MockArgs(
            queue_busy_cooldown_seconds=180,
            field_queue_busy_skip_after=2,
            sleep_between_fields=2.0,
        )

        register_queue_busy_field("field_a", args, counts, skipped)
        register_queue_busy_field("field_b", args, counts, skipped)
        # field_a 再触发一次，应被跳过
        register_queue_busy_field("field_a", args, counts, skipped)

        assert "field_a" in skipped
        assert "field_b" not in skipped
        assert counts["field_a"] == 2
        assert counts["field_b"] == 1


# ============================================================================
# executor ↔ simulation 历史跳过集成测试
# ============================================================================


class TestHistorySkipIntegration:
    """
    测试 executor 的历史跳过逻辑与 simulation 结果的集成。

    验证 should_skip_expression_by_history 在不同失败模式下的行为。
    """

    def test_skip_when_sharpe_and_fitness_both_negative(
        self,
        failed_field_test_result: FieldTestResult,
    ) -> None:
        """LOW_SHARPE 和 LOW_FITNESS 都为负数时应跳过。"""
        assert should_skip_expression_by_history(
            "sales",
            "ts_mean_20",
            "rank(ts_mean(sales, 20))",
            [failed_field_test_result],
        )

    def test_no_skip_when_submittable(
        self,
        sample_field_test_result: FieldTestResult,
    ) -> None:
        """历史上已有可提交结果时不跳过。"""
        assert not should_skip_expression_by_history(
            "sales",
            "ts_mean_20",
            "rank(ts_mean(sales, 20))",
            [sample_field_test_result],
        )

    def test_no_skip_when_different_field(self) -> None:
        """不同字段不应被跳过。"""
        result = FieldTestResult(
            field_id="other_field",
            field_type="MATRIX",
            field_name="other",
            template_name="ts_mean_20",
            expression="rank(ts_mean(sales, 20))",
            submittable=False,
            failed_checks=[
                {"name": "LOW_SHARPE", "value": -0.1},
                {"name": "LOW_FITNESS", "value": -0.2},
            ],
        )
        assert not should_skip_expression_by_history(
            "sales",
            "ts_mean_20",
            "rank(ts_mean(sales, 20))",
            [result],
        )

    def test_skip_when_concentrated_weight_and_low_sub_universe(self) -> None:
        """CONCENTRATED_WEIGHT 和 LOW_SUB_UNIVERSE_SHARPE 同时存在时跳过。"""
        result = FieldTestResult(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="ts_mean_20",
            expression="rank(ts_mean(sales, 20))",
            submittable=False,
            failed_checks=[
                {"name": "CONCENTRATED_WEIGHT", "value": 0.8},
                {"name": "LOW_SUB_UNIVERSE_SHARPE", "value": 0.5},
            ],
        )
        assert should_skip_expression_by_history(
            "sales",
            "ts_mean_20",
            "rank(ts_mean(sales, 20))",
            [result],
        )


class TestFieldSkipIntegration:
    """
    测试 should_skip_field 与 RunFilters 的集成。

    验证字段跳过逻辑在各种过滤条件下的行为。
    """

    def test_skip_by_queue(self) -> None:
        """因队列拥塞被跳过。"""
        filters = RunFilters()
        assert should_skip_field("field_1", "test", filters, {"field_1"})

    def test_skip_by_include_filter(self) -> None:
        """不在 include_fields 中被跳过。"""
        filters = RunFilters(include_fields={"allowed_field"})
        assert should_skip_field("field_1", "test", filters, set())

    def test_skip_by_include_filter_matches_name(self) -> None:
        """字段名匹配 include_fields 时不被跳过。"""
        filters = RunFilters(include_fields={"test_name"})
        assert not should_skip_field("field_1", "test_name", filters, set())

    def test_skip_by_exclude_filter(self) -> None:
        """在 exclude_fields 中被跳过。"""
        filters = RunFilters(exclude_fields={"field_1"})
        assert should_skip_field("field_1", "test", filters, set())

    def test_not_skipped_by_default(self) -> None:
        """默认过滤器不过滤任何字段。"""
        filters = RunFilters()
        assert not should_skip_field("any_field", "any_name", filters, set())


# ============================================================================
# drain_completed_futures 编排流程测试
# ============================================================================


class TestDrainCompletedFuturesFlow:
    """
    测试 drain_completed_futures 的完整编排流程。

    这是 scheduler 的核心消费循环，验证多个 future 的消费、
    拥塞检测和冷却应用是否按预期协作。
    """

    def test_drain_single_success_future(
        self,
        scheduler_args: MockArgs,
        empty_execution_state: ExecutionState,
        runtime_state_max_workers_5: RuntimeConcurrencyState,
    ) -> None:
        """消费单个成功完成的 future。"""
        future = MagicMock()
        result = FieldTestResult(
            field_id="f1",
            field_type="MATRIX",
            field_name="test",
            template_name="tpl",
            status="simulated",
            submittable=True,
            expression="rank(test)",
        )
        future.result.return_value = result

        empty_execution_state.pending_futures = {
            future: {
                "field_id": "f1",
                "field_type": "MATRIX",
                "field_name": "test",
                "template_name": "tpl",
                "expression": "rank(test)",
                "settings_fingerprint": "abc",
            }
        }

        with (
            patch("alpha.core.scheduler.dump_results_incremental"),
            patch("alpha.core.scheduler.is_informative_result", return_value=True),
            patch(
                "alpha.core.scheduler.result_identity",
                return_value=("f1", "tpl", "rank(test)", "abc"),
            ),
        ):
            _stats = drain_completed_futures(
                completed_futures=[future],
                execution_state=empty_execution_state,
                args=scheduler_args,
                settings_fingerprint="abc",
                template_library_fingerprint="def",
                run_config={"key": "val"},
                runtime_state=runtime_state_max_workers_5,
            )

        assert len(empty_execution_state.results) == 1
        assert empty_execution_state.results[0].submittable is True
        assert not runtime_state_max_workers_5.is_cooling_down()

    def test_drain_congestion_future_triggers_cooldown(
        self,
        scheduler_args: MockArgs,
        empty_execution_state: ExecutionState,
        runtime_state_max_workers_5: RuntimeConcurrencyState,
    ) -> None:
        """消费拥塞 future 应触发冷却。"""
        future = MagicMock()
        result = FieldTestResult(
            field_id="f1",
            field_type="MATRIX",
            field_name="test",
            template_name="tpl",
            status="error",
            submittable=False,
            expression="rank(test)",
            message="CONCURRENT_SIMULATION_LIMIT_EXCEEDED",
            failed_stage="simulation",
        )
        future.result.return_value = result

        empty_execution_state.pending_futures = {
            future: {
                "field_id": "f1",
                "field_type": "MATRIX",
                "field_name": "test",
                "template_name": "tpl",
                "expression": "rank(test)",
                "settings_fingerprint": "abc",
            }
        }

        with (
            patch("alpha.core.scheduler.dump_results_incremental"),
            patch("alpha.core.scheduler.is_informative_result", return_value=False),
        ):
            drain_completed_futures(
                completed_futures=[future],
                execution_state=empty_execution_state,
                args=scheduler_args,
                settings_fingerprint="abc",
                template_library_fingerprint="def",
                run_config=None,
                runtime_state=runtime_state_max_workers_5,
            )

        assert runtime_state_max_workers_5.is_cooling_down()
        assert runtime_state_max_workers_5.runtime_max_workers == 1

    def test_drain_future_exception_handling(
        self,
        scheduler_args: MockArgs,
        empty_execution_state: ExecutionState,
        runtime_state_max_workers_5: RuntimeConcurrencyState,
    ) -> None:
        """future 抛异常时创建失败结果，不触发冷却。"""
        future = MagicMock()
        future.result.side_effect = RuntimeError("worker crash")

        empty_execution_state.pending_futures = {
            future: {
                "field_id": "f1",
                "field_type": "MATRIX",
                "field_name": "test",
                "template_name": "tpl",
                "expression": "rank(test)",
                "settings_fingerprint": "abc",
            }
        }

        with (
            patch("alpha.core.scheduler.dump_results_incremental"),
            patch("alpha.core.scheduler.is_informative_result", return_value=False),
        ):
            drain_completed_futures(
                completed_futures=[future],
                execution_state=empty_execution_state,
                args=scheduler_args,
                settings_fingerprint="abc",
                template_library_fingerprint="def",
                run_config=None,
                runtime_state=runtime_state_max_workers_5,
            )

        assert len(empty_execution_state.results) == 1
        assert empty_execution_state.results[0].status == "error"
        assert empty_execution_state.results[0].failed_stage == "worker"
        assert not runtime_state_max_workers_5.is_cooling_down()


# ============================================================================
# 数据类跨模块一致性测试
# ============================================================================


class TestContextConsistency:
    """
    测试上下文数据类在跨模块场景中的一致性。

    确保 FieldTestContext、TemplateBuildContext、FutureCompletionContext
    的工厂方法产生一致的 FieldTestResult。
    """

    def test_field_test_context_failure_then_success_consistency(
        self,
        basic_test_context: FieldTestContext,
    ) -> None:
        """failure() → success() 链：上下文字段在两种路径下保持一致。"""
        fail_result = basic_test_context.failure(
            failed_stage="simulation",
            message="Network error",
        )
        assert fail_result.field_id == "sales"
        assert fail_result.field_type == "MATRIX"
        assert fail_result.template_name == "ts_mean_20"
        assert fail_result.settings_fingerprint == "abc123"
        assert fail_result.submittable is False

        success_result = basic_test_context.success(
            simulation_id="sim_1",
            alpha_id="alpha_1",
            submittable=True,
            submitted=True,
            message="submitted",
            status="submitted",
        )
        assert success_result.field_id == "sales"
        assert success_result.field_type == "MATRIX"
        assert success_result.template_name == "ts_mean_20"
        assert success_result.submittable is True
        assert success_result.submitted is True

    def test_future_completion_context_fingerprints_preserved(
        self,
        scheduler_args: MockArgs,
    ) -> None:
        """FutureCompletionContext 保持 fingerprints 不变。"""
        ctx = FutureCompletionContext(
            args=scheduler_args,
            settings_fingerprint="s_fp_001",
            template_library_fingerprint="tl_fp_001",
            run_config={"mode": "full"},
        )
        assert ctx.settings_fingerprint == "s_fp_001"
        assert ctx.template_library_fingerprint == "tl_fp_001"
        assert ctx.run_config == {"mode": "full"}

    def test_template_build_context_defaults(self) -> None:
        """TemplateBuildContext 默认值正确。"""
        ctx = TemplateBuildContext()
        assert ctx.all_fields == []
        assert ctx.template_library == {}
        assert ctx.field_feedback == {}
        assert ctx.global_failed_check_counts == {}
        assert ctx.include_templates == set()
        assert ctx.exclude_templates == set()
        assert ctx.use_dataset_heuristics is False


# ============================================================================
# 端到端场景：summarize_failure → build_failure_result 链路
# ============================================================================


class TestFailureReportingPipeline:
    """
    测试失败报告管道的端到端行为。

    从 API 错误负载 → summarize_failure → build_failure_result 的完整链路。
    """

    def test_api_error_to_failure_result(self) -> None:
        """API 错误消息经 summarize 后嵌入 FieldTestResult。"""
        api_error = {"detail": "Invalid expression: unexpected token"}
        summary = summarize_failure(api_error)
        assert summary == "Invalid expression: unexpected token"

        result = build_failure_result(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="ts_mean_20",
            simulation_id=None,
            alpha_id=None,
            expression="rank(ts_mean(sales, 20))",
            settings_fingerprint="abc",
            template_library_fingerprint="def",
            failed_stage="simulation",
            message=summary,
        )
        assert result.status == "error"
        assert result.message == "Invalid expression: unexpected token"
        assert result.submittable is False

    def test_check_failure_to_failure_result(self) -> None:
        """检查失败消息经 summarize 后嵌入 FieldTestResult。"""
        check_error = {
            "checks": [
                {"name": "LOW_SHARPE", "result": "FAIL", "value": 0.3, "limit": 1.0},
                {"name": "LOW_FITNESS", "result": "FAIL", "value": 0.5, "limit": 1.0},
            ]
        }
        summary = summarize_failure(check_error)
        assert "LOW_SHARPE" in summary
        assert "LOW_FITNESS" in summary

        result = build_failure_result(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="ts_mean_20",
            simulation_id="sim_1",
            alpha_id="alpha_1",
            expression="rank(ts_mean(sales, 20))",
            settings_fingerprint="abc",
            template_library_fingerprint="def",
            failed_stage="checksubmit",
            message=summary,
            failed_checks=[
                {"name": "LOW_SHARPE", "value": 0.3, "limit": 1.0},
                {"name": "LOW_FITNESS", "value": 0.5, "limit": 1.0},
            ],
        )
        assert result.failed_stage == "checksubmit"
        assert result.failed_checks is not None
        assert len(result.failed_checks) == 2


# ============================================================================
# first_non_empty 在跨模块上下文中的一致性测试
# ============================================================================


class TestFirstNonEmptyCrossModule:
    """
    测试 first_non_empty 在跨模块调用中的一致性。

    该函数被 simulation、executor、scheduler 等多个模块使用，
    需要保证其行为在不同调用模式下一致。
    """

    def test_simulation_usage_pattern(self) -> None:
        """模拟 simulation 中的典型使用模式。"""
        # extract_alpha_id 内部使用模式
        result = first_non_empty(None, "", "alpha_123")
        assert result == "alpha_123"

    def test_executor_usage_pattern(self) -> None:
        """模拟 executor 中的典型使用模式（field id 获取）。"""
        result = first_non_empty(None, "UNKNOWN")
        assert result == "UNKNOWN"

    def test_handles_api_null_variants(self) -> None:
        """处理 API 返回的各种空值变体。"""
        assert first_non_empty(None, "", [], {}, "real_value") == "real_value"
        assert first_non_empty(None, "", [], {}) is None
