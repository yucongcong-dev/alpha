#!/usr/bin/env python3
"""
中期改进功能集成测试
测试错误处理框架
"""

import pytest

from alpha.error_handling import (
    CircuitBreakerStrategy,
    ErrorCategory,
    ErrorContext,
    ErrorHandler,
    ErrorSeverity,
    FallbackStrategy,
    RetryStrategy,
    get_error_handler,
    handle_global_error,
)


class TestErrorHandlingFramework:
    """测试错误处理框架"""

    def setup_method(self):
        """设置测试环境"""
        handler = ErrorHandler()
        handler.clear_errors()

    def test_error_handler_with_strategies(self):
        """测试错误处理器的恢复策略"""
        handler = get_error_handler()
        handler.clear_errors()

        exception = ValueError("Test error")
        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.VALIDATION,
            operation="test_op",
            module="test_module",
            function="test_func"
        )

        error_record = handler.handle_error(exception, context)

        assert error_record.exception == exception
        assert error_record.recovered is True
        assert error_record.recovery_action is not None

    def test_retry_strategy(self):
        """测试重试策略"""
        strategy = RetryStrategy(max_retries=2, delay=0.1)
        handler = get_error_handler()

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.NETWORK,
            operation="test_op",
            module="test_module",
            function="test_func"
        )

        from alpha.exceptions import BrainRateLimitError

        error_record = handler.handle_error(BrainRateLimitError("rate limit"), context)
        assert strategy.can_recover(error_record)

        result = strategy.recover(error_record)
        assert result["action"] == "retry"

    def test_fallback_strategy(self):
        """测试降级策略"""
        strategy = FallbackStrategy(fallback_value="fallback_result")
        handler = get_error_handler()

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.CONFIG,
            operation="test_op",
            module="test_module",
            function="test_func"
        )

        error_record = handler.handle_error(ValueError("config error"), context)
        assert strategy.can_recover(error_record)

        result = strategy.recover(error_record)
        assert result["action"] == "fallback_value"
        assert result["value"] == "fallback_result"

    def test_circuit_breaker_strategy(self):
        """测试熔断器策略"""
        strategy = CircuitBreakerStrategy(failure_threshold=2, recovery_timeout=0.1)
        handler = get_error_handler()

        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.API,
            operation="test_op",
            module="test_module",
            function="test_func"
        )

        error_record = handler.handle_error(ValueError("api error"), context)
        assert strategy.can_recover(error_record)

        result1 = strategy.recover(error_record)
        assert result1["action"] == "circuit_breaker_monitor"

        result2 = strategy.recover(error_record)
        assert result2["action"] == "circuit_breaker_open"

    def test_error_handler_metrics(self):
        """测试错误处理器指标"""
        handler = get_error_handler()
        handler.clear_errors()

        for _ in range(3):
            handler.handle_error(
                ValueError("test"),
                ErrorContext(severity=ErrorSeverity.WARNING, category=ErrorCategory.VALIDATION)
            )

        metrics = handler.get_metrics()
        assert metrics["errors_total"] == 3
        assert metrics["errors_warning"] == 3

    def test_error_handler_callable(self):
        """测试错误处理器可调用作为装饰器"""
        handler = get_error_handler()
        handler.clear_errors()

        @handler(severity=ErrorSeverity.ERROR, category=ErrorCategory.API)
        def risky_operation():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            risky_operation()

        assert handler.get_metrics()["errors_total"] == 1


class TestIntegration:
    """测试各模块集成"""

    def test_error_handler_integration(self):
        """测试错误处理器集成"""
        handler = get_error_handler()
        handler.clear_errors()

        try:
            raise ValueError("Integration test error")
        except ValueError as e:
            record = handle_global_error(
                e,
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.SYSTEM,
                operation="integration_test"
            )

        assert record.recovered is True
        assert handler.get_metrics()["errors_total"] == 1
