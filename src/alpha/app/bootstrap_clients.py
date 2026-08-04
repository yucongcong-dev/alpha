"""Credential resolution and API client creation for bootstrap."""

from __future__ import annotations

from ..api.client import BrainClient, WorkerClientFactory
from ..models.runtime_options import ApiClientOptions
from ..models.runtime_protocols import ApiClientArgs
from .bootstrap_types import ApiClientServices, CredentialServices, ResolvedCredentials


def resolve_credentials(
    credentials: ResolvedCredentials,
    *,
    services: CredentialServices,
) -> tuple[str, str]:
    """Resolve credentials without mutating the runtime args object."""
    email, password = services.load_credentials(credentials)
    return str(email or ""), str(password or "")


def create_and_login_client(
    email: str,
    password: str,
    args: ApiClientArgs,
    *,
    services: ApiClientServices,
) -> tuple[BrainClient, WorkerClientFactory]:
    """创建 Brain API 客户端并完成登录，同时创建工作线程客户端工厂。"""
    client_options = ApiClientOptions.from_args(args)
    http_backend = services.get_runtime_config().http.backend
    bootstrap_client = BrainClient(
        email,
        password,
        min_request_interval=client_options.min_request_interval,
        rate_limit_max_retries=client_options.rate_limit_max_retries,
        http_backend=http_backend,
    )
    try:
        services.login_with_retry(bootstrap_client, client_options.login_retries)
        client_factory = WorkerClientFactory(
            client_options,
            email,
            password,
            http_backend=http_backend,
        )
    except BaseException:
        bootstrap_client.close()
        raise
    return bootstrap_client, client_factory
