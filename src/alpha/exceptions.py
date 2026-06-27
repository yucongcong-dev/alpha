"""
异常类模块

本模块定义了 Brain API 客户端使用的自定义异常类，用于处理
API 交互过程中可能出现的各种错误情况。

异常层次结构：
    RuntimeError (内置)
    └── BrainAPIError
        ├── BrainRateLimitError (速率限制错误)
        └── BrainQueueBusyError (队列繁忙错误)
"""

from __future__ import annotations


class BrainAPIError(RuntimeError):
    """Brain API 错误基类。所有 API 交互错误均应继承此类。

    Attributes:
        message: 错误消息字符串。
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


class BrainRateLimitError(BrainAPIError):
    """API 速率限制错误。携带建议的重试等待时间。

    Attributes:
        message: 错误消息。
        retry_after: 建议重试等待秒数，若 API 未提供则为 None。
    """

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after

    def __str__(self) -> str:
        if self.retry_after is not None:
            return f"{self.message} (请在 {self.retry_after} 秒后重试)"
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r}, retry_after={self.retry_after!r})"


class BrainQueueBusyError(BrainAPIError):
    """API 任务队列繁忙错误。高并发或服务器高负载时抛出。

    Attributes:
        message: 错误消息。
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"
