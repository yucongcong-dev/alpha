"""Brain API HTTP session, authentication and request retry mixin."""

from __future__ import annotations

import base64
import logging
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from ..config import (
    AUTH_URL,
    DEFAULT_HEADERS,
    get_http_request_timeout,
    get_rate_limit_default_wait,
    get_server_error_backoff_max,
    get_server_error_backoff_step,
)
from ..exceptions import BrainAPIError, BrainRateLimitError
from .api_types import ApiParams
from .payloads import safe_json_bytes
from .timing import doubled_retry_after, wait_seconds

logger = logging.getLogger(__name__)

_request_throttle_lock = threading.Lock()
_global_last_request_at: float = 0.0


class BrainSessionMixin:
    """Authentication and low-level HTTP request helpers for BrainClient."""

    email: str
    password: str
    min_request_interval: float
    rate_limit_max_retries: int
    opener: Any

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
                logger.warning(
                    "[rate-limit] %s %s attempt=%d/%d retry_after=%s",
                    method,
                    url,
                    attempt,
                    retries,
                    response_headers.get("Retry-After"),
                )
                wait_seconds(
                    doubled_retry_after(response_headers, default=get_rate_limit_default_wait()),
                    "rate limit",
                )
                continue
            if status == 401 and attempt < retries:
                logger.warning("[auth] session expired on %s %s, re-logging in...", method, url)
                self.login()
                continue
            if status in (500, 502, 503, 504):
                wait_seconds(
                    min(get_server_error_backoff_max(), attempt * get_server_error_backoff_step()),
                    f"server error {status}",
                )
                continue
            if expected is None or status in expected:
                return status, response_headers, content
            break

        if last_response is None:
            raise BrainAPIError(f"No response from {method} {url}")
        status, response_headers, content = last_response
        if status == 429:
            retry_after = doubled_retry_after(response_headers, default=get_rate_limit_default_wait())
            detail = safe_json_bytes(content)
            raise BrainRateLimitError(
                f"{method} {url} rate limited after {retries} attempts, "
                f"skip current template: {detail}",
                int(retry_after),
            )
        detail = safe_json_bytes(content)
        raise BrainAPIError(f"{method} {url} failed: {status} {detail}")

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
        if self.min_request_interval > 0:
            global _global_last_request_at
            with _request_throttle_lock:
                now = time.monotonic()
                elapsed = now - _global_last_request_at
                remaining = self.min_request_interval - elapsed
                _global_last_request_at = max(
                    now, _global_last_request_at + self.min_request_interval
                )
            if remaining > 0:
                wait_seconds(remaining, "global request throttle")
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

        request = Request(url=url, data=request_data, headers=headers or {}, method=method)
        try:
            with self.opener.open(request, timeout=get_http_request_timeout()) as response:
                return response.getcode(), dict(response.headers.items()), response.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()
        except URLError as exc:
            raise BrainAPIError(f"{method} {url} failed: {exc}") from exc
