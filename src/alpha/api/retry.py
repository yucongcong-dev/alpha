"""API retry and login helpers."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, TypeVar

from ..config.runtime_values import get_runtime_config
from ..exceptions import (
    BrainAPIError,
    BrainHTTPError,
    BrainQueueBusyError,
    BrainRateLimitError,
    BrainStopRequested,
    BrainTransientError,
)
from .timing import wait_seconds

if TYPE_CHECKING:
    from .client import BrainClient

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def _retry_disposition(error: Exception) -> tuple[str, bool]:
    """Return the log label and whether one failure is retryable here."""
    if isinstance(error, BrainRateLimitError):
        return "rate limited", False
    if isinstance(error, BrainQueueBusyError):
        return "queue busy", False
    if isinstance(error, BrainTransientError):
        return "transport failure", True
    if isinstance(error, BrainAPIError):
        return "terminal API error", False
    return "failed", True


def _raise_if_aborted(name: str, should_abort: Callable[[], bool] | None) -> None:
    if should_abort is not None and should_abort():
        raise BrainStopRequested(f"{name} aborted because stop was requested")


def _wait_before_retry(
    name: str,
    retry_wait_seconds: float,
    should_abort: Callable[[], bool] | None,
    *,
    cause: Exception,
) -> None:
    if should_abort is not None and should_abort():
        raise BrainStopRequested(f"{name} aborted because stop was requested") from cause
    if should_abort is None:
        wait_seconds(retry_wait_seconds, f"retry {name}")
        return
    wait_seconds(
        retry_wait_seconds,
        f"retry {name}",
        should_abort=should_abort,
    )


def retry_operation(
    name: str,
    retries: int,
    func: Callable[[], _T],
    *,
    retry_wait_seconds: float | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> _T:
    """以有限重试执行单个阶段，并特殊处理限流与排队拥塞。"""
    if retry_wait_seconds is None:
        retry_wait_seconds = get_runtime_config().http.retry_operation_default_wait
    attempts = max(retries, 1)
    last_error: Exception | None = None
    last_attempt = 0

    for attempt in range(1, attempts + 1):
        last_attempt = attempt
        _raise_if_aborted(name, should_abort)
        try:
            return func()
        except BrainStopRequested:
            raise
        except Exception as exc:
            last_error = exc
            disposition, retryable = _retry_disposition(exc)
            logger.warning(
                "[retry] %s %s on attempt %d/%d: %s",
                name,
                disposition,
                attempt,
                attempts,
                exc,
            )
            if not retryable or attempt >= attempts:
                break
            _wait_before_retry(
                name,
                retry_wait_seconds,
                should_abort,
                cause=exc,
            )

    if isinstance(last_error, BrainHTTPError):
        raise last_error
    raise BrainAPIError(
        f"{name} failed after {last_attempt} attempts: {last_error}"
    ) from last_error


def is_invalid_credentials_error(error: Exception) -> bool:
    """判断异常是否表示 Brain 登录凭据无效。"""
    return "INVALID_CREDENTIALS" in str(error) or "401" in str(error)


def login_with_retry(client: BrainClient, retries: int) -> None:
    """通过统一的重试封装完成客户端登录。"""
    attempts = max(retries, 1)
    login_retry_wait = get_runtime_config().http.login_retry_wait
    try:
        retry_operation("login", attempts, client.login, retry_wait_seconds=login_retry_wait)
    except BrainAPIError as exc:
        if is_invalid_credentials_error(exc):
            raise BrainAPIError(
                "登录失败：账号或密码无效，脚本已重试 "
                f"{attempts} 次并停止。请确认官网可以登录；如果本地保存的是错误凭据，"
                "请删除 worldquant_brain_credentials.json 和 "
                "worldquant_brain_credentials.key 后重新运行脚本输入账号密码。"
            ) from exc
        raise BrainAPIError(
            f"登录失败：脚本已重试 {attempts} 次并停止。最后一次错误：{exc}"
        ) from exc
