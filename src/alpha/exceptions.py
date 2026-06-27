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
    """
    Brain API 错误的基类。

    所有与 Brain API 交互过程中发生的错误都应继承此类。
    该类提供了统一的错误接口，便于错误处理和日志记录。

    Attributes:
        message (str): 错误消息，描述错误的具体内容。

    Args:
        message: 错误消息字符串，描述错误的具体内容。

    Example:
        >>> raise BrainAPIError("API 请求失败")
        BrainAPIError: API 请求失败
    """

    def __init__(self, message: str) -> None:
        """
        初始化 BrainAPIError 异常。

        Args:
            message: 错误消息字符串，描述错误的具体内容。
        """
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        """
        返回异常的字符串表示。

        Returns:
            str: 异常消息字符串。
        """
        return self.message

    def __repr__(self) -> str:
        """
        返回异常的官方字符串表示。

        Returns:
            str: 包含异常类名和消息的字符串。
        """
        return f"{self.__class__.__name__}({self.message!r})"


class BrainRateLimitError(BrainAPIError):
    """
    Brain API 速率限制错误。

    当 API 请求超过速率限制时抛出此异常。该异常携带了
    retry_after 属性，指示客户端应该等待多少秒后重试。

    Attributes:
        message (str): 错误消息，描述速率限制的具体情况。
        retry_after (Optional[int]): 建议的重试等待时间（秒）。
            如果 API 未提供此信息，则为 None。

    Args:
        message: 错误消息字符串，描述速率限制的具体情况。
        retry_after: 建议的重试等待时间（秒）。默认为 None。

    Example:
        >>> error = BrainRateLimitError("请求过于频繁", retry_after=60)
        >>> print(error.retry_after)
        60
        >>> raise BrainRateLimitError("API 速率限制")
        BrainRateLimitError: API 速率限制

    Note:
        客户端应该捕获此异常，并使用指数退避策略或
        retry_after 值进行重试。
    """

    def __init__(
        self,
        message: str,
        retry_after: int | None = None
    ) -> None:
        """
        初始化 BrainRateLimitError 异常。

        Args:
            message: 错误消息字符串，描述速率限制的具体情况。
            retry_after: 建议的重试等待时间（秒）。如果 API 未提供此信息，
                可以设置为 None。
        """
        super().__init__(message)
        self.retry_after = retry_after

    def __str__(self) -> str:
        """
        返回异常的字符串表示。

        如果 retry_after 有值，会在消息中包含建议的重试时间。

        Returns:
            str: 异常消息字符串，可能包含重试时间信息。
        """
        if self.retry_after is not None:
            return f"{self.message} (请在 {self.retry_after} 秒后重试)"
        return self.message

    def __repr__(self) -> str:
        """
        返回异常的官方字符串表示。

        Returns:
            str: 包含异常类名、消息和 retry_after 的字符串。
        """
        return (
            f"{self.__class__.__name__}("
            f"{self.message!r}, retry_after={self.retry_after!r})"
        )


class BrainQueueBusyError(BrainAPIError):
    """
    Brain API 队列繁忙错误。

    当 API 服务器的任务队列已满或过于繁忙时抛出此异常。
    这通常发生在高并发请求或服务器负载过高的情况下。

    Attributes:
        message (str): 错误消息，描述队列繁忙的具体情况。

    Args:
        message: 错误消息字符串，描述队列繁忙的具体情况。

    Example:
        >>> raise BrainQueueBusyError("服务器队列繁忙，请稍后重试")
        BrainQueueBusyError: 服务器队列繁忙，请稍后重试

    Note:
        客户端应该捕获此异常，并实现适当的退避策略。
        建议使用指数退避算法，在多次重试后逐步增加等待时间。
    """

    def __init__(self, message: str) -> None:
        """
        初始化 BrainQueueBusyError 异常。

        Args:
            message: 错误消息字符串，描述队列繁忙的具体情况。
        """
        super().__init__(message)

    def __str__(self) -> str:
        """
        返回异常的字符串表示。

        Returns:
            str: 异常消息字符串。
        """
        return self.message

    def __repr__(self) -> str:
        """
        返回异常的官方字符串表示。

        Returns:
            str: 包含异常类名和消息的字符串。
        """
        return f"{self.__class__.__name__}({self.message!r})"
