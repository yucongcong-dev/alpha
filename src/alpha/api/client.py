"""
Brain API client composition entry.

Brain API 客户端组合入口。

HTTP session, fields, simulations, alpha actions, timing, payload parsing, and
retry helpers live in focused modules. This file keeps the public BrainClient
and WorkerClientFactory entry points stable.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
import threading
import time

from ..config._constants_api import DEFAULT_RATE_LIMIT_MAX_RETRIES
from ..config.runtime_values import HttpRuntimeConfig, load_http_runtime_config
from ..exceptions import BrainAPIError
from ..models.runtime_options import ApiClientOptions
from .alphas import BrainAlphasMixin
from .fields import BrainFieldsMixin
from .http_backend import UrllibHttpBackend
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
    """面向 WorldQuant Brain 认证与 Alpha 接口的轻量 urllib 客户端。"""

    def __init__(
        self,
        email: str,
        password: str,
        min_request_interval: float = 0.0,
        rate_limit_max_retries: int = DEFAULT_RATE_LIMIT_MAX_RETRIES,
        http_config: HttpRuntimeConfig | None = None,
        request_deadline: float | None = None,
        request_abort: Callable[[], bool] | None = None,
    ) -> None:
        """初始化客户端凭证、节流参数与 HTTP 后端。"""
        if not email or not password:
            raise BrainAPIError(
                "Missing credentials. Set --email/--password or WQB_EMAIL/WQB_PASSWORD."
            )
        self.email = email
        self.password = password
        self.min_request_interval = max(min_request_interval, 0.0)
        self.rate_limit_max_retries = max(rate_limit_max_retries, 1)
        self.http_config = http_config or load_http_runtime_config()
        self.request_deadline = request_deadline
        self.request_abort = request_abort
        self._http_backend = UrllibHttpBackend()

    def close(self) -> None:
        """Release resources held by the HTTP backend."""
        self._http_backend.close()

    def abort_active_requests(self) -> None:
        """Interrupt active HTTP reads while keeping the client usable."""
        self._http_backend.abort_active_requests()

    def __enter__(self) -> BrainClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class WorkerClientFactory:
    """为每个工作线程提供独立且已认证的 BrainClient。"""

    def __init__(self, options: ApiClientOptions, email: str, password: str) -> None:
        """记录线程级客户端创建所需的参数与凭证。"""
        self.options = options
        self.email = email
        self.password = password
        self._local = threading.local()
        self._clients: list[BrainClient] = []
        self._clients_lock = threading.Lock()
        self._closed: bool = False

    def get_client(
        self,
        *,
        request_deadline: float | None = None,
        request_abort: Callable[[], bool] | None = None,
    ) -> BrainClient:
        """获取当前线程专属客户端，不存在时懒加载并登录。"""
        client: BrainClient | None = getattr(self._local, "client", None)
        if client is not None:
            client.request_deadline = request_deadline
            client.request_abort = request_abort
            return client

        client = BrainClient(
            self.email,
            self.password,
            min_request_interval=self.options.min_request_interval,
            rate_limit_max_retries=self.options.rate_limit_max_retries,
            http_config=self.options.http_config,
            request_deadline=request_deadline,
            request_abort=request_abort,
        )
        initialized = False
        try:
            if request_deadline is None and request_abort is None:
                login_with_retry(client, self.options.login_retries)
            else:

                def _abort_requested() -> bool:
                    return bool(request_abort is not None and request_abort()) or bool(
                        request_deadline is not None and time.monotonic() >= request_deadline
                    )

                login_with_retry(
                    client,
                    self.options.login_retries,
                    should_abort=_abort_requested,
                )
            initialized = True
        finally:
            # 只在初始化失败时释放半成品客户端；close 出错不能掩盖原始异常。
            if not initialized:
                with suppress(Exception):
                    client.close()
        with self._clients_lock:
            if self._closed:
                client.close()
                raise BrainAPIError("Worker client factory is closed")
            self._clients.append(client)
        self._local.client = client
        return client

    def close(self) -> None:
        """Close all worker clients after their executor has stopped."""
        with self._clients_lock:
            if self._closed:
                return
            self._closed = True
            clients = tuple(self._clients)
            self._clients.clear()
        for client in clients:
            client.close()
        if hasattr(self._local, "client"):
            del self._local.client

    def abort_active_requests(self) -> None:
        """Interrupt active requests without closing worker clients."""
        with self._clients_lock:
            clients = tuple(self._clients)
        for client in clients:
            client.abort_active_requests()
