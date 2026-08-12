"""API 端点 + HTTP 超时 + 响应头常量。

来源: config/constants_defaults.yaml 的 api.* / http.* 段。
"""

from __future__ import annotations

from ._constants_core import (
    _yaml_dict,
    _yaml_float,
    _yaml_int,
    _yaml_str,
)

# ---- API 端点 ----
API_BASE: str = _yaml_str("api", "base_url", default="https://api.worldquantbrain.com")
AUTH_URL: str = _yaml_str("api", "auth_url", default=f"{API_BASE}/authentication").replace(
    "{base}", API_BASE
)
DATA_FIELDS_URL: str = _yaml_str(
    "api", "data_fields_url", default=f"{API_BASE}/data-fields"
).replace("{base}", API_BASE)
SIMULATIONS_URL: str = _yaml_str(
    "api", "simulations_url", default=f"{API_BASE}/simulations"
).replace("{base}", API_BASE)
ALPHAS_URL: str = _yaml_str("api", "alphas_url", default=f"{API_BASE}/alphas").replace(
    "{base}", API_BASE
)
DEFAULT_RATE_LIMIT_MAX_RETRIES: int = _yaml_int("api", "default_rate_limit_max_retries", default=3)

DEFAULT_HEADERS: dict = _yaml_dict(
    "api",
    "headers",
    "default",
    default={
        "Accept": "application/json",
        "Content-Type": "application/json",
    },
)
VERSION_HEADER: dict[str, str] = _yaml_dict(
    "api", "headers", "version", default={"Accept": "application/json;version=2.0"}
)
SIM_ACCEPT_HEADER: dict[str, str] = _yaml_dict(
    "api", "headers", "simulation", default={"Accept": "application/json;version=3.0"}
)

# ---- HTTP 客户端超时 ----
SIMULATION_RETRY_WAIT: float = _yaml_float("http", "simulation_retry_wait", default=3.0)
