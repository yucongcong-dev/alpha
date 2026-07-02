"""
Brain API 客户端模块

本模块提供与 WorldQuant Brain API 进行交互的客户端类和辅助函数，
支持用户认证、Alpha 模拟计算、结果轮询和提交等操作。

主要功能：
    - HTTP 请求发送与重试处理
    - 速率限制与队列拥塞处理
    - 模拟任务创建与轮询
    - Alpha 结果查询与提交
    - 多线程客户端管理

模块内容：
    - retry_operation: 统一阶段重试封装
    - login_with_retry: 登录重试封装
    - BrainClient: 主 API 客户端类
    - WorkerClientFactory: 多线程客户端工厂

响应 payload 解析已拆到 api.payloads，等待与 Retry-After 解析已拆到 api.timing。
本模块仍导入这些 helper 以保持旧调用路径兼容。
"""

from __future__ import annotations

from collections.abc import Callable
from http.cookiejar import CookieJar
import logging
import threading
from typing import TypeVar
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener

from ..config.constants import DEFAULT_RATE_LIMIT_MAX_RETRIES
from ..config.getters import get_login_retry_wait, get_retry_operation_default_wait
from ..exceptions import (
    BrainAPIError,
    BrainQueueBusyError,
    BrainRateLimitError,
)
from ..models.runtime import ApiClientOptions
from .alphas import BrainAlphasMixin
from .fields import BrainFieldsMixin
from .session import BrainSessionMixin
from .simulations import BrainSimulationsMixin
from .timing import wait_seconds

logger = logging.getLogger(__name__)

# ============================================================================
# 辅助函数 - 重试与登录
# ============================================================================

_T = TypeVar("_T")


def retry_operation(
    name: str,
    retries: int,
    func: Callable[[], _T],
    *,
    retry_wait_seconds: float | None = None,
) -> _T:
    """
    以有限重试执行单个阶段，并特殊处理限流与排队拥塞。

    对指定的操作进行多次重试，在每次失败后等待指定时间。
    对速率限制和队列拥塞错误会立即终止重试，跳过当前模板。

    Args:
        name: 操作名称，用于日志输出。
        retries: 最大重试次数。
        func: 要执行的函数，不接受参数。
        retry_wait_seconds: 重试之间的等待秒数。默认为 2.0。

    Returns:
        Any: 操作函数的返回值。

    Raises:
        BrainAPIError: 当所有重试都失败时抛出，
            包含最后一次错误信息。

    Example:
        >>> def my_operation():
        ...     # 执行某些 API 操作
        ...     return {"status": "ok"}
        >>> result = retry_operation("simulate", 3, my_operation)
        >>> print(result)
        {'status': 'ok'}

    Note:
        - 用于 login/simulate/check/submit 等阶段的统一封装
        - 每次失败都会打印日志
        - 速率限制和队列拥塞错误会立即跳过，不再重试
        - 内层 API 调用已耗尽自身的速率限制重试时，
          立即跳过当前模板而不是重新运行整个阶段
    """
    # 用于 login/simulate/check/submit 的通用阶段封装：
    # - 每次失败都打印日志
    # - 遵守显式的速率限制重试窗口
    # - 仅在配置的尝试次数后才失败
    if retry_wait_seconds is None:
        retry_wait_seconds = get_retry_operation_default_wait()
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            return func()
        except BrainRateLimitError as exc:
            last_error = exc
            logger.warning(
                "[retry] %s rate limited on attempt %d/%d: %s",
                name,
                attempt,
                retries,
                exc,
            )
            # 当内层 API 调用已耗尽自身的速率限制重试时，
            # 立即跳过当前模板而不是重新运行整个阶段
            break
        except BrainQueueBusyError as exc:
            last_error = exc
            logger.warning(
                "[retry] %s queue busy on attempt %d/%d: %s",
                name,
                attempt,
                retries,
                exc,
            )
            # 队列拥塞也应立即跳过当前模板，
            # 让主循环可以降低运行时并发并冷却
            break
        except BrainAPIError as exc:
            # poll_simulation 内部已耗尽轮询/等待预算，
            # 不应再次重试整个阶段（否则有效超时成倍增长）
            last_error = exc
            logger.warning(
                "[retry] %s exhausted on attempt %d/%d: %s",
                name,
                attempt,
                retries,
                exc,
            )
            break
        except Exception as exc:
            last_error = exc
            logger.warning(
                "[retry] %s failed on attempt %d/%d: %s",
                name,
                attempt,
                retries,
                exc,
            )
            if attempt < retries:
                wait_seconds(retry_wait_seconds, f"retry {name}")

    raise BrainAPIError(f"{name} failed after {retries} attempts: {last_error}")


