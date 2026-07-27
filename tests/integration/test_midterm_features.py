#!/usr/bin/env python3
"""错误记录与重试装饰器的集成测试。"""

import pytest

from alpha.error_handling import (
    ErrorCategory,
    ErrorContext,
    ErrorHandler,
    ErrorSeverity,
    get_error_handler,
    handle_global_error,
    retry_on_error,
    set_error_handler,
)


class TestErrorHandlingFramework:
    """测试错误处理框架"""

    def setup_method(self):
        """设置测试环境"""
        handler = ErrorHandler()
        set_error_handler(handler)

    def test_error_handler_records_error(self):
        """测试错误处理器记录异常与上下文。"""
        handler = get_error_handler()

        exception = ValueError("Test error")
        context = ErrorContext(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.VALIDATION,
            operation="test_op",
            module="test_module",
            function="test_func",
        )

        error_record = handler.handle_error(exception, context)

        assert error_record.exception == exception
        assert error_record.context == context
        assert error_record.recovered is False
        assert error_record.recovery_action is None
        assert handler.get_recent_errors() == [error_record]

    def test_retry_decorator_retries_until_success(self, monkeypatch):
        """测试重试装饰器按配置重试并最终返回。"""
        monkeypatch.setattr("alpha.error_handling.time.sleep", lambda _delay: None)
        attempts = 0

        @retry_on_error(max_retries=3, delay=0.1, exceptions=(ValueError,))
        def flaky_operation():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("temporary error")
            return "ok"

        assert flaky_operation() == "ok"
        assert attempts == 3

    def test_error_handler_metrics(self):
        """测试错误处理器指标"""
        handler = get_error_handler()
        handler.clear_errors()

        for _ in range(3):
            handler.handle_error(
                ValueError("test"),
                ErrorContext(
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.VALIDATION,
                ),
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
                operation="integration_test",
            )

        assert record.recovered is False
        assert handler.get_metrics()["errors_total"] == 1
