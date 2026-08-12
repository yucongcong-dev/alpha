"""Credential resolution and API client creation for bootstrap."""

from __future__ import annotations

from contextlib import suppress

from ..api.client import BrainClient, WorkerClientFactory, login_with_retry
from ..io.credentials import load_credentials
from ..models.runtime_options import ApiClientOptions, CredentialLoadOptions


def resolve_credentials(
    credentials: CredentialLoadOptions,
) -> tuple[str, str]:
    """Resolve credentials without mutating the runtime args object."""
    email, password = load_credentials(credentials)
    return str(email or ""), str(password or "")


def create_and_login_client(
    email: str,
    password: str,
    client_options: ApiClientOptions,
) -> tuple[BrainClient, WorkerClientFactory]:
    """创建 Brain API 客户端并完成登录，同时创建工作线程客户端工厂。"""
    bootstrap_client = BrainClient(
        email,
        password,
        min_request_interval=client_options.min_request_interval,
        rate_limit_max_retries=client_options.rate_limit_max_retries,
    )
    initialized = False
    try:
        login_with_retry(bootstrap_client, client_options.login_retries)
        client_factory = WorkerClientFactory(
            client_options,
            email,
            password,
        )
        initialized = True
    finally:
        # 只在初始化失败时释放半成品客户端；close 出错不能掩盖原始异常。
        if not initialized:
            with suppress(Exception):
                bootstrap_client.close()
    return bootstrap_client, client_factory
