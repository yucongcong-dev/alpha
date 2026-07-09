"""
端到端集成测试

测试核心业务流程的完整链路，包括：
- 配置加载和验证
- 运行上下文初始化
- 字段测试和结果处理
- 数据类序列化/反序列化
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from alpha.core.result_processing import apply_completed_result
from alpha.models.domain import (
    FailedCheck,
    FieldTestContext,
    FieldTestResult,
    TemplateLibraryItem,
)
from alpha.models.domain_serializers import (
    serialize_field_test_result,
    serialize_template_library_item,
)
from alpha.models.runtime import (
    ExecutionState,
    PendingFutureContext,
    RuntimeConcurrencyState,
)


class TestDataClassSerialization:
    """
    测试核心数据类的序列化/反序列化兼容性。
    确保数据类可以正确地转换为字典并存储到文件中。
    """

    def test_field_test_result_serialization(self):
        """测试FieldTestResult序列化"""
        failed_check = FailedCheck(name="LOW_SHARPE", value=0.3, limit=1.0, result="FAIL")
        result = FieldTestResult(
            field_id="sales",
            field_type="MATRIX",
            field_name="sales",
            template_name="ts_mean_20",
            expression="rank(ts_mean(sales, 20))",
            submittable=True,
            status="simulated",
            failed_checks=[failed_check],
        )

        result_dict = serialize_field_test_result(result)
        assert result_dict["field_id"] == "sales"
        assert result_dict["field_type"] == "MATRIX"
        assert result_dict["submittable"] is True
        assert len(result_dict.get("failed_checks", [])) == 1
        assert result_dict["failed_checks"][0]["name"] == "LOW_SHARPE"

        json_str = json.dumps(result_dict)
        loaded_dict = json.loads(json_str)
        assert loaded_dict["field_id"] == "sales"

    def test_field_test_context_to_result(self):
        """测试FieldTestContext生成FieldTestResult"""
        ctx = FieldTestContext(
            field_id="test_field",
            field_type="MATRIX",
            field_name="test",
            template_name="test_tpl",
            expression="rank(test)",
            settings_fingerprint="abc123",
        )

        success_result = ctx.success(
            simulation_id="sim_1",
            alpha_id="alpha_1",
            submittable=True,
            submitted=True,
            message="submitted",
            status="submitted",
        )
        assert success_result.field_id == "test_field"
        assert success_result.submittable is True
        assert success_result.submitted is True

        fail_result = ctx.failure(
            failed_stage="simulation",
            message="Network error",
        )
        assert fail_result.status == "error"
        assert fail_result.submittable is False
        assert fail_result.failed_stage == "simulation"

    def test_template_library_item_serialization(self):
        """测试TemplateLibraryItem序列化"""
        item = TemplateLibraryItem(
            name="ts_mean_20",
            expression="rank(ts_mean({field}, 20))",
            priority=1,
            family="mean",
            stage="refine",
            metadata={"category": "technical"},
        )

        assert item.name == "ts_mean_20"
        assert item.expression == "rank(ts_mean({field}, 20))"
        assert item.priority == 1
        assert item.family == "mean"
        assert item.stage == "refine"

        item_dict = serialize_template_library_item(item)

        json_str = json.dumps(item_dict)
        loaded = json.loads(json_str)
        assert loaded["family"] == "mean"
        assert loaded["stage"] == "refine"


class TestExecutionStateManagement:
    """
    测试执行状态管理的核心功能：
    - 结果添加和统计
    - 历史跳过逻辑
    - 并发状态管理
    """

    def test_execution_state_result_management(self):
        """测试执行状态的结果管理"""
        state = ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        )

        result1 = FieldTestResult(
            field_id="field_1",
            field_type="MATRIX",
            field_name="test1",
            template_name="tpl",
            expression="rank(test1)",
            submittable=True,
            status="simulated",
        )
        result2 = FieldTestResult(
            field_id="field_2",
            field_type="MATRIX",
            field_name="test2",
            template_name="tpl",
            expression="rank(test2)",
            submittable=False,
            status="error",
        )

        state.results.append(result1)
        state.results.append(result2)

        assert len(state.results) == 2

    def test_execution_state_pending_futures(self):
        """测试执行状态的pending futures管理"""
        state = ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        )

        ctx = PendingFutureContext(
            field_id="test_field",
            field_type="MATRIX",
            field_name="test",
            template_name="test_tpl",
            expression="rank(test)",
            settings_fingerprint="abc",
        )

        mock_future = MagicMock()
        state.pending_futures[mock_future] = ctx

        assert len(state.pending_futures) == 1
        assert "test_field" in str(next(iter(state.pending_futures.values())).field_id)

    def test_runtime_concurrency_state(self):
        """测试运行时并发状态管理"""
        state = RuntimeConcurrencyState(max_workers=5, runtime_max_workers=5)

        assert state.runtime_max_workers == 5
        assert state.max_workers == 5
        assert not state.is_cooling_down()

        state.cooldown_until = 9999999999.0
        state.runtime_max_workers = 1
        assert state.is_cooling_down()
        assert state.runtime_max_workers == 1


class TestResultProcessingFlow:
    """
    测试结果处理流程的核心功能：
    - 结果持久化决策
    - 结果应用和统计更新
    """

    def test_apply_completed_result(self):
        """测试应用完成结果"""
        from alpha.models.runtime import FutureCompletionContext, ResultWriteOptions

        state = ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        )
        result = FieldTestResult(
            field_id="test_field",
            field_type="MATRIX",
            field_name="test",
            template_name="test_tpl",
            expression="rank(test)",
            submittable=True,
            status="simulated",
        )

        completion_ctx = FutureCompletionContext(
            result_write_options=ResultWriteOptions(
                dataset_id="test_dataset",
                output_path="test_output.jsonl",
                auto_update_blacklist=False,
            ),
            settings_fingerprint="abc",
            template_library_fingerprint="def",
            run_config={"key": "val"},
        )

        apply_completed_result(
            result=result,
            completion_ctx=completion_ctx,
            execution_state=state,
        )

        assert len(state.results) == 1
        assert state.submittable_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
