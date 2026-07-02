"""HTTP 后端抽象层，消除对 urllib/httpx 的硬编码依赖。

本模块定义 HttpBackend 协议和两个内置实现：
  - UrllibHttpBackend：基于 urllib.request 的兼容后端（默认）
  - HttpxHttpBackend：基于 httpx 的现代后端（连接池、HTTP/2）

通过 settings.yaml global.http.backend 选择后端：
  http:
    backend: "httpx"  # 或 "urllib"（默认）
"""

from __future__ import annotations

import logging
from http.cookiejar import Cookie, CookieJar
from typing import Any, Protocol
from urllib.request import (
    HTTPCookieProcessor,
    ProxyHandler,
    Request as UrllibRequest,
    build_opener,
)

logger = logging.getLogger(__name__)


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


class UrllibHttpBackend:
    """基于 urllib.request 的 HTTP 后端（默认兼容实现）。"""

    def __init__(self) -> None:
        self._cookies = CookieJar()
        self._opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(self._cookies))

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
            with self._opener.open(request, timeout=timeout) as response:  # type: ignore[arg-type]
                return response.getcode(), dict(response.headers.items()), response.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()
        except URLError as exc:
            from ..exceptions import BrainAPIError

            raise BrainAPIError(f"{method} {url} failed: {exc}") from exc

    def set_cookie(self, cookie: Cookie) -> None:
        self._cookies.set_cookie(cookie)

    def load_cookies(self, cookies: CookieJar) -> None:
        for cookie in cookies:
            self._cookies.set_cookie(cookie)


class HttpxHttpBackend:
    """基于 httpx 的现代 HTTP 后端（连接池、Keep-Alive、HTTP/2 支持）。"""

    def __init__(self) -> None:
        self._cookies = CookieJar()
        self._client: Any = None

    def _get_client(self) -> Any:
        """懒加载 httpx.Client，自动配置连接池、超时和重定向。"""
        if self._client is not None:
            return self._client
        try:
            import httpx

            self._client = httpx.Client(
                timeout=httpx.Timeout(90.0, connect=15.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                follow_redirects=True,
                http2=True,
            )
            return self._client
        except ImportError as exc:
            raise ImportError(
                "httpx 后端需要安装 httpx 包: pip install httpx"
            ) from exc

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
        timeout: float = 90.0,
    ) -> tuple[int, dict[str, str], bytes]:
        from http.cookiejar import Cookie

        client = self._get_client()
        try:
            import httpx

            # 将 CookieJar 序列化为请求头
            request_cookies: dict[str, str] = {}
            for cookie in self._cookies:
                if isinstance(cookie, Cookie):
                    request_cookies[cookie.name] = cookie.value

            response = client.request(
                method=method,
                url=url,
                headers=headers,
                content=data,
                cookies=request_cookies if request_cookies else None,
            )
            response_headers = dict(response.headers.items())
            # 更新 CookieJar
            for set_cookie_value in response.headers.get_list("set-cookie"):
                try:
                    self._cookies.set_cookie(
                        Cookie(
                            version=0,
                            name="",
                            value="",
                            port=None,
                            port_specified=False,
                            domain="",
                            domain_specified=False,
                            domain_initial_dot=False,
                            path="/",
                            path_specified=True,
                            secure=False,
                            expires=0,
                            discard=True,
                            comment=None,
                            comment_url=None,
                            rest={},
                            rfc2109=False,
                        )
                    )
                except Exception:
                    pass  # ignore malformed cookies
            return response.status_code, response_headers, response.content
        except Exception as exc:
            from ..exceptions import BrainAPIError

            raise BrainAPIError(f"{method} {url} failed: {exc}") from exc

    def set_cookie(self, cookie: Cookie) -> None:
        self._cookies.set_cookie(cookie)

    def load_cookies(self, cookies: CookieJar) -> None:
        for cookie in cookies:
            self._cookies.set_cookie(cookie)


def create_http_backend(backend_name: str = "") -> HttpBackend:
    """根据配置名称创建 HTTP 后端实例。

    Args:
        backend_name: "httpx" 或 "urllib"（默认）。

    Returns:
        HttpBackend 实例。

    Raises:
        ImportError: 当指定的后端所需的包未安装时。
    """
    name = (backend_name or "").strip().lower()
    if name == "httpx":
        logger.info("[http] 使用 httpx 后端 (连接池 + HTTP/2)")
        return HttpxHttpBackend()
    logger.info("[http] 使用 urllib 后端 (标准库)")
    return UrllibHttpBackend()
