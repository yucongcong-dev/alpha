"""
Brain API client composition entry.

Brain API 客户端组合入口。

HTTP session, fields, simulations, alpha actions, timing, payload parsing, and
retry helpers live in focused modules. This file keeps the public BrainClient
and WorkerClientFactory entry points stable.
"""

from __future__ import annotations

from http.cookiejar import CookieJar
import threading
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener

from ..config.constants import DEFAULT_RATE_LIMIT_MAX_RETRIES
from ..exceptions import BrainAPIError
from ..models.runtime import ApiClientOptions
from .alphas import BrainAlphasMixin
from .fields import BrainFieldsMixin
from .retry import (
    is_invalid_credentials_error,
    login_with_retry,
    retry_operation,
)
from .session import BrainSessionMixin
from .simulations import BrainSimulationsMixin
from .timing import wait_seconds

__all__ = [
    "BrainClient",
    "WorkerClientFactory",
    "is_invalid_credentials_error",
    "login_with_retry",
    "retry_operation",
    "wait_seconds",
]


class BrainClient(BrainSessionMixin, BrainFieldsMixin, BrainSimulationsMixin, BrainAlphasMixin):
    """面向 WorldQuant Brain 认证与 Alpha 接口的轻量 HTTP 客户端。"""

    def __init__(
        self,
        email: str,
        password: str,
        min_request_interval: float = 0.0,
        rate_limit_max_retries: int = DEFAULT_RATE_LIMIT_MAX_RETRIES,
    ) -> None:
        """初始化客户端凭证、节流参数与 cookie/opener 状态。"""
        if not email or not password:
            raise BrainAPIError(
                "Missing credentials. Set --email/--password or WQB_EMAIL/WQB_PASSWORD."
            )
        self.email = email
        self.password = password
        self.min_request_interval = max(min_request_interval, 0.0)
        self.rate_limit_max_retries = max(rate_limit_max_retries, 1)
        self.cookies = CookieJar()
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(self.cookies))


class WorkerClientFactory:
    """为每个工作线程提供独立且已认证的 BrainClient。"""

    def __init__(self, options: ApiClientOptions, email: str, password: str) -> None:
        """记录线程级客户端创建所需的参数与凭证。"""
        self.options = options
        self.email = email
        self.password = password
        self._local = threading.local()

    def get_client(self) -> BrainClient:
        """获取当前线程专属客户端，不存在时懒加载并登录。"""
        client: BrainClient | None = getattr(self._local, "client", None)
        if client is not None:
            return client

        client = BrainClient(
            self.email,
            self.password,
            min_request_interval=self.options.min_request_interval,
            rate_limit_max_retries=self.options.rate_limit_max_retries,
        )
        login_with_retry(client, self.options.login_retries)
        self._local.client = client
        return client