def is_invalid_credentials_error(error: Exception) -> bool:
    """
    判断异常是否表示 Brain 登录凭据无效。

    检查异常消息中是否包含指示无效凭据的关键字符串。

    Args:
        error: 要检查的异常对象。

    Returns:
        bool: 如果异常表示无效凭据返回 True，否则返回 False。

    Example:
        >>> exc = BrainAPIError("Login failed: INVALID_CREDENTIALS")
        >>> is_invalid_credentials_error(exc)
        True

        >>> exc = BrainAPIError("Login failed: 401 Unauthorized")
        >>> is_invalid_credentials_error(exc)
        True

        >>> exc = BrainAPIError("Network error")
        >>> is_invalid_credentials_error(exc)
        False

    Note:
        - 检查的字符串："INVALID_CREDENTIALS", "401"
        - 用于区分凭据错误和网络/服务器错误
    """
    return "INVALID_CREDENTIALS" in str(error) or "401" in str(error)


def login_with_retry(client: BrainClient, retries: int) -> None:
    """
    通过统一的重试封装完成客户端登录。

    使用 retry_operation 对登录操作进行重试，
    并对无效凭据错误提供详细的中文错误提示。

    Args:
        client: BrainClient 实例，要进行登录的客户端。
        retries: 最大重试次数。

    Raises:
        BrainAPIError: 当登录失败时抛出，包含详细的中文错误提示。

    Example:
        >>> client = BrainClient("user@example.com", "password")
        >>> login_with_retry(client, retries=3)

    Note:
        - 登录操作被单独封装，以便调用者可以为其设置独立的重试策略
        - 无效凭据错误会提供详细的中文提示，建议删除凭证文件重新输入
        - 其他错误也会提供清晰的中文提示
    """
    # 登录被单独封装，以便调用者可以为其设置独立的重试策略
    # 和比低层 HTTP 错误更清晰的最终消息
    attempts = max(retries, 1)
    try:
        retry_operation("login", attempts, client.login, retry_wait_seconds=get_login_retry_wait())
    except BrainAPIError as exc:
        if is_invalid_credentials_error(exc):
            raise BrainAPIError(
                "登录失败：账号或密码无效，脚本已重试 "
                f"{attempts} 次并停止。请确认官网可以登录；如果本地保存的是错误凭据，"
                "请删除 worldquant_brain_credentials.json 和 "
                "worldquant_brain_credentials.key 后重新运行脚本输入账号密码。"
            ) from exc
        raise BrainAPIError(
            f"登录失败：脚本已重试 {attempts} 次并停止。最后一次错误：{exc}"
        ) from exc


# ============================================================================
# BrainClient 类
# ============================================================================


