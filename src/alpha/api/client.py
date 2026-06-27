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
    - wait_seconds: 带日志的休眠函数
    - extract_retry_after: 解析 Retry-After 头
    - doubled_retry_after: 双倍等待时间
    - polling_retry_after: 轮询等待时间
    - first_non_empty: 返回第一个非空值
    - safe_json_bytes: 安全解析 JSON
    - simulation_payload_is_pending: 判断模拟状态
    - BrainClient: 主 API 客户端类
    - WorkerClientFactory: 多线程客户端工厂
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import threading
import time
from http.cookiejar import CookieJar
from typing import Any, Callable, Iterable, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from ..config import (
    ALPHAS_URL,
    API_BASE,
    AUTH_URL,
    DATA_FIELDS_URL,
    DEFAULT_HEADERS,
    DEFAULT_RATE_LIMIT_MAX_RETRIES,
    HTTP_REQUEST_TIMEOUT,
    LOGIN_RETRY_WAIT,
    POLLING_DEFAULT_WAIT,
    POLLING_NO_RETRY_AFTER_WAIT,
    POLLING_RETRY_BUFFER,
    RATE_LIMIT_DEFAULT_WAIT,
    RETRY_OPERATION_DEFAULT_WAIT,
    SERVER_ERROR_BACKOFF_MAX,
    SERVER_ERROR_BACKOFF_STEP,
    SIM_ACCEPT_HEADER,
    SIMULATIONS_URL,
    VERSION_HEADER,
)
from ..exceptions import (
    BrainAPIError,
    BrainQueueBusyError,
    BrainRateLimitError,
)
from ..utils.helpers import first_non_empty

logger = logging.getLogger(__name__)

# ============================================================================
# 辅助函数 - 时间与等待
# ============================================================================

def wait_seconds(seconds: float, reason: str, verbose: bool = True) -> None:
    """
    带日志地休眠，使退避与等待行为在输出中可见。

    在控制台打印等待原因和等待时间，然后休眠指定秒数。
    这样所有的暂停操作都会在日志中留下痕迹，便于调试。

    Args:
        seconds: 要休眠的秒数。如果小于等于 0，不会实际休眠。
        reason: 等待原因描述，会显示在日志消息中。
        verbose: 是否打印 INFO 级别日志。默认为 True。
            对于短等待（<10秒），建议设为 False 以减少日志噪音。

    Example:
        >>> wait_seconds(3.5, "rate limit")
        [wait] rate limit: sleeping 3.5s

        >>> wait_seconds(0, "no wait needed")
        # 不打印任何消息，不执行休眠

        >>> wait_seconds(5.0, "routine poll", verbose=False)
        # 不打印日志，但会执行休眠

    Note:
        - 秒数会自动调整为非负值
        - 只在秒数 > 0 时才打印日志和执行休眠
        - 使用 time.sleep 实现，休眠期间程序阻塞
        - verbose=False 时仍会执行休眠，但不打印日志
    """
    # 集中化的休眠辅助函数，使每次暂停都在日志中可见
    seconds = max(seconds, 0.0)
    if seconds > 0:
        # 短等待使用 DEBUG 级别，长等待使用 INFO 级别
        if verbose or seconds >= 10.0:
            logger.info("[wait] %s: sleeping %.1fs", reason, seconds)
        else:
            logger.debug("[wait] %s: sleeping %.1fs", reason, seconds)
        time.sleep(seconds)


def extract_retry_after(
    headers: dict[str, str],
    default: float = 5.0
) -> float:
    """
    将 Retry-After HTTP 头解析为秒数，失败时使用保守默认值。

    解析 HTTP 响应头中的 Retry-After 字段，返回等待秒数。
    如果字段不存在或无法解析为数字，返回默认值。

    Args:
        headers: HTTP 响应头字典。
        default: 解析失败时的默认等待秒数。默认为 5.0。

    Returns:
        float: 等待秒数。如果 Retry-After 存在且可解析，
            返回解析后的值；否则返回 default。

    Example:
        >>> headers = {"Retry-After": "10"}
        >>> extract_retry_after(headers)
        10.0

        >>> headers = {}
        >>> extract_retry_after(headers, default=3.0)
        3.0

        >>> headers = {"Retry-After": "invalid"}
        >>> extract_retry_after(headers)
        5.0

    Note:
        - Retry-After 字段不一定总是存在或总是数字
        - 保持安全的默认值用于所有速率限制和异步轮询场景
        - 不会抛出异常，始终返回数值
    """
    # Retry-After 不保证存在或可解析为数字，
    # 为所有速率限制和异步轮询路径保持安全的默认值
    value = headers.get("Retry-After")
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def doubled_retry_after(
    headers: dict[str, str],
    default: float = 5.0
) -> float:
    """
    将服务端给出的等待时间翻倍，采用更保守的退避窗口。

    使用 extract_retry_after 解析等待时间，然后乘以 2，
    以减少对慢速后端队列的重复轮询。

    Args:
        headers: HTTP 响应头字典。
        default: 解析失败时的默认等待秒数。默认为 5.0。

    Returns:
        float: 双倍等待秒数。计算方式：
            extract_retry_after(headers, default) * 2.0

    Example:
        >>> headers = {"Retry-After": "10"}
        >>> doubled_retry_after(headers)
        20.0

        >>> headers = {}
        >>> doubled_retry_after(headers, default=5.0)
        10.0

    Note:
        - 在 API 响应慢时采用更保守的退避策略
        - 使用 2 倍的建议等待时间，减少重复轮询慢速后端队列
    """
    # 当 API 要求稍后返回时采用保守策略；
    # 使用 2 倍的建议等待时间，减少重复轮询慢速后端队列
    return extract_retry_after(headers, default=default) * 2.0


