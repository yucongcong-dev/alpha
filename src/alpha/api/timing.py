"""
Brain API 等待与 Retry-After 解析工具。
"""

from __future__ import annotations

import logging
import time

from ..config.runtime_values import get_runtime_config

logger = logging.getLogger(__name__)


def wait_seconds(seconds: float, reason: str, verbose: bool = True) -> None:
    """带日志地休眠，使退避与等待行为在输出中可见。"""
    seconds = max(seconds, 0.0)
    if seconds <= 0:
        return
    if verbose or seconds >= 10.0:
        logger.info("[wait] %s: sleeping %.1fs", reason, seconds)
    else:
        logger.debug("[wait] %s: sleeping %.1fs", reason, seconds)
    time.sleep(seconds)


def extract_retry_after(headers: dict[str, str], default: float = 5.0) -> float:
    """将 Retry-After HTTP 头解析为秒数，失败时使用默认值。"""
    value = headers.get("Retry-After")
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def doubled_retry_after(headers: dict[str, str], default: float = 5.0) -> float:
    """将服务端给出的等待时间翻倍，采用更保守的退避窗口。"""
    return extract_retry_after(headers, default=default) * 2.0


def polling_retry_after(
    headers: dict[str, str], default: float = 5.0, buffer_seconds: float | None = None
) -> float:
    """按服务端 Retry-After 轮询异步任务，并添加小缓冲时间。"""
    if buffer_seconds is None:
        buffer_seconds = get_runtime_config().http.polling_retry_buffer
    return extract_retry_after(headers, default=default) + max(buffer_seconds, 0.0)
