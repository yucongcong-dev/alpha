"""Standard-library HTTP transport used by the BRAIN client."""

from __future__ import annotations

from collections.abc import Mapping
from http.cookiejar import Cookie, CookieJar
import threading
from typing import Protocol
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener
from urllib.request import Request as UrllibRequest


def response_header(headers: Mapping[str, str], name: str) -> str | None:
    """Return one HTTP response header using case-insensitive name matching."""
    normalized_name = name.casefold()
    return next(
        (value for key, value in headers.items() if key.casefold() == normalized_name),
        None,
    )


class HttpBackend(Protocol):
    """HTTP 后端协议：统一 request/response 接口，支持 Cookie 管理。"""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
        timeout: float = 90.0,
    ) -> tuple[int, dict[str, str], bytes]:
        """发送 HTTP 请求，返回 (status_code, response_headers, body_bytes)。"""
        ...

    def set_cookie(self, cookie: Cookie) -> None:
        """设置单个 cookie。"""
        ...

    def load_cookies(self, cookies: CookieJar) -> None:
        """批量导入 CookieJar 中的 cookie。"""
        ...

    def close(self) -> None:
        """Release resources owned by the HTTP backend."""
        ...

    def abort_active_requests(self) -> None:
        """Interrupt responses currently being read by the backend."""
        ...


class UrllibHttpBackend:
    """基于 urllib.request 的 HTTP 后端（默认兼容实现）。"""

    def __init__(self) -> None:
        self._cookies = CookieJar()
        self._opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(self._cookies))
        self._active_responses: set[object] = set()
        self._active_responses_lock = threading.Lock()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
        timeout: float = 90.0,
    ) -> tuple[int, dict[str, str], bytes]:
        from urllib.error import HTTPError, URLError

        request = UrllibRequest(url=url, data=data, headers=headers or {}, method=method)
        try:
            response = self._opener.open(request, timeout=timeout)
            with self._active_responses_lock:
                self._active_responses.add(response)
            try:
                return response.getcode(), dict(response.headers.items()), response.read()
            finally:
                with self._active_responses_lock:
                    self._active_responses.discard(response)
                close = getattr(response, "close", None)
                if callable(close):
                    close()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()
        except (URLError, TimeoutError) as exc:
            from ..exceptions import BrainTransientError

            raise BrainTransientError(f"{method} {url} failed: {exc}") from exc

    def set_cookie(self, cookie: Cookie) -> None:
        self._cookies.set_cookie(cookie)

    def load_cookies(self, cookies: CookieJar) -> None:
        for cookie in cookies:
            self._cookies.set_cookie(cookie)

    def close(self) -> None:
        """urllib keeps no explicit connection pool to close."""
        self.abort_active_requests()

    def abort_active_requests(self) -> None:
        """Close active responses without marking the backend closed.

        Closing a response from the stopping thread unblocks a worker that is
        currently reading a long-poll response.  The backend remains reusable
        for other lifecycle paths until its owner calls ``close``.  urllib
        cannot interrupt a request that is still resolving DNS, connecting, or
        waiting for response headers; callers mitigate that window by capping
        the per-request timeout before those phases.
        """
        with self._active_responses_lock:
            responses = tuple(self._active_responses)
        for response in responses:
            try:
                response.close()  # type: ignore[attr-defined]
            except Exception:
                pass