def polling_retry_after(
    headers: dict[str, str],
    default: float = 5.0,
    buffer_seconds: float = POLLING_RETRY_BUFFER
) -> float:
    """
    按服务端 Retry-After 轮询异步任务，并添加小缓冲时间。

    使用 extract_retry_after 解析等待时间，然后加上缓冲秒数，
    用于时钟和网络抖动的补偿，但不加倍等待时间。

    Args:
        headers: HTTP 响应头字典。
        default: 解析失败时的默认等待秒数。默认为 5.0。
        buffer_seconds: 缓冲秒数，用于时钟/网络抖动补偿。
            默认为 1.0。

    Returns:
        float: 等待秒数。计算方式：
            extract_retry_after(headers, default) + max(buffer_seconds, 0.0)

    Example:
        >>> headers = {"Retry-After": "10"}
        >>> polling_retry_after(headers, default=5.0, buffer_seconds=1.0)
        11.0

        >>> headers = {}
        >>> polling_retry_after(headers, default=5.0, buffer_seconds=2.0)
        7.0

    Note:
        - 用于模拟轮询，平台已经告诉我们何时返回
        - 加上小缓冲时间用于时钟/网络抖动，但不加倍队列时间
    """
    # 模拟轮询时，平台已经告诉我们何时返回
    # 为时钟/网络抖动加上小缓冲时间，但不加倍队列时间
    return extract_retry_after(headers, default=default) + max(buffer_seconds, 0.0)


# ============================================================================
# 辅助函数 - 数据处理
# ============================================================================


def safe_json_bytes(content: bytes) -> dict[str, Any]:
    """
    安全解码 JSON 字节内容，并保留可调试的原始文本回退。

    尝试将字节内容解析为 JSON 字典。如果解析成功，
    返回解析后的字典；如果解析失败，返回包含原始文本
    （截断到 500 字符）的字典，便于调试。

    Args:
        content: HTTP 响应的字节内容。

    Returns:
        Dict[str, Any]: 解析结果字典。
            - 成功解析时：返回解析后的 JSON 字典
            - 解析非字典 JSON 时：返回 {"data": 解析结果}
            - 解析失败时：返回 {"text": 截断的原始文本}

    Example:
        >>> content = b'{"status": "ok"}'
        >>> safe_json_bytes(content)
        {'status': 'ok'}

        >>> content = b'[1, 2, 3]'
        >>> safe_json_bytes(content)
        {'data': [1, 2, 3]}

        >>> content = b'invalid json'
        >>> safe_json_bytes(content)
        {'text': 'invalid json'}

    Note:
        - 尝试将原始字节转换为字典，尽可能保留结构化数据
        - 不让格式错误的响应体在调试时隐藏原始响应文本
        - 失败时截断原始文本到 500 字符，避免日志过长
    """
    # 尽可能将原始字节转换为字典，
    # 不让格式错误的响应体在调试时隐藏原始响应文本
    try:
        data = json.loads(content.decode("utf-8"))
        if isinstance(data, dict):
            return data
        return {"data": data}
    except ValueError:
        return {"text": content.decode("utf-8", errors="replace")[:500]}


def simulation_payload_is_pending(
    payload: dict[str, Any]
) -> tuple[bool, str, Any]:
    """
    从 simulation 响应体判断任务是否仍在等待。

    检查模拟任务响应的状态字段，判断任务是否仍在队列中
    或正在运行。返回三个值：是否等待、状态字符串、进度信息。

    Args:
        payload: 模拟任务的响应 JSON 字典。

    Returns:
        Tuple[bool, str, Any]: 返回一个元组，包含三个元素：
            - is_pending (bool): 任务是否仍在等待（PENDING/RUNNING/QUEUED）
            - status (str): 状态字符串，已转换为大写
            - progress (Any): 进度信息，可能为数值或字符串

    Example:
        >>> payload = {"status": "PENDING", "progress": 0}
        >>> is_pending, status, progress = simulation_payload_is_pending(payload)
        >>> print(is_pending)
        True
        >>> print(status)
        PENDING

        >>> payload = {"status": "COMPLETED", "progress": 100}
        >>> is_pending, status, progress = simulation_payload_is_pending(payload)
        >>> print(is_pending)
        False

    Note:
        - API 可能使用 status 或 state 字段表示状态
        - 可能使用 progress 或 stage 字段表示进度
        - 状态字符串会被转换为大写进行比较
    """
    status = str(
        first_non_empty(payload.get("status"), payload.get("state"), "")
    ).upper()
    progress = first_non_empty(payload.get("progress"), payload.get("stage"), "")
    return status in {"PENDING", "RUNNING", "QUEUED"}, status, progress


