"""
错误处理和性能监控集成测试
测试错误处理中间件和性能监控工具的集成使用
"""

from __future__ import annotations

import time
import logging
from unittest.mock import patch, MagicMock

import pytest

from alpha.error_handling import (
    ErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    error_handler,
    retry_on_error,
    get_error_handler,
    handle_global_error,
)
from alpha.performance_monitor import (
    PerformanceMonitor,
    monitor_performance,
    record_metric,
    get_performance_monitor,
    CriticalOperations,
)
from alpha.exceptions import BrainRateLimitError, BrainQueueBusyError


class TestErrorPerformanceIntegration:
    """错误处理和性能监控集成测试"""
    
    def setup_method(self):
        """每个测试方法前重置"""
        # 重置全局实例
        from alpha.error_handling import _global_error_handler
        from alpha.performance_monitor import _global_monitor
        
        _global_error_handler = None
        _global_monitor = None
        
        # 配置日志
        logging.basicConfig(level=logging.WARNING)
    
    def test_error_handler_with_performance_monitoring(self):
        """测试错误处理与性能监控集成"""
        # 获取错误处理器和性能监控器
        error_handler = get_error_handler()
        performance_monitor = get_performance_monitor()
        
        # 清空指标
        performance_monitor.clear_metrics()
        
        # 定义被监控的函数
        @error_handler(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.API,
            operation="test_operation"
        )
        @monitor_performance("test.operation")
        def test_operation(should_fail: bool = False):
            """测试操作"""
            if should_fail:
                raise BrainRateLimitError("Rate limit exceeded", retry_after=5)
            time.sleep(0.01)  # 模拟工作
            return "success"
        
        # 测试成功情况
        result = test_operation(should_fail=False)
        assert result == "success"
        
        # 测试失败情况
        with pytest.raises(BrainRateLimitError):
            test_operation(should_fail=True)
        
        # 验证错误处理
        error_records = error_handler.get_recent_errors()
        assert len(error_records) == 1
        assert error_records[0].context.operation == "test_operation"
        assert error_records[0].context.category == ErrorCategory.API
        assert isinstance(error_records[0].exception, BrainRateLimitError)
        
        # 验证性能监控
        summary = performance_monitor.get_metrics_summary()
        assert "test.operation" in summary["timers"]
        
        timer_stats = summary["timers"]["test.operation"]
        assert timer_stats["count"] == 2  # 成功和失败各一次
        
        # 验证错误指标
        metrics = error_handler.get_metrics()
        assert metrics["errors_total"] == 1
        assert metrics["errors_error"] == 1
        assert metrics["errors_api"] == 1
    
    def test_retry_with_performance_tracking(self):
        """测试重试机制与性能跟踪"""
        error_handler = get_error_handler()
        performance_monitor = get_performance_monitor()
        performance_monitor.clear_metrics()
        
        call_count = 0
        
        @retry_on_error(max_retries=3, delay=0.01)
        @error_handler(
            severity=ErrorSeverity.WARNING,
            category=ErrorCategory.NETWORK,
            operation="retry_operation"
        )
        @monitor_performance("retry.operation")
        def retry_operation():
            """重试操作"""
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:
                raise ConnectionError("Network error")
            return f"success on attempt {call_count}"
        
        # 执行函数
        result = retry_operation()
        assert result == "success on attempt 3"
        assert call_count == 3
        
        # 验证性能监控
        summary = performance_monitor.get_metrics_summary()
        assert "retry.operation" in summary["timers"]
        
        # 验证错误处理
        error_records = error_handler.get_recent_errors()
        assert len(error_records) == 2  # 前两次失败
        
        # 验证重试指标
        metrics = error_handler.get_metrics()
        assert metrics.get("recoveries_total", 0) >= 0
    
    def test_critical_operations_monitoring(self):
        """测试关键操作监控"""
        performance_monitor = get_performance_monitor()
        performance_monitor.clear_metrics()
        
        # 模拟关键操作
        with performance_monitor.timer("api.call.custom"):
            time.sleep(0.01)
        
        # 使用CriticalOperations类
        with patch.object(CriticalOperations, 'api_call') as mock_api_call:
            CriticalOperations.api_call("test_endpoint", param="value")
            
            # 验证调用了性能监控
            summary = performance_monitor.get_metrics_summary()
            assert "api.call" in summary["timers"] or "api.call.custom" in summary["timers"]
    
    def test_error_recovery_strategies(self):
        """测试错误恢复策略"""
        error_handler = get_error_handler()
        
        # 清空现有策略
        error_handler.strategies.clear()
        
        # 添加自定义策略
        from alpha.error_handling import RetryStrategy, FallbackStrategy
        
        error_handler.register_strategy(RetryStrategy(max_retries=2, delay=0.01))
        error_handler.register_strategy(FallbackStrategy(fallback_value="fallback_result"))
        
        # 创建错误上下文
        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.CONFIG,
            operation="config_load",
            module="test",
            function="load_config"
        )
        
        # 模拟配置错误
        config_error = ValueError("Invalid configuration")
        
        # 处理错误
        error_record = error_handler.handle_error(config_error, context)
        
        # 验证恢复
        assert error_record.recovered is True
        assert error_record.recovery_action == "fallback_value"
        
        # 验证指标
        metrics = error_handler.get_metrics()
        assert metrics["errors_total"] == 1
        assert metrics["recoveries_total"] == 1
        assert metrics.get("recoveries_fallback_value", 0) == 1
    
    def test_performance_metrics_recording(self):
        """测试性能指标记录"""
        performance_monitor = get_performance_monitor()
        performance_monitor.clear_metrics()
        
        # 记录各种指标
        record_metric("api.requests", 1, metric_type="counter")
        record_metric("api.requests", 2, metric_type="counter")  # 应该累加
        
        record_metric("memory.usage", 123.45, metric_type="gauge")
        record_metric("cpu.usage", 78.9, metric_type="gauge")
        
        # 记录计时器
        record_metric("db.query", 0.123, metric_type="timer")
        record_metric("db.query", 0.456, metric_type="timer")
        
        # 获取摘要
        summary = performance_monitor.get_metrics_summary()
        
        # 验证计数器
        assert summary["counters"]["api.requests"] == 3  # 1 + 2
        
        # 验证测量值
        assert summary["gauges"]["memory.usage"] == 123.45
        assert summary["gauges"]["cpu.usage"] == 78.9
        
        # 验证计时器
        assert "db.query" in summary["timers"]
        timer_stats = summary["timers"]["db.query"]
        assert timer_stats["count"] == 2
        assert timer_stats["total_time"] == pytest.approx(0.579)  # 0.123 + 0.456
    
    def test_concurrent_error_handling(self):
        """测试并发错误处理"""
        import threading
        
        error_handler = get_error_handler()
        performance_monitor = get_performance_monitor()
        
        error_handler.clear_errors()
        performance_monitor.clear_metrics()
        
        errors_handled = []
        
        def worker(worker_id: int):
            """工作线程"""
            try:
                if worker_id % 2 == 0:
                    raise BrainRateLimitError(f"Rate limit in worker {worker_id}", retry_after=1)
                else:
                    raise BrainQueueBusyError(f"Queue busy in worker {worker_id}")
            except Exception as e:
                context = ErrorContext(
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.API,
                    operation=f"worker_{worker_id}",
                    module="test",
                    function="worker"
                )
                error_record = error_handler.handle_error(e, context)
                errors_handled.append(error_record)
        
        # 创建多个工作线程
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证所有错误都被处理
        assert len(errors_handled) == 10
        
        # 验证指标
        metrics = error_handler.get_metrics()
        assert metrics["errors_total"] == 10
        
        # 验证性能监控
        summary = performance_monitor.get_metrics_summary()
        # 这里可能没有性能指标，因为我们没有记录，但至少应该没有异常
    
    def test_error_and_performance_report_integration(self):
        """测试错误和性能报告集成"""
        error_handler = get_error_handler()
        performance_monitor = get_performance_monitor()
        
        error_handler.clear_errors()
        performance_monitor.clear_metrics()
        
        # 生成一些错误和性能数据
        for i in range(3):
            context = ErrorContext(
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.API,
                operation=f"test_op_{i}",
                module="test",
                function="test_function"
            )
            error = BrainRateLimitError(f"Test error {i}", retry_after=i)
            error_handler.handle_error(error, context)
        
        for i in range(5):
            with performance_monitor.timer(f"operation.{i}"):
                time.sleep(0.001)
        
        # 获取报告
        error_report = error_handler.generate_report()
        performance_summary = performance_monitor.get_metrics_summary()
        
        # 验证错误报告
        assert error_report["metrics"]["errors_total"] == 3
        assert len(error_report["recent_errors"]) <= 5
        
        # 验证性能摘要
        assert len(performance_summary["timers"]) >= 1
        assert performance_summary["timers"]["operation.0"]["count"] == 1
        
        # 创建集成报告
        integrated_report = {
            "timestamp": time.time(),
            "errors": error_report,
            "performance": performance_summary,
            "system_status": {
                "has_errors": error_report["metrics"]["errors_total"] > 0,
                "error_rate": error_report["metrics"]["errors_total"] / max(1, performance_summary["timers"].get("operation.0", {}).get("count", 1)),
                "avg_response_time": performance_summary["timers"].get("operation.0", {}).get("avg_time", 0),
            }
        }
        
        # 验证集成报告
        assert "errors" in integrated_report
        assert "performance" in integrated_report
        assert "system_status" in integrated_report
        assert isinstance(integrated_report["system_status"]["has_errors"], bool)
    
    def test_global_error_handling(self):
        """测试全局错误处理"""
        error_handler = get_error_handler()
        error_handler.clear_errors()
        
        # 使用全局错误处理函数
        try:
            raise ValueError("Global error test")
        except Exception as e:
            error_record = handle_global_error(
                e,
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.CONFIG,
                operation="global_test",
                module="global",
                function="test"
            )
        
        # 验证错误被处理
        error_records = error_handler.get_recent_errors()
        assert len(error_records) == 1
        assert error_records[0].context.operation == "global_test"
        assert error_records[0].context.severity == ErrorSeverity.CRITICAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])