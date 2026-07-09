#!/usr/bin/env python3
"""Lightweight error logging and decoration helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
import functools
import logging
import threading
import time
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


class ErrorSeverity(Enum):
    """Structured severity levels for runtime logging."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(Enum):
    """Structured error categories for coarse-grained metrics."""

    API = "API"
    NETWORK = "NETWORK"
    CONFIG = "CONFIG"
    VALIDATION = "VALIDATION"
    RESOURCE = "RESOURCE"
    TIMEOUT = "TIMEOUT"
    CONCURRENCY = "CONCURRENCY"
    SYSTEM = "SYSTEM"
    UNKNOWN = "UNKNOWN"


@dataclass
class ErrorContext:
    """Normalized metadata attached to a captured exception."""

    timestamp: float = field(default_factory=time.time)
    severity: ErrorSeverity = ErrorSeverity.ERROR
    category: ErrorCategory = ErrorCategory.UNKNOWN
    operation: str = ""
    module: str = ""
    function: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    stack_trace: str | None = None

    def to_dict(self) -> dict[str, Any]:
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
        return (
            f"[{self.severity.value}] {self.category.value}: "
            f"{self.operation} (module={self.module}, function={self.function})"
        )


@dataclass
class ErrorRecord:
    """Single captured exception plus its normalized context."""

    exception: Exception
    context: ErrorContext
    recovered: bool = False
    recovery_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exception_type": type(self.exception).__name__,
            "exception_message": str(self.exception),
            "context": self.context.to_dict(),
            "recovery_action": self.recovery_action,
            "recovered": self.recovered,
            "timestamp": self.context.timestamp,
        }

    def __str__(self) -> str:
        message = f"{self.context} -> {type(self.exception).__name__}: {self.exception}"
        if self.recovery_action:
            message += f" [Recovery: {self.recovery_action}]"
        if self.recovered:
            message += " [RECOVERED]"
        return message


class ErrorHandler:
    """Thread-safe runtime error recorder used by decorators and global hooks."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_records: list[ErrorRecord] = []
        self.metrics: dict[str, Any] = defaultdict(int)
        self._lock = threading.RLock()

    def handle_error(self, exception: Exception, context: ErrorContext) -> ErrorRecord:
        """Capture an exception, update metrics, and emit a structured log."""
        error_record = ErrorRecord(exception=exception, context=context)
        with self._lock:
            self.error_records.append(error_record)
            self.metrics["errors_total"] += 1
            self.metrics[f"errors_{context.severity.value.lower()}"] += 1
            self.metrics[f"errors_{context.category.value.lower()}"] += 1
        self._log_error(error_record)
        return error_record

    def _log_error(self, error_record: ErrorRecord) -> None:
        message = str(error_record)
        if error_record.context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(message, exc_info=error_record.exception)
        elif error_record.context.severity == ErrorSeverity.ERROR:
            self.logger.error(message, exc_info=error_record.exception)
        elif error_record.context.severity == ErrorSeverity.WARNING:
            self.logger.warning(message)
        elif error_record.context.severity == ErrorSeverity.INFO:
            self.logger.info(message)
        else:
            self.logger.debug(message)

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.metrics)

    def get_recent_errors(self, limit: int = 10) -> list[ErrorRecord]:
        with self._lock:
            return list(self.error_records[-limit:])

    def clear_errors(self) -> None:
        with self._lock:
            self.error_records.clear()
            self.metrics.clear()

    def generate_report(self) -> dict[str, Any]:
        with self._lock:
            return {
                "timestamp": time.time(),
                "metrics": dict(self.metrics),
                "recent_errors": [error.to_dict() for error in self.error_records[-5:]],
            }

    def __call__(
        self,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        operation: str = "",
        module: str = "",
        **context_kwargs: Any,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        return error_handler(
            severity=severity,
            category=category,
            operation=operation,
            module=module,
            **context_kwargs,
        )


def error_handler(
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    operation: str = "",
    module: str = "",
    **context_kwargs: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that records structured error context before re-raising."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            handler = get_error_handler()
            context = ErrorContext(
                severity=severity,
                category=category,
                operation=operation or func.__name__,
                module=module or func.__module__,
                function=func.__name__,
                parameters={"args": str(args), "kwargs": str(kwargs)},
                **context_kwargs,
            )
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                handler.handle_error(exc, context)
                raise

        return wrapper

    return decorator


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Simple retry decorator retained for compatibility."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            logger = logging.getLogger(__name__)
            last_exception: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt == max_retries - 1:
                        raise
                    current_delay = delay * (backoff_factor ** attempt)
                    logger.warning(
                        "Retry %d/%d for %s: %s. Waiting %.1fs",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        exc,
                        current_delay,
                    )
                    time.sleep(current_delay)
            assert last_exception is not None
            raise last_exception

        return wrapper

    return decorator


_global_error_handler: ErrorHandler | None = None


def get_error_handler() -> ErrorHandler:
    """Return the process-global error handler instance."""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def set_error_handler(handler: ErrorHandler) -> None:
    """Override the process-global error handler instance."""
    global _global_error_handler
    _global_error_handler = handler


def handle_global_error(exception: Exception, **context_kwargs: Any) -> ErrorRecord:
    """Capture an exception through the global handler without a decorator."""
    context = ErrorContext(
        severity=context_kwargs.pop("severity", ErrorSeverity.ERROR),
        category=context_kwargs.pop("category", ErrorCategory.UNKNOWN),
        operation=context_kwargs.pop("operation", "global"),
        **context_kwargs,
    )
    return get_error_handler().handle_error(exception, context)


__all__ = [
    "ErrorCategory",
    "ErrorContext",
    "ErrorHandler",
    "ErrorRecord",
    "ErrorSeverity",
    "error_handler",
    "get_error_handler",
    "handle_global_error",
    "retry_on_error",
    "set_error_handler",
]