def extract_total(payload: dict[str, Any]) -> int | None:
    """
    在接口提供时提取总数元数据。

    从响应负载中提取记录总数，用于分页控制。
    会尝试多个可能的总数字段名称。

    Args:
        payload: API 响应的 JSON 字典。

    Returns:
        Optional[int]: 记录总数，如果未找到则返回 None。

    Example:
        >>> payload = {"results": [...], "total": 100}
        >>> extract_total(payload)
        100

        >>> payload = {"results": [...], "count": 50}
        >>> extract_total(payload)
        50

        >>> payload = {"results": [...]}
        >>> extract_total(payload)
        None

    Note:
        - API 可能使用不同的键名表示总数
        - 尝试的键名：count, total, total_count
        - 即使 API 更改总数键名，仍保留分页支持
    """
    # 即使 API 更改总数键名，仍保留分页支持
    for key in ("count", "total", "total_count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return None


def normalize_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    从响应负载中规范化提取结果列表。

    从 API 响应中提取结果列表，处理可能的不同响应格式。
    如果响应是列表，直接返回；如果是字典，尝试提取 results 字段。

    Args:
        payload: API 响应的 JSON 字典。

    Returns:
        List[Dict[str, Any]]: 结果列表，如果未找到则返回空列表。

    Example:
        >>> payload = {"results": [{"id": 1}, {"id": 2}]}
        >>> normalize_results(payload)
        [{'id': 1}, {'id': 2}]

        >>> payload = [{"id": 1}, {"id": 2}]
        >>> normalize_results(payload)
        [{'id': 1}, {'id': 2}]

    Note:
        - 处理 API 响应格式的变化
        - 如果 payload 本身是列表，直接返回
        - 如果 payload 是字典，依次尝试 results / items / data / records 键
    """
    # 如果 payload 本身是列表，直接返回
    if isinstance(payload, list):
        return payload
    # 不同列表端点使用不同的容器键
    for key in ("results", "items", "data", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


# ============================================================================
# 辅助函数 - 重试与登录
# ============================================================================

_T = TypeVar("_T")


def retry_operation(
    name: str,
    retries: int,
    func: Callable[[], _T],
    *,
    retry_wait_seconds: float = RETRY_OPERATION_DEFAULT_WAIT,
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
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            return func()
        except BrainRateLimitError as exc:
            last_error = exc
            logger.warning(
                "[retry] %s rate limited on attempt %d/%d: %s", name, attempt, retries, exc,
            )
            # 当内层 API 调用已耗尽自身的速率限制重试时，
            # 立即跳过当前模板而不是重新运行整个阶段
            break
        except BrainQueueBusyError as exc:
            last_error = exc
            logger.warning(
                "[retry] %s queue busy on attempt %d/%d: %s", name, attempt, retries, exc,
            )
            # 队列拥塞也应立即跳过当前模板，
            # 让主循环可以降低运行时并发并冷却
            break
        except BrainAPIError as exc:
            # poll_simulation 内部已耗尽轮询/等待预算，
            # 不应再次重试整个阶段（否则有效超时成倍增长）
            last_error = exc
            logger.warning(
                "[retry] %s exhausted on attempt %d/%d: %s", name, attempt, retries, exc,
            )
            break
        except Exception as exc:
            last_error = exc
            logger.warning(
                "[retry] %s failed on attempt %d/%d: %s", name, attempt, retries, exc,
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
        retry_operation("login", attempts, client.login, retry_wait_seconds=LOGIN_RETRY_WAIT)
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

class BrainClient:
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
        min_request_interval (float): 最小请求间隔（秒）。
        rate_limit_max_retries (int): 速率限制时的最大重试次数。
        last_request_started_at (float): 上次请求开始时间（单调时钟）。
        cookies (CookieJar): HTTP Cookie 存储容器。
        opener: urllib 的 opener 对象，用于发送请求。

    Example:
        >>> client = BrainClient(
        ...     "user@example.com",
        ...     "password",
        ...     min_request_interval=0.5
        ... )
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
            ...     rate_limit_max_retries=3
            ... )

        Note:
            - min_request_interval 使用单调时钟计算，不受系统时间调整影响
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
        self.last_request_started_at = 0.0
        self.cookies = CookieJar()
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(self.cookies))

    def login(self) -> None:
        """
        使用 basic auth 登录并初始化会话 cookie。

        将邮箱和密码编码为 HTTP Basic Auth 格式，
        发送认证请求，并初始化会话 Cookie。

        Raises:
            BrainAPIError: 当登录失败时抛出，包含状态码和错误详情。

        Example:
            >>> client = BrainClient("user@example.com", "password")
            >>> client.login()
            [auth] login success

        Note:
            - 使用 HTTP Basic Auth 方式认证
            - 认证成功后，会话 Cookie 会自动存储
            - 登录失败会抛出异常，包含详细错误信息
        """
        token = base64.b64encode(
            f"{self.email}:{self.password}".encode()
        ).decode("ascii")
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
        expected: Iterable[int] | None = None,
        headers: dict[str, str] | None = None,
        retries: int | None = None,
        **kwargs: Any,
    ) -> tuple[int, dict[str, str], bytes]:
        """
        发送带共享头、退避与重试策略的 HTTP 请求。

        发送 HTTP 请求，自动处理：
        - 请求头合并（默认头 + 自定义头）
        - 速率限制重试（429 响应）
        - 服务器错误重试（500/502/503/504）
        - 错误响应处理

        Args:
            method: HTTP 方法（GET, POST, PUT, DELETE 等）。
            url: 请求 URL。
            expected: 预期的状态码列表。如果响应状态码在此列表中，
                认为请求成功。如果为 None，接受所有非错误状态码。
            headers: 自定义请求头，会与 DEFAULT_HEADERS 合并。
            retries: 重试次数。如果为 None，使用 rate_limit_max_retries。
            **kwargs: 其他传递给 raw_request 的参数（如 params, data）。

        Returns:
            Tuple[int, Dict[str, str], bytes]: 返回一个元组，包含三个元素：
                - status (int): HTTP 状态码
                - response_headers (Dict[str, str]): 响应头字典
                - content (bytes): 响应内容字节

        Raises:
            BrainAPIError: 当请求最终失败时抛出。
            BrainRateLimitError: 当速率限制重试耗尽时抛出。

        Example:
            >>> status, headers, content = client.request(
            ...     "GET",
            ...     "https://api.example.com/data",
            ...     expected={200},
            ...     headers={"X-Custom": "value"}
            ... )
            >>> print(status)
            200

        Note:
            - 集中化的 HTTP 封装层：
              - 合并请求头
              - 遵守 API 速率限制 Retry-After
              - 重试临时服务器错误
              - 将重复的 429 升级为专门的速率限制异常
            - 速率限制时使用双倍的 Retry-After 时间
            - 服务器错误时使用指数退避（最大 30 秒）
        """
        # 集中化的 HTTP 封装层：
        # - 合并请求头
        # - 遵守 API 速率限制 Retry-After
        # - 重试临时服务器错误
        # - 将重复的 429 升级为专门的速率限制异常
        merged_headers = dict(DEFAULT_HEADERS)
        if headers:
            merged_headers.update(headers)
        retries = (
            self.rate_limit_max_retries
            if retries is None
            else max(retries, 1)
        )

        last_response: tuple[int, dict[str, str], bytes] | None = None
        for attempt in range(1, retries + 1):
            status, response_headers, content = self.raw_request(
                method, url, headers=merged_headers, **kwargs
            )
            last_response = (status, response_headers, content)
            if status == 429:
                logger.warning(
                    "[rate-limit] %s %s attempt=%d/%d retry_after=%s",
                    method, url, attempt, retries, response_headers.get('Retry-After'),
                )
                wait_seconds(
                    doubled_retry_after(response_headers, default=RATE_LIMIT_DEFAULT_WAIT),
                    "rate limit",
                )
                continue
            if status == 401 and attempt < retries:
                logger.warning(
                    "[auth] session expired on %s %s, re-logging in...",
                    method, url,
                )
                self.login()
                continue
            if status in (500, 502, 503, 504):
                wait_seconds(
                    min(SERVER_ERROR_BACKOFF_MAX, attempt * SERVER_ERROR_BACKOFF_STEP),
                    f"server error {status}"
                )
                continue
            if expected is None or status in expected:
                return status, response_headers, content
            break

        if last_response is None:
            raise BrainAPIError(f"No response from {method} {url}")
        status, response_headers, content = last_response
        if status == 429:
            retry_after = doubled_retry_after(response_headers, default=RATE_LIMIT_DEFAULT_WAIT)
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
        params: dict[str, Any] | None = None,
        data: Any | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """
        执行一次不带高层重试策略的原始 HTTP 请求。

        发送单个 HTTP 请求，不处理重试、速率限制等高层逻辑。
        仅负责请求节流、参数编码、请求构建和响应解析。

        Args:
            method: HTTP 方法（GET, POST, PUT, DELETE 等）。
            url: 请求 URL。
            headers: 请求头字典。如果为 None，使用空字典。
            params: URL 查询参数字典。会自动编码并附加到 URL。
            data: 请求体数据。可以是 bytes 或其他类型。
                非 bytes 数据会被编码为 UTF-8 字节串。

        Returns:
            Tuple[int, Dict[str, str], bytes]: 返回一个元组，包含三个元素：
                - status (int): HTTP 状态码
                - response_headers (Dict[str, str]): 响应头字典
                - content (bytes): 响应内容字节

        Raises:
            BrainAPIError: 当发生 URL 错误（网络错误）时抛出。

        Example:
            >>> status, headers, content = client.raw_request(
            ...     "GET",
            ...     "https://api.example.com/data",
            ...     params={"limit": 10, "offset": 0}
            ... )
            >>> print(status)
            200

        Note:
            - 保持 raw_request 简单，高层重试逻辑在 request() 中
            - 自动遵守 min_request_interval 全局节流
            - HTTP 错误（如 404、500）不抛出异常，而是返回状态码
            - 只有网络错误（URLError）才抛出异常
            - 请求超时设置为 90 秒
        """
        # 保持 raw_request 简单，高层重试逻辑在 request() 中
        if self.min_request_interval > 0:
            now = time.monotonic()
            elapsed = now - self.last_request_started_at
            remaining = self.min_request_interval - elapsed
            if remaining > 0:
                wait_seconds(remaining, "global request throttle")
            self.last_request_started_at = time.monotonic()
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

        request = Request(
            url=url,
            data=request_data,
            headers=headers or {},
            method=method,
        )
        try:
            with self.opener.open(request, timeout=HTTP_REQUEST_TIMEOUT) as response:
                return (
                    response.getcode(),
                    dict(response.headers.items()),
                    response.read(),
                )
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()
        except URLError as exc:
            raise BrainAPIError(f"{method} {url} failed: {exc}") from exc

    def fetch_dataset_fields(
        self,
        dataset_id: str,
        *,
        limit: int,
        offset: int,
        page_size: int,
        region: str,
        universe: str,
        instrument_type: str,
        delay: int,
    ) -> list[dict[str, Any]]:
        """
        按分页拉取某个数据集的字段元数据。

        分页查询指定数据集的字段列表，支持分页控制、
        地区过滤、宇宙过滤、工具类型过滤和延迟过滤。

        Args:
            dataset_id: 数据集 ID（如 "fundamental6"）。
            limit: 要获取的最大字段数。如果为 0，获取所有字段。
            offset: 查询起始偏移量。
            page_size: 每页大小。
            region: 地区过滤（如 "USA"）。
            universe: 宇宙过滤（如 "TOP3000"）。
            instrument_type: 工具类型过滤（如 "EQUITY"）。
            delay: 延迟过滤（如 1）。

        Returns:
            List[Dict[str, Any]]: 字段元数据列表，每个字段为一个字典。

        Example:
            >>> fields = client.fetch_dataset_fields(
            ...     "fundamental6",
            ...     limit=100,
            ...     offset=0,
            ...     page_size=50,
            ...     region="USA",
            ...     universe="TOP3000",
            ...     instrument_type="EQUITY",
            ...     delay=1
            ... )
            >>> print(len(fields))
            100

        Note:
            - 按页拉取，支持处理大数据集
            - 当达到 limit 或数据耗尽时停止
            - 使用 extract_total 提取总数，优化分页控制
        """
        fields: list[dict[str, Any]] = []
        current_offset = offset

        while True:
            batch_size = page_size
            if limit > 0:
                remaining = limit - len(fields)
                if remaining <= 0:
                    break
                batch_size = min(batch_size, remaining)

            # 一次拉取一页，以便大数据集可以分批处理
            payload = self._fetch_dataset_fields_page(
                dataset_id,
                batch_size,
                current_offset,
                region=region,
                universe=universe,
                instrument_type=instrument_type,
                delay=delay,
            )

            batch = normalize_results(payload)
            if not batch:
                break

            fields.extend(batch)
            current_offset += len(batch)

            total = extract_total(payload)
            if len(batch) < batch_size:
                break
            if total is not None and current_offset >= total:
                break

        return fields

    def _fetch_dataset_fields_page(
        self,
        dataset_id: str,
        limit: int,
        offset: int,
        *,
        region: str,
        universe: str,
        instrument_type: str,
        delay: int,
    ) -> dict[str, Any]:
        """
        获取一页字段元数据，并尝试几种已知可行的查询参数形态。

        尝试多种查询参数组合，以适应 API 的不同接受模式。
        如果一种组合被接受，返回响应；如果所有组合都被拒绝，抛出异常。

        Args:
            dataset_id: 数据集 ID。
            limit: 本页要获取的字段数。
            offset: 查询偏移量。
            region: 地区过滤。
            universe: 宇宙过滤。
            instrument_type: 工具类型过滤。
            delay: 延迟过滤。

        Returns:
            Dict[str, Any]: API 响应 JSON 字典。

        Raises:
            BrainAPIError: 当所有查询参数组合都被拒绝时抛出。

        Example:
            >>> payload = client._fetch_dataset_fields_page(
            ...     "fundamental6",
            ...     limit=50,
            ...     offset=0,
            ...     region="USA",
            ...     universe="TOP3000",
            ...     instrument_type="EQUITY",
            ...     delay=1
            ... )
            >>> print(payload["results"])
            [...]

        Note:
            - 这些查询形态来自当前的前端打包代码：
              - dataset.id 在请求查询中保留
              - type=all 被省略
              - 常见过滤器可能包含 region/delay/universe/instrumentType
            - API 已观察到会拒绝某些形态（HTTP 400）
            - 我们尝试一小组合理的变体，然后才失败
        """
        last_error: Exception | None = None

        # 这些查询形态来自当前的前端打包代码：
        # - dataset.id 在请求查询中保留
        # - type=all 被省略
        # - 常见过滤器可能包含 region/delay/universe/instrumentType
        # API 已观察到会拒绝某些形态（HTTP 400），
        # 所以我们尝试一小组合理的变体，然后才失败
        candidate_params = [
            {
                "dataset.id": dataset_id,
                "region": region,
                "delay": str(delay),
                "universe": universe,
                "instrumentType": instrument_type,
                "limit": limit,
                "offset": offset,
            },
            {
                "dataset.id": dataset_id,
                "region": region,
                "delay": str(delay),
                "universe": universe,
                "limit": limit,
                "offset": offset,
            },
            {
                "dataset.id": dataset_id,
                "region": region,
                "instrumentType": instrument_type,
                "limit": limit,
                "offset": offset,
            },
            {
                "dataset.id": dataset_id,
                "region": region,
                "delay": str(delay),
                "instrumentType": instrument_type,
                "limit": limit,
                "offset": offset,
            },
            {
                "dataset.id": dataset_id,
                "limit": limit,
                "offset": offset,
            },
        ]

        for params in candidate_params:
            try:
                _, _, content = self.request(
                    "GET",
                    DATA_FIELDS_URL,
                    params=params,
                    headers=VERSION_HEADER,
                    expected={200},
                )
                logger.info("[data] data-fields query accepted: %s", params)
                return safe_json_bytes(content)
            except BrainAPIError as exc:
                last_error = exc
                logger.warning(
                    "[data] data-fields query rejected: %s -> %s", params, exc,
                )

        raise BrainAPIError(
            f"Unable to fetch dataset fields for {dataset_id}: {last_error}"
        )

    def create_simulation(self, payload: dict[str, Any]) -> str:
        """
        创建模拟任务并返回后续轮询使用的 Location 地址。

        发送模拟创建请求，返回 Location 头中包含的模拟任务 URL，
        用于后续轮询查询模拟状态。

        Args:
            payload: 模拟请求 JSON 字典，包含 Alpha 表达式和设置。

        Returns:
            str: 模拟任务的 Location URL。

        Raises:
            BrainAPIError: 当创建成功但 Location 头缺失时抛出。

        Example:
            >>> payload = {
            ...     "code": "rank(close)",
            ...     "settings": {"region": "USA", "delay": 1}
            ... }
            >>> location = client.create_simulation(payload)
            >>> print(location)
            https://api.worldquantbrain.com/simulations/abc123

        Note:
            - WorldQuant 通过 Location 头返回新创建的模拟
            - Location URL 用于后续轮询查询模拟状态
            - 使用 SIM_ACCEPT_HEADER 作为请求头
        """
        # WorldQuant 通过 Location 头返回新创建的模拟
        _, response_headers, _ = self.request(
            "POST",
            SIMULATIONS_URL,
            data=json.dumps(payload),
            headers=SIM_ACCEPT_HEADER,
            expected={201},
        )
        location = response_headers.get("Location")
        if not location:
            raise BrainAPIError("Simulation created but Location header is missing.")
        return location

    @staticmethod
    def _check_pending_limits(
        pending_cycles: int,
        max_pending_cycles: int,
        max_queue_seconds: float,
        pending_started_at: float | None,
        url: str,
    ) -> None:
        """检查 pending 状态是否超出排队/时间预算。"""
        if pending_cycles > max_pending_cycles:
            raise BrainQueueBusyError(
                f"Simulation stayed queued too long "
                f"({pending_cycles} pending cycles) for {url}; "
                f"skip current template."
            )
        if (
            max_queue_seconds > 0
            and pending_started_at is not None
            and time.monotonic() - pending_started_at > max_queue_seconds
        ):
            raise BrainQueueBusyError(
                f"Simulation exceeded queue budget "
                f"({max_queue_seconds:.0f}s) for {url}; skip current template."
            )

    def poll_simulation(
        self,
        location: str,
        *,
        max_polls: int,
        max_wait_seconds: float,
        max_pending_cycles: int,
        max_queue_seconds: float,
    ) -> dict[str, Any]:
        """
        轮询单个模拟任务，直到完成或超出排队/等待预算。

        持续轮询模拟任务状态，直到：
        - 模拟完成（返回结果）
        - 超出最大轮询次数
        - 超出最大等待时间
        - 队列等待时间超出预算

        Args:
            location: 模拟任务的 URL 或相对路径。
            max_polls: 最大轮询次数。
            max_wait_seconds: 最大总等待时间（秒）。
            max_pending_cycles: 最大队列等待周期数。
            max_queue_seconds: 最大队列等待时间（秒）。

        Returns:
            Dict[str, Any]: 模拟完成的响应 JSON 字典。

        Raises:
            BrainAPIError: 当超出轮询或等待限制时抛出。
            BrainQueueBusyError: 当队列等待超出限制时抛出。

        Example:
            >>> result = client.poll_simulation(
            ...     location,
            ...     max_polls=100,
            ...     max_wait_seconds=600,
            ...     max_pending_cycles=10,
            ...     max_queue_seconds=60
            ... )
            >>> print(result["status"])
            COMPLETED

        Note:
            - URL 会自动补全为完整 URL（如果传入相对路径）
            - 首先解析响应体：一些成功响应可能仍带有 Retry-After
            - 响应体是完成状态的真相来源
            - 队列状态（PENDING/QUEUED）会跟踪等待时间和周期数
        """
        url = (
            location
            if location.startswith("http")
            else f"{API_BASE}{location}"
        )
        poll_count = 0
        pending_cycles = 0
        started_at = time.monotonic()
        pending_started_at: float | None = None
        while True:
            poll_count += 1
            if poll_count > max_polls:
                raise BrainAPIError(
                    f"Simulation polling exceeded max polls ({max_polls}) "
                    f"for {url}; skip current template."
                )
            if time.monotonic() - started_at > max_wait_seconds:
                raise BrainAPIError(
                    f"Simulation polling exceeded max wait "
                    f"({max_wait_seconds:.1f}s) for {url}; skip current template."
                )
            # 首先解析响应体：一些成功响应可能仍带有 Retry-After，
            # 响应体是完成状态的真相来源
            _, response_headers, content = self.request(
                "GET",
                url,
                headers=SIM_ACCEPT_HEADER,
                expected={200, 202},
            )
            payload = safe_json_bytes(content)
            is_pending, status, progress = simulation_payload_is_pending(payload)
            if is_pending:
                if pending_started_at is None:
                    pending_started_at = time.monotonic()
                pending_cycles += 1
                self._check_pending_limits(
                    pending_cycles, max_pending_cycles,
                    max_queue_seconds, pending_started_at, url,
                )
                logger.info(
                    "[simulation] pending location=%s status=%s progress=%s retry_after=%s",
                    url, status, progress, response_headers.get('Retry-After'),
                )
                if response_headers.get("Retry-After"):
                    wait_seconds(
                        polling_retry_after(response_headers, default=POLLING_DEFAULT_WAIT),
                        "simulation pending",
                        verbose=False,  # 常规轮询等待不打印 INFO 日志
                    )
                else:
                    wait_seconds(POLLING_NO_RETRY_AFTER_WAIT, f"simulation {status.lower()}", verbose=False)
                continue

            # 一些 API 响应仅暴露 Retry-After 而省略明确的等待状态。
            # 仅在确认响应体尚未包含完成的模拟负载后，
            # 才将这些视为等待状态。
            if response_headers.get("Retry-After"):
                body_status = str(
                    first_non_empty(
                        payload.get("status"), payload.get("state"), ""
                    )
                ).upper()
                # 如果 response body 已经是终态，直接返回，
                # 不被 Retry-After 头误导继续等待
                if body_status in {"COMPLETED", "FAILED", "ERROR", "CANCELLED"}:
                    logger.info(
                        "[simulation] terminal state detected body_status=%s ignoring Retry-After header",
                        body_status,
                    )
                    return payload
                # body_status 为空或 NONE 说明服务器尚未准备好，
                # 这等价于 PENDING，打印一次 body 帮助排查
                if body_status in {"", "NONE"} and pending_cycles == 0:
                    logger.info(
                        "[simulation] status is null/empty, body_keys=%s body_preview=%.200s",
                        sorted(payload.keys()), str(payload),
                    )
                if pending_started_at is None:
                    pending_started_at = time.monotonic()
                pending_cycles += 1
                self._check_pending_limits(
                    pending_cycles, max_pending_cycles,
                    max_queue_seconds, pending_started_at, url,
                )
                logger.info(
                    "[simulation] pending location=%s body_status=%s retry_after=%s",
                    url, body_status or 'unknown', response_headers.get('Retry-After'),
                )
                wait_seconds(
                    polling_retry_after(response_headers, default=POLLING_DEFAULT_WAIT),
                    "simulation pending",
                    verbose=False,  # 常规轮询等待不打印 INFO 日志
                )
                continue
            return payload

    def get_alpha_detail(self, alpha_id: str) -> dict[str, Any]:
        """
        获取 Alpha 详情，包括可用时的 check-submit 结果。

        查询指定 Alpha 的详细信息，包括模拟结果、
        check-submit 结果（如果可用）等。

        Args:
            alpha_id: Alpha 的唯一标识符。

        Returns:
            Dict[str, Any]: Alpha 详情 JSON 字典。

        Example:
            >>> detail = client.get_alpha_detail("abc123")
            >>> print(detail["status"])
            SUBMITTABLE

        Note:
            - 使用 SIM_ACCEPT_HEADER 作为请求头
            - 返回完整的 Alpha 详情，包括可提交状态
        """
        _, _, content = self.request(
            "GET",
            f"{ALPHAS_URL}/{alpha_id}",
            headers=SIM_ACCEPT_HEADER,
            expected={200},
        )
        return safe_json_bytes(content)

    def submit_alpha(self, alpha_id: str) -> dict[str, Any]:
        """
        提交可提交的 Alpha，并在需要时跟随异步 Retry-After 轮询。

        提交指定的 Alpha，如果 API 返回 Retry-After，
        会自动切换为 GET 请求继续轮询，直到提交完成。

        Args:
            alpha_id: Alpha 的唯一标识符。

        Returns:
            Dict[str, Any]: 提交结果 JSON 字典。

        Example:
            >>> result = client.submit_alpha("abc123")
            >>> print(result["status"])
            SUBMITTED

        Note:
            - 提交开始为 POST，可能继续为轮询 GET 请求
            - 如果平台返回 Retry-After，会继续轮询
            - 使用 SIM_ACCEPT_HEADER 作为请求头
        """
        url = f"{ALPHAS_URL}/{alpha_id}/submit"
        method = "POST"

        while True:
            # 提交开始为 POST，可能继续为轮询 GET 请求
            # 如果平台返回 Retry-After
            _, response_headers, content = self.request(
                method,
                url,
                headers=SIM_ACCEPT_HEADER,
                expected={200, 202},
            )
            retry_after = response_headers.get("Retry-After")
            if retry_after:
                logger.info(
                    "[submit] pending alpha_id=%s method=%s retry_after=%s",
                    alpha_id, method, retry_after,
                )
                wait_seconds(
                    polling_retry_after(response_headers, default=POLLING_DEFAULT_WAIT),
                    "submission pending",
                )
                method = "GET"
                continue
            return safe_json_bytes(content)


# ============================================================================
# WorkerClientFactory 类
# ============================================================================

class WorkerClientFactory:
    """
    为每个工作线程提供独立且已认证的 BrainClient。

    urllib opener/cookie 状态跨线程共享不够安全，
    所以每个工作线程懒加载创建并登录自己的客户端，恰好一次。

    Attributes:
        args (argparse.Namespace): 命令行参数命名空间。
        email (str): 用户邮箱地址。
        password (str): 用户密码。
        _local (threading.local): 线程本地存储。

    Example:
        >>> import argparse
        >>> args = argparse.Namespace(
        ...     min_request_interval=0.5,
        ...     rate_limit_max_retries=3,
        ...     login_retries=2
        ... )
        >>> factory = WorkerClientFactory(args, "user@example.com", "password")
        >>> # 在工作线程中
        >>> client = factory.get_client()
        >>> # client 已登录且独立于其他线程的客户端

    Note:
        - 每个线程首次调用 get_client 时会创建并登录客户端
        - 同一线程后续调用返回相同的客户端实例
        - 使用 threading.local 实现线程隔离
        - 客户端创建时会使用 args 中的配置参数
    """

    def __init__(
        self,
        args: argparse.Namespace,
        email: str,
        password: str
    ) -> None:
        """
        记录线程级客户端创建所需的参数与凭证。

        存储 args 和凭证，供后续线程本地客户端创建使用。

        Args:
            args: 命令行参数命名空间，必须包含：
                - min_request_interval: 最小请求间隔
                - rate_limit_max_retries: 速率限制重试次数
                - login_retries: 登录重试次数
            email: WorldQuant Brain 账号的邮箱地址。
            password: WorldQuant Brain 账号的密码。

        Example:
            >>> import argparse
            >>> args = argparse.Namespace(
            ...     min_request_interval=0.5,
            ...     rate_limit_max_retries=3,
            ...     login_retries=2
            ... )
            >>> factory = WorkerClientFactory(args, "user@example.com", "password")
        """
        self.args = args
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
        client = getattr(self._local, "client", None)
        if client is not None:
            return client

        client = BrainClient(
            self.email,
            self.password,
            min_request_interval=self.args.min_request_interval,
            rate_limit_max_retries=self.args.rate_limit_max_retries,
        )
        login_with_retry(client, self.args.login_retries)
        self._local.client = client
        return client
