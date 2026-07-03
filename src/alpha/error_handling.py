#!/usr/bin/env python3
"""
错误处理中间件和框架
提供统一的错误处理、恢复机制和监控
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TypeVar, cast
from typing_extensions import ParamSpec

from alpha.exceptions import BrainRateLimitError, BrainQueueBusyError

# 类型变量
P = ParamSpec('P')
R = TypeVar('R')
T = TypeVar('T')


class ErrorSeverity(Enum):
    """错误严重程度"""
    DEBUG = "DEBUG"      # 调试信息，不影响功能
    INFO = "INFO"        # 信息性错误，正常流程
    WARNING = "WARNING"  # 警告，功能可能受影响
    ERROR = "ERROR"      # 错误，功能受影响但可恢复
    CRITICAL = "CRITICAL" # 严重错误，需要人工干预


class ErrorCategory(Enum):
    """错误类别"""
    API = "API"                 # API调用错误
    NETWORK = "NETWORK"         # 网络错误
    CONFIG = "CONFIG"          # 配置错误
    VALIDATION = "VALIDATION"  # 数据验证错误
    RESOURCE = "RESOURCE"      # 资源错误（内存、磁盘等）
    TIMEOUT = "TIMEOUT"        # 超时错误
    CONCURRENCY = "CONCURRENCY" # 并发错误
    SYSTEM = "SYSTEM"          # 系统错误
    UNKNOWN = "UNKNOWN"        # 未知错误


@dataclass
class ErrorContext:
    """错误上下文信息"""
    timestamp: float = field(default_factory=time.time)
    severity: ErrorSeverity = ErrorSeverity.ERROR
    category: ErrorCategory = ErrorCategory.UNKNOWN
    operation: str = ""
    module: str = ""
    function: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "severity": self.severity.value,
            "category": self.category.value,
            "operation": self.operation,
            "module": self.module,
            "function": self.function,
            "parameters": self.parameters,
            "metadata": self.metadata,
            "stack_trace": self.stack_trace,
        }
    
    def __str__(self) -> str:
        return (f"[{self.severity.value}] {self.category.value}: "
                f"{self.operation} (module={self.module}, function={self.function})")


@dataclass
class ErrorRecord:
    """错误记录"""
    exception: Exception
    context: ErrorContext
    recovery_action: Optional[str] = None
    recovered: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "exception_type": type(self.exception).__name__,
            "exception_message": str(self.exception),
            "context": self.context.to_dict(),
            "recovery_action": self.recovery_action,
            "recovered": self.recovered,
            "timestamp": self.context.timestamp,
        }
    
    def __str__(self) -> str:
        base = f"{self.context} -> {type(self.exception).__name__}: {self.exception}"
        if self.recovery_action:
            base += f" [Recovery: {self.recovery_action}]"
        if self.recovered:
            base += " [RECOVERED]"
        return base


class RecoveryStrategy(ABC):
    """恢复策略基类"""
    
    @abstractmethod
    def can_recover(self, error: ErrorRecord) -> bool:
        """检查是否可以恢复"""
        pass
    
    @abstractmethod
    def recover(self, error: ErrorRecord) -> Any:
        """执行恢复操作"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """获取策略描述"""
        pass


class RetryStrategy(RecoveryStrategy):
    """重试策略"""
    
    def __init__(self, max_retries: int = 3, delay: float = 1.0, 
                 backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff_factor = backoff_factor
        self._retry_counts: dict[str, int] = defaultdict(int)
    
    def can_recover(self, error: ErrorRecord) -> bool:
        """检查是否可以重试"""
        # 只对特定类型的错误重试
        if isinstance(error.exception, (BrainRateLimitError, BrainQueueBusyError)):
            operation_key = f"{error.context.module}.{error.context.function}"
            return self._retry_counts[operation_key] < self.max_retries
        
        # 网络错误和超时错误也可以重试
        if error.context.category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT]:
            operation_key = f"{error.context.module}.{error.context.function}"
            return self._retry_counts[operation_key] < self.max_retries
        
        return False
    
    def recover(self, error: ErrorRecord) -> Any:
        """执行重试恢复"""
        operation_key = f"{error.context.module}.{error.context.function}"
        retry_count = self._retry_counts[operation_key]
        
        # 计算延迟时间
        if isinstance(error.exception, BrainRateLimitError):
            delay = error.exception.retry_after or self.delay
        else:
            delay = self.delay * (self.backoff_factor ** retry_count)
        
        # 记录重试
        self._retry_counts[operation_key] += 1
        
        return {
            "action": "retry",
            "retry_count": retry_count + 1,
            "max_retries": self.max_retries,
            "delay": delay,
            "message": f"将在 {delay:.1f} 秒后重试"
        }
    
    def get_description(self) -> str:
        return f"RetryStrategy(max_retries={self.max_retries}, delay={self.delay})"


class FallbackStrategy(RecoveryStrategy):
    """降级策略"""
    
    def __init__(self, fallback_value: Any = None, 
                 fallback_function: Optional[Callable] = None):
        self.fallback_value = fallback_value
        self.fallback_function = fallback_function
    
    def can_recover(self, error: ErrorRecord) -> bool:
        """检查是否可以降级"""
        # 配置错误、验证错误可以使用降级
        return error.context.category in [
            ErrorCategory.CONFIG, 
            ErrorCategory.VALIDATION
        ]
    
    def recover(self, error: ErrorRecord) -> Any:
        """执行降级恢复"""
        if self.fallback_function:
            try:
                result = self.fallback_function()
                return {
                    "action": "fallback_function",
                    "result": result,
                    "message": "使用降级函数返回结果"
                }
            except Exception as e:
                return {
                    "action": "fallback_value",
                    "value": self.fallback_value,
                    "message": f"降级函数失败，使用默认值: {e}"
                }
        else:
            return {
                "action": "fallback_value",
                "value": self.fallback_value,
                "message": "使用默认降级值"
            }
    
    def get_description(self) -> str:
        if self.fallback_function:
            return f"FallbackStrategy(function={self.fallback_function.__name__})"
        return f"FallbackStrategy(value={self.fallback_value})"


class CircuitBreakerStrategy(RecoveryStrategy):
    """熔断器策略"""
    
    def __init__(self, failure_threshold: int = 5, 
                 recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._open_circuits: dict[str, float] = {}
    
    def can_recover(self, error: ErrorRecord) -> bool:
        """检查是否触发熔断"""
        operation_key = f"{error.context.module}.{error.context.function}"
        
        # 检查熔断器是否已打开
        if operation_key in self._open_circuits:
            opened_time = self._open_circuits[operation_key]
            if time.time() - opened_time < self.recovery_timeout:
                return False  # 熔断器仍处于打开状态
            else:
                # 恢复期结束，关闭熔断器
                del self._open_circuits[operation_key]
                self._failures[operation_key].clear()
        
        return True
    
    def recover(self, error: ErrorRecord) -> Any:
        """执行熔断恢复"""
        operation_key = f"{error.context.module}.{error.context.function}"
        
        # 记录失败
        current_time = time.time()
        self._failures[operation_key].append(current_time)
        
        # 清理过期的失败记录
        window_start = current_time - self.recovery_timeout
        self._failures[operation_key] = [
            t for t in self._failures[operation_key] 
            if t >= window_start
        ]
        
        # 检查是否触发熔断
        if len(self._failures[operation_key]) >= self.failure_threshold:
            self._open_circuits[operation_key] = current_time
            return {
                "action": "circuit_breaker_open",
                "message": f"熔断器已打开，将在 {self.recovery_timeout} 秒后恢复",
                "failures": len(self._failures[operation_key]),
                "threshold": self.failure_threshold
            }
        
        return {
            "action": "circuit_breaker_monitor",
            "message": "监控中，未触发熔断",
            "failures": len(self._failures[operation_key]),
            "threshold": self.failure_threshold
        }
    
    def get_description(self) -> str:
        return (f"CircuitBreakerStrategy(threshold={self.failure_threshold}, "
                f"timeout={self.recovery_timeout})")


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.strategies: list[RecoveryStrategy] = []
        self.error_records: list[ErrorRecord] = []
        self.metrics: dict[str, Any] = defaultdict(int)
        self._lock = threading.RLock()
        
        # 注册默认策略
        self.register_strategy(RetryStrategy())
        self.register_strategy(FallbackStrategy())
        self.register_strategy(CircuitBreakerStrategy())
    
    def register_strategy(self, strategy: RecoveryStrategy) -> None:
        """注册恢复策略"""
        with self._lock:
            self.strategies.append(strategy)
        self.logger.debug(f"Registered recovery strategy: {strategy.get_description()}")
    
    def handle_error(self, exception: Exception, context: ErrorContext) -> ErrorRecord:
        """处理错误"""
        # 创建错误记录
        error_record = ErrorRecord(exception=exception, context=context)
        
        # 更新指标
        with self._lock:
            self.metrics[f"errors_total"] += 1
            self.metrics[f"errors_{context.severity.value.lower()}"] += 1
            self.metrics[f"errors_{context.category.value.lower()}"] += 1
        
        # 尝试恢复
        recovery_result = self._attempt_recovery(error_record)
        
        # 记录错误
        with self._lock:
            self.error_records.append(error_record)
        
        # 记录日志
        self._log_error(error_record, recovery_result)
        
        return error_record
    
    def _attempt_recovery(self, error_record: ErrorRecord) -> Optional[dict[str, Any]]:
        """尝试恢复"""
        for strategy in self.strategies:
            if strategy.can_recover(error_record):
                try:
                    result = strategy.recover(error_record)
                    if isinstance(result, dict):
                        error_record.recovery_action = result.get("action", "unknown")
                        error_record.recovered = True
                        
                        with self._lock:
                            self.metrics["recoveries_total"] += 1
                            self.metrics[f"recoveries_{error_record.recovery_action}"] += 1
                        
                        return result
                except Exception as e:
                    self.logger.error(f"Recovery strategy failed: {e}")
        
        return None
    
    def _log_error(self, error_record: ErrorRecord, recovery_result: Optional[dict[str, Any]]) -> None:
        """记录错误日志"""
        log_message = str(error_record)
        
        if recovery_result:
            log_message += f" | Recovery: {recovery_result.get('message', 'unknown')}"
        
        # 根据严重程度选择日志级别
        if error_record.context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, exc_info=error_record.exception)
        elif error_record.context.severity == ErrorSeverity.ERROR:
            self.logger.error(log_message, exc_info=error_record.exception)
        elif error_record.context.severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
        elif error_record.context.severity == ErrorSeverity.INFO:
            self.logger.info(log_message)
        else:  # DEBUG
            self.logger.debug(log_message)
    
    def get_metrics(self) -> dict[str, Any]:
        """获取错误指标"""
        with self._lock:
            return dict(self.metrics)
    
    def get_recent_errors(self, limit: int = 10) -> list[ErrorRecord]:
        """获取最近的错误"""
        with self._lock:
            return list(self.error_records[-limit:]) if self.error_records else []
    
    def clear_errors(self) -> None:
        """清除错误记录"""
        with self._lock:
            self.error_records.clear()
            self.metrics.clear()
    
    def generate_report(self) -> dict[str, Any]:
        """生成错误报告"""
        with self._lock:
            report: dict[str, Any] = {
                "timestamp": time.time(),
                "metrics": dict(self.metrics),
                "recent_errors": [],
                "recovery_strategies": [s.get_description() for s in self.strategies]
            }
            
            # 添加最近错误
            for error in self.error_records[-5:]:
                report["recent_errors"].append(error.to_dict())
        
        return report
    
    def __call__(
        self,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        operation: str = "",
        module: str = "",
        **context_kwargs
    ):
        """使 ErrorHandler 实例可作为装饰器使用"""
        return error_handler(
            severity=severity,
            category=category,
            operation=operation,
            module=module,
            **context_kwargs
        )


# 装饰器
def error_handler(
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    operation: str = "",
    module: str = "",
    **context_kwargs
):
    """错误处理装饰器"""
    
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # 获取错误处理器实例
            handler = get_error_handler()
            
            # 准备上下文
            context = ErrorContext(
                severity=severity,
                category=category,
                operation=operation or func.__name__,
                module=module or func.__module__,
                function=func.__name__,
                parameters={
                    "args": str(args),
                    "kwargs": str(kwargs)
                },
                **context_kwargs
            )
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 处理错误
                handler.handle_error(e, context)
                
                # 总是重新抛出异常，让调用者决定如何处理
                raise
        
        return wrapper
    
    return decorator


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,)
):
    """重试装饰器"""
    
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    # 如果是最后一次尝试，直接抛出
                    if attempt == max_retries - 1:
                        raise
                    
                    # 计算延迟
                    current_delay = delay * (backoff_factor ** attempt)
                    
                    # 记录重试
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__}: "
                        f"{e}. Waiting {current_delay:.1f}s"
                    )
                    
                    # 等待
                    time.sleep(current_delay)
            
            # 理论上不会到达这里
            raise last_exception  # type: ignore
        
        return wrapper
    
    return decorator


# 全局错误处理器
_global_error_handler: Optional[ErrorHandler] = None

def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler

def set_error_handler(handler: ErrorHandler) -> None:
    """设置全局错误处理器"""
    global _global_error_handler
    _global_error_handler = handler

def handle_global_error(exception: Exception, **context_kwargs) -> ErrorRecord:
    """处理全局错误"""
    handler = get_error_handler()
    
    context = ErrorContext(
        severity=context_kwargs.pop("severity", ErrorSeverity.ERROR),
        category=context_kwargs.pop("category", ErrorCategory.UNKNOWN),
        operation=context_kwargs.pop("operation", "global"),
        **context_kwargs
    )
    
    return handler.handle_error(exception, context)


# 示例使用
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG)
    
    # 获取错误处理器
    handler = get_error_handler()
    
    # 示例函数
    @error_handler(
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.API,
        operation="测试API调用",
        module="example"
    )
    def example_api_call(url: str):
        """示例API调用"""
        if "error" in url:
            raise BrainRateLimitError("API速率限制", retry_after=5)
        return f"Success: {url}"
    
    # 测试
    try:
        result = example_api_call("https://api.test.com/error")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Caught exception: {e}")
    
    # 查看报告
    report = handler.generate_report()
    print("\n错误报告:")
    print(f"总错误数: {report['metrics'].get('errors_total', 0)}")
    print(f"恢复数: {report['metrics'].get('recoveries_total', 0)}")