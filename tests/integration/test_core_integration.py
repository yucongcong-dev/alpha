# -*- coding: utf-8 -*-
"""
核心模块集成测试

测试 core 包中各模块之间的协作，包括：
- simulation 与 scheduler 的协作
- executor 与 simulation、scheduler 的协作
- 模型类与执行流程的集成
"""

import unittest
from unittest.mock import MagicMock, patch

from alpha.models.base import (
    ExecutionState,
    FieldTestResult,
    RuntimeConcurrencyState,
    RunFilters,
)


class TestExecutionStateIntegration(unittest.TestCase):
    """ExecutionState 与各模块的集成测试"""

    def test_create_execution_state(self):
        """测试创建 ExecutionState 实例"""
        state = ExecutionState(
            results=[],
            attempted_keys=set(),
            template_stats={},
            pending_futures={},
            field_queue_busy_counts={},
            skipped_fields_due_to_queue=set(),
        )
        self.assertEqual(len(state.results), 0)
        self.assertEqual(len(state.attempted_keys), 0)
        self.assertEqual(state.last_submission_at, 0.0)

    def test_execution_state_with_results(self):
        """测试 ExecutionState 添加结果后的状态"""
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
            template_name="test_template",
            status="simulated",
            submittable=True,
            expression="rank(test)",
        )
        state.results.append(result)
        self.assertEqual(len(state.results), 1)
        self.assertTrue(state.results[0].submittable)


class TestSimulationSchedulerIntegration(unittest.TestCase):
    """simulation 与 scheduler 模块的集成测试"""

    def test_build_failure_result_used_in_scheduler(self):
        """测试 scheduler 中使用 build_failure_result"""
        from alpha.core.simulation import build_failure_result
        from alpha.core.scheduler import handle_completed_future

        result = build_failure_result(
            field_id="test",
            field_type="MATRIX",
            field_name="test",
            template_name="test",
            simulation_id=None,
            alpha_id=None,
            expression="rank(test)",
            settings_fingerprint="test",
            template_library_fingerprint="test",
            failed_stage="simulate",
            message="test error",
        )
        self.assertFalse(result.submittable)
        self.assertEqual(result.failed_stage, "simulate")

    def test_runtime_concurrency_state_transitions(self):
        """测试 RuntimeConcurrencyState 状态转换"""
        state = RuntimeConcurrencyState(max_workers=5, runtime_max_workers=5)
        self.assertFalse(state.is_cooling_down())

        from alpha.core.scheduler import apply_congestion_cooldown

        args = MagicMock()
        args.queue_busy_cooldown_seconds = 60

        apply_congestion_cooldown(args, state)
        self.assertEqual(state.runtime_max_workers, 1)
        self.assertTrue(state.is_cooling_down())


class TestExecutorSimulationIntegration(unittest.TestCase):
    """executor 与 simulation 模块的集成测试"""

    def test_should_skip_field_with_queue_skip(self):
        """测试 should_skip_field 与队列跳过的集成"""
        from alpha.core.executor import should_skip_field

        filters = RunFilters()
        skipped = {"field_123"}

        self.assertTrue(should_skip_field("field_123", "test", filters, skipped))
        self.assertFalse(should_skip_field("field_456", "test2", filters, skipped))

    def test_should_skip_expression_by_history(self):
        """测试 should_skip_expression_by_history 与 FieldTestResult 的集成"""
        from alpha.core.executor import should_skip_expression_by_history

        results = [
            FieldTestResult(
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
        ]

        self.assertTrue(
            should_skip_expression_by_history(
                "sales", "ts_mean_20", "rank(ts_mean(sales, 20))", results
            )
        )
        self.assertFalse(
            should_skip_expression_by_history(
                "sales", "ts_mean_60", "rank(ts_mean(sales, 60))", results
            )
        )


class TestModuleImports(unittest.TestCase):
    """模块导入测试，确保没有循环依赖"""

    def test_import_core_package(self):
        """测试导入 core 包"""
        import alpha.core as core
        self.assertTrue(hasattr(core, 'run_field_test'))
        self.assertTrue(hasattr(core, 'run_field_test_in_worker'))
        self.assertTrue(hasattr(core, 'handle_completed_future'))
        self.assertTrue(hasattr(core, 'drain_completed_futures'))
        self.assertTrue(hasattr(core, 'build_pending_templates_for_field'))
        self.assertTrue(hasattr(core, 'print_dry_run_plan'))

    def test_import_simulation_module(self):
        """测试导入 simulation 模块"""
        from alpha.core import simulation
        self.assertTrue(hasattr(simulation, 'extract_alpha_id'))
        self.assertTrue(hasattr(simulation, 'extract_checks'))
        self.assertTrue(hasattr(simulation, 'create_simulation_with_retry'))
        self.assertTrue(hasattr(simulation, 'run_field_test'))

    def test_import_scheduler_module(self):
        """测试导入 scheduler 模块"""
        from alpha.core import scheduler
        self.assertTrue(hasattr(scheduler, 'handle_completed_future'))
        self.assertTrue(hasattr(scheduler, 'drain_completed_futures'))
        self.assertTrue(hasattr(scheduler, 'apply_congestion_cooldown'))
        self.assertTrue(hasattr(scheduler, 'throttle_before_submission'))

    def test_import_executor_module(self):
        """测试导入 executor 模块"""
        from alpha.core import executor
        self.assertTrue(hasattr(executor, 'build_pending_templates_for_field'))
        self.assertTrue(hasattr(executor, 'should_skip_field'))
        self.assertTrue(hasattr(executor, 'print_dry_run_plan'))
        self.assertTrue(hasattr(executor, 'run_field_test'))
        self.assertTrue(hasattr(executor, 'handle_completed_future'))

    def test_no_circular_imports(self):
        """测试没有循环依赖"""
        import sys
        alpha_modules = [k for k in sys.modules.keys() if k.startswith('alpha.core')]
        self.assertIn('alpha.core.simulation', alpha_modules)
        self.assertIn('alpha.core.scheduler', alpha_modules)
        self.assertIn('alpha.core.executor', alpha_modules)


if __name__ == "__main__":
    unittest.main()