class BrainClient(BrainSessionMixin, BrainFieldsMixin, BrainSimulationsMixin, BrainAlphasMixin):
    """
    面向 WorldQuant Brain 认证与 Alpha 接口的轻量 HTTP 客户端。

    提供与 WorldQuant Brain API 进行交互的核心功能，包括：
    - 用户认证与会话管理
    - HTTP 请求发送与重试处理
    - 速率限制与错误处理
    - 数据集字段查询
    - 模拟任务创建与轮询
    - Alpha 查询与提交

    Attributes:
        email (str): 用户邮箱地址。
        password (str): 用户密码。
        min_request_interval (float): 最小请求间隔（秒），全局共享节流时钟。
        rate_limit_max_retries (int): 速率限制时的最大重试次数。
        cookies (CookieJar): HTTP Cookie 存储容器。
        opener: urllib 的 opener 对象，用于发送请求。

    Example:
        >>> client = BrainClient("user@example.com", "password", min_request_interval=0.5)
        >>> client.login()
        [auth] login success
        >>> # 使用客户端进行 API 操作

    Note:
        - 所有 HTTP 请求都通过 request 方法统一处理
        - 请求方法自动处理速率限制、重试和错误
        - Cookie 状态由 urllib 自动管理
        - 不适合跨线程共享，每个线程应使用独立客户端
    """

    def __init__(
        self,
        email: str,
        password: str,
        min_request_interval: float = 0.0,
        rate_limit_max_retries: int = DEFAULT_RATE_LIMIT_MAX_RETRIES,
    ) -> None:
        """
        初始化客户端凭证、节流参数与 cookie/opener 状态。

        创建 BrainClient 实例，设置用户凭证、请求节流参数，
        并初始化 Cookie 存储和 HTTP opener。

        Args:
            email: WorldQuant Brain 账号的邮箱地址。
            password: WorldQuant Brain 账号的密码。
            min_request_interval: 最小请求间隔（秒）。
                用于全局请求节流，避免过于频繁的请求。默认为 0.0。
            rate_limit_max_retries: 遇到速率限制时的最大重试次数。
                默认为 DEFAULT_RATE_LIMIT_MAX_RETRIES。

        Raises:
            BrainAPIError: 当邮箱或密码为空时抛出。

        Example:
            >>> client = BrainClient(
            ...     "user@example.com",
            ...     "password",
            ...     min_request_interval=0.5,
            ...     rate_limit_max_retries=3,
            ... )

        Note:
            - min_request_interval 使用全局共享时钟，所有客户端实例协调节流
            - rate_limit_max_retries 至少为 1
            - opener 和 cookie 状态不适合跨线程共享
        """
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


# ============================================================================
# WorkerClientFactory 类
# ============================================================================


class WorkerClientFactory:
    """
    为每个工作线程提供独立且已认证的 BrainClient。

    urllib opener/cookie 状态跨线程共享不够安全，
    所以每个工作线程懒加载创建并登录自己的客户端，恰好一次。

    Attributes:
        options (ApiClientOptions): worker 客户端窄配置。
        email (str): 用户邮箱地址。
        password (str): 用户密码。
        _local (threading.local): 线程本地存储。

    Example:
        >>> import argparse
        >>> options = ApiClientOptions(
        ...     min_request_interval=0.5, rate_limit_max_retries=3, login_retries=2
        ... )
        >>> factory = WorkerClientFactory(options, "user@example.com", "password")
        >>> # 在工作线程中
        >>> client = factory.get_client()
        >>> # client 已登录且独立于其他线程的客户端

    Note:
        - 每个线程首次调用 get_client 时会创建并登录客户端
        - 同一线程后续调用返回相同的客户端实例
        - 使用 threading.local 实现线程隔离
        - 客户端创建时会使用 args 中的配置参数
    """

    def __init__(self, options: ApiClientOptions, email: str, password: str) -> None:
        """
        记录线程级客户端创建所需的参数与凭证。

        存储 args 和凭证，供后续线程本地客户端创建使用。

        Args:
            options: worker 客户端窄配置，包含请求节流、限流重试和登录重试参数。
            email: WorldQuant Brain 账号的邮箱地址。
            password: WorldQuant Brain 账号的密码。

        Example:
            >>> options = ApiClientOptions(
            ...     min_request_interval=0.5, rate_limit_max_retries=3, login_retries=2
            ... )
            >>> factory = WorkerClientFactory(options, "user@example.com", "password")
        """
        self.options = options
        self.email = email
        self.password = password
        self._local = threading.local()

    def get_client(self) -> BrainClient:
        """
        获取当前线程专属客户端，不存在时懒加载并登录。

        返回当前线程的 BrainClient 实例。如果实例不存在，
        创建新客户端、登录并存储到线程本地存储。

        Returns:
            BrainClient: 当前线程的已登录客户端实例。

        Example:
            >>> client = factory.get_client()
            >>> print(client.email)
            user@example.com

        Note:
            - 使用线程本地存储确保线程安全
            - 每个线程恰好创建一次客户端
            - 创建时自动登录，使用 login_with_retry
            - 使用 args 中的配置参数创建客户端
        """
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
