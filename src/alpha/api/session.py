"""Brain API HTTP session, authentication and request retry mixin."""

from __future__ import annotations

import base64
import logging
import threading
import time
from typing import Any
from urllib.parse import urlencode

from ..config._constants_api import (
    AUTH_URL,
    DEFAULT_HEADERS,
)
from ..config.runtime_values import get_runtime_config
from ..exceptions import BrainAPIError, BrainHTTPError, BrainRateLimitError, BrainStopRequested
from .api_types import ApiParams
from .http_backend import HttpBackend, response_header
from .payloads import safe_json_bytes
from .timing import doubled_retry_after, wait_seconds

logger = logging.getLogger(__name__)

_request_throttle_condition = threading.Condition()
_global_last_request_at: float = 0.0
_global_rate_limit_until: float = 0.0


def _wait_for_request_slot(
    min_request_interval: float,
    *,
    request_deadline: float | None = None,
) -> None:
    """Wait until both the global interval and rate-limit embargo allow a request."""
    global _global_last_request_at

    with _request_throttle_condition:
        while True:
            now = time.monotonic()
            if request_deadline is not None and now >= request_deadline:
                raise BrainStopRequested("HTTP request deadline reached")
            allowed_at = max(
                _global_rate_limit_until,
                _global_last_request_at + min_request_interval,
            )
            remaining = allowed_at - now
            if remaining <= 0:
                _global_last_request_at = now
                return
            if request_deadline is not None:
                remaining = min(remaining, request_deadline - now)
            _request_throttle_condition.wait(timeout=remaining)


def _extend_rate_limit_deadline(retry_after_seconds: float) -> None:
    """Share a 429 backoff deadline across every client in this process."""
    global _global_rate_limit_until

    deadline = time.monotonic() + max(retry_after_seconds, 0.0)
    with _request_throttle_condition:
        if deadline <= _global_rate_limit_until:
            return
        _global_rate_limit_until = deadline
        _request_throttle_condition.notify_all()


def _wait_before_request_retry(
    seconds: float,
    reason: str,
    *,
    request_deadline: float | None,
) -> None:
    """Wait for a request retry without crossing the caller's deadline."""
    if request_deadline is None:
        wait_seconds(seconds, reason)
        return
    wait_seconds(
        seconds,
        reason,
        should_abort=lambda: time.monotonic() >= request_deadline,
    )


class BrainSessionMixin:
    """Authentication and low-level HTTP request helpers for BrainClient."""

    email: str
    password: str
    min_request_interval: float
    rate_limit_max_retries: int
    request_deadline: float | None
    _http_backend: HttpBackend

    def login(self) -> None:
        """使用 basic auth 登录并初始化会话 cookie。"""
        token = base64.b64encode(f"{self.email}:{self.password}".encode()).decode("ascii")
        status, _, content = self.raw_request(
            "POST",
            AUTH_URL,
            headers={**DEFAULT_HEADERS, "Authorization": f"Basic {token}"},
            data=b"{}",
        )
        if status not in (200, 201):
            detail = safe_json_bytes(content)
            raise BrainAPIError(f"Login failed: {status} {detail}")
        logger.info("[auth] login success")

    def request(
        self,
        method: str,
        url: str,
        *,
        expected: set[int] | None = None,
        headers: dict[str, str] | None = None,
        retries: int | None = None,
        **kwargs: Any,
    ) -> tuple[int, dict[str, str], bytes]:
        """发送带共享头、退避与重试策略的 HTTP 请求。"""
        merged_headers = dict(DEFAULT_HEADERS)
        http_config = get_runtime_config().http
        if headers:
            merged_headers.update(headers)
        retries = self.rate_limit_max_retries if retries is None else max(retries, 1)

        last_response: tuple[int, dict[str, str], bytes] | None = None
        for attempt in range(1, retries + 1):
            status, response_headers, content = self.raw_request(
                method, url, headers=merged_headers, **kwargs
            )
            last_response = (status, response_headers, content)
            if status == 429:
                retry_after_header = response_header(response_headers, "Retry-After")
                retry_after_seconds = doubled_retry_after(
                    response_headers, default=http_config.rate_limit_default_wait
                )
                _extend_rate_limit_deadline(retry_after_seconds)
                logger.warning(
                    "[rate-limit] %s %s attempt=%d/%d retry_after=%s",
                    method,
                    url,
                    attempt,
                    retries,
                    retry_after_header,
                )
                if attempt < retries:
                    _wait_before_request_retry(
                        retry_after_seconds,
                        "rate limit",
                        request_deadline=self.request_deadline,
                    )
                continue
            if status == 401 and attempt < retries:
                logger.warning("[auth] session expired on %s %s, re-logging in...", method, url)
                self.login()
                continue
            if status in (500, 502, 503, 504):
                if attempt < retries:
                    _wait_before_request_retry(
                        min(
                            http_config.server_error_backoff_max,
                            attempt * http_config.server_error_backoff_step,
                        ),
                        f"server error {status}",
                        request_deadline=self.request_deadline,
                    )
                continue
            if expected is None or status in expected:
                return status, response_headers, content
            break

        if last_response is None:
            raise BrainAPIError(f"No response from {method} {url}")
        status, response_headers, content = last_response
        if status == 429:
            retry_after_seconds = doubled_retry_after(
                response_headers, default=http_config.rate_limit_default_wait
            )
            detail = safe_json_bytes(content)
            raise BrainRateLimitError(
                f"{method} {url} rate limited after {retries} attempts, "
                f"skip current template: {detail}",
                int(retry_after_seconds),
            )
        detail = safe_json_bytes(content)
        raise BrainHTTPError(
            f"{method} {url} failed: {status} {detail}",
            status=status,
        )

    def raw_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: ApiParams | None = None,
        data: Any | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """执行一次不带高层重试策略的原始 HTTP 请求。"""
        _wait_for_request_slot(
            self.min_request_interval,
            request_deadline=self.request_deadline,
        )
        if params:
            query = urlencode(params)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"

        request_data: bytes | None
        if data is None:
            request_data = None
        elif isinstance(data, bytes):
            request_data = data
        else:
            request_data = str(data).encode("utf-8")

        request_timeout = get_runtime_config().http.request_timeout
        if self.request_deadline is not None:
            remaining = self.request_deadline - time.monotonic()
            if remaining <= 0:
                raise BrainStopRequested("HTTP request deadline reached")
            request_timeout = min(request_timeout, remaining)

        return self._http_backend.request(
            method=method,
            url=url,
            headers=headers,
            data=request_data,
            timeout=request_timeout,
        )
