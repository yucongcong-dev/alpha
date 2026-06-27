"""exceptions.py 异常类单元测试"""

from __future__ import annotations

import pytest

from alpha.exceptions import BrainAPIError, BrainQueueBusyError, BrainRateLimitError


class TestBrainAPIError:
    """测试基类异常"""

    def test_create_error(self) -> None:
        error = BrainAPIError("测试错误")
        assert error.message == "测试错误"
        assert str(error) == "测试错误"

    def test_repr(self) -> None:
        error = BrainAPIError("test")
        assert repr(error) == "BrainAPIError('test')"

    def test_is_runtime_error(self) -> None:
        error = BrainAPIError("msg")
        assert isinstance(error, RuntimeError)

    def test_can_catch_as_base(self) -> None:
        with pytest.raises(BrainAPIError):
            raise BrainRateLimitError("rate limited")


class TestBrainRateLimitError:
    """测试速率限制异常"""

    def test_with_retry_after(self) -> None:
        error = BrainRateLimitError("请求过于频繁", retry_after=60)
        assert error.retry_after == 60
        assert str(error) == "请求过于频繁 (请在 60 秒后重试)"

    def test_without_retry_after(self) -> None:
        error = BrainRateLimitError("限速")
        assert error.retry_after is None
        assert str(error) == "限速"

    def test_repr_with_retry_after(self) -> None:
        error = BrainRateLimitError("test", retry_after=30)
        assert repr(error) == "BrainRateLimitError('test', retry_after=30)"

    def test_repr_without_retry_after(self) -> None:
        error = BrainRateLimitError("test")
        assert repr(error) == "BrainRateLimitError('test', retry_after=None)"

    def test_is_brain_api_error(self) -> None:
        assert isinstance(BrainRateLimitError("x"), BrainAPIError)


class TestBrainQueueBusyError:
    """测试队列繁忙异常"""

    def test_create_error(self) -> None:
        error = BrainQueueBusyError("服务器队列繁忙")
        assert str(error) == "服务器队列繁忙"

    def test_repr(self) -> None:
        error = BrainQueueBusyError("busy")
        assert repr(error) == "BrainQueueBusyError('busy')"

    def test_is_brain_api_error(self) -> None:
        assert isinstance(BrainQueueBusyError("x"), BrainAPIError)

    def test_inherits_message(self) -> None:
        error = BrainQueueBusyError("test msg")
        assert error.message == "test msg"
