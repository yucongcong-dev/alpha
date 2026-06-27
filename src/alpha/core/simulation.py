"""
模拟生命周期管理模块

本模块负责单个 Alpha 模拟任务的完整生命周期管理，
包括 simulation (创建+轮询)、checksubmit (检查验证) 和 submit (提交) 三个顶层阶段。

模块内容：
    - Alpha ID 提取与解析函数
    - 检查项提取与分析函数
    - 模拟指标预检函数
    - 失败摘要函数
    - simulation / checksubmit / submit 阶段函数
    - 结果构建函数
    - 字段测试核心执行函数
"""

# pyright: reportExplicitAny=false, reportAny=false

import argparse
import json
import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, cast

from ..api.client import (
    BrainClient,
    WorkerClientFactory,
    retry_operation,
)
from ..utils.helpers import first_non_empty
from ..config import (
    API_KEY_DETAIL,
    API_KEY_ERROR,
    API_KEY_FAILED,
    API_KEY_MESSAGE,
    API_KEY_PROGRESS,
    API_KEY_STATE,
    API_KEY_STATUS,
    CHECK_CONCENTRATED_WEIGHT,
    CHECK_HIGH_TURNOVER,
    CHECK_LOW_FITNESS,
    CHECK_LOW_SHARPE,
    CHECK_LOW_TURNOVER,
    FAILURE_SUMMARY_MAX_LEN,
    MAX_FAILED_CHECK_NAMES,
    PRECHECK_FALLBACK_MAX_TURNOVER,
    PRECHECK_FALLBACK_MAX_WEIGHT,
    PRECHECK_FALLBACK_MIN_FITNESS,
    PRECHECK_FALLBACK_MIN_SHARPE,
    PRECHECK_FALLBACK_MIN_TURNOVER,
    SENTINEL_UNKNOWN,
    SENTINEL_UNKNOWN_CHECK,
    SIMULATION_RETRY_WAIT,
    STATUS_ERROR,
    STATUS_SIMULATED,
    STATUS_SUBMITTED,
    SUBMIT_MAX_TURNOVER,
    SUBMIT_MAX_WEIGHT,
    SUBMIT_MIN_FITNESS,
    SUBMIT_MIN_SHARPE,
    SUBMIT_MIN_TURNOVER,
)
from ..generators.settings import build_simulation_payload
from ..models.base import (
    FieldTestContext,
    FieldTestResult,
    SettingsVariant,
)
from ..utils.helpers import choose_field_type

logger = logging.getLogger(__name__)


@dataclass
class PrecheckConfig:
    """本地预检配置（不可变）"""
    min_sharpe: float = PRECHECK_FALLBACK_MIN_SHARPE
    min_fitness: float = PRECHECK_FALLBACK_MIN_FITNESS
    min_turnover: float = PRECHECK_FALLBACK_MIN_TURNOVER
    max_turnover: float = PRECHECK_FALLBACK_MAX_TURNOVER
    max_weight: float = PRECHECK_FALLBACK_MAX_WEIGHT
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "PrecheckConfig":
        """从命令行参数构建配置"""
        return cls(
            min_sharpe=getattr(args, "min_sharpe", cls.min_sharpe),
            min_fitness=getattr(args, "min_fitness", cls.min_fitness),
            min_turnover=getattr(args, "min_turnover", cls.min_turnover),
            max_turnover=getattr(args, "max_turnover", cls.max_turnover),
            max_weight=getattr(args, "max_weight", cls.max_weight),
        )

# ============================================================================
# 模块级常量（API 响应 JSON 键名）
# ============================================================================

_ALPHA_ID_REGEX: re.Pattern = re.compile(r"/alphas/([^/]+)", re.IGNORECASE)
"""从 location URL 提取 alpha ID 的正则模式（预编译）"""

_SIM_ID_REGEX: re.Pattern = re.compile(r"/simulations/([^/]+)", re.IGNORECASE)
"""从 location URL 提取 simulation ID 的正则模式（预编译）"""

_RESULT_FAIL: str = "FAIL"
"""check 结果字符串常量"""

_RESULT_PASS: str = "PASS"
"""check 结果字符串常量"""

_KEY_ALPHA: str = "alpha"
_KEY_ALPHA_ID: str = "alphaId"
_KEY_CHECKS: str = "checks"
_KEY_CHILDREN: str = "children"
_KEY_CONCENTRATED_WEIGHT: str = "concentratedWeight"
_KEY_ID: str = "id"
_KEY_IS: str = "is"
_KEY_LIMIT: str = "limit"
_KEY_LOCATION: str = "location"
_KEY_MAX_WEIGHT: str = "maxWeight"
_KEY_MAX_WEIGHT_ALT: str = "max_weight"
_KEY_NAME: str = "name"
_KEY_RESULT: str = "result"
_KEY_SHARPE: str = "sharpe"
_KEY_FITNESS: str = "fitness"
_KEY_THRESHOLD: str = "threshold"
_KEY_TURNOVER: str = "turnover"
_KEY_TYPE: str = "type"
_KEY_VALUE: str = "value"
_TYPE_ALPHA: str = "ALPHA"

# ============================================================================
# Alpha ID 提取与解析函数
# ============================================================================

def extract_alpha_id(payload: dict[str, Any]) -> str | None:
    """
    从结构不稳定的模拟返回中提取 Alpha ID。

    由于 API 响应格式在不同端点上不一致，此函数会检查多种可能的结构形态，
    以可靠地提取 Alpha ID。

    Args:
        payload: 模拟任务的响应 JSON 字典。

    Returns:
        str | None: Alpha ID 字符串，如果未找到则返回 None。

    Example:
        >>> payload = {"alpha": "alpha_123"}
        >>> extract_alpha_id(payload)
        'alpha_123'

        >>> payload = {"alpha": {"id": "alpha_456"}}
        >>> extract_alpha_id(payload)
        'alpha_456'

        >>> payload = {"location": "/alphas/alpha_789"}
        >>> extract_alpha_id(payload)
        'alpha_789'

    Note:
        - 检查的候选字段包括：alpha、alphaId、id（当 type 为 ALPHA 时）
        - 支持嵌套字典结构
        - 支持从 location URL 中提取 ID
        - 支持从 children 列表中递归提取
    """
    candidates = [
        payload.get(_KEY_ALPHA),
        payload.get(_KEY_ALPHA_ID),
        payload.get(_KEY_ID) if payload.get(_KEY_TYPE) == _TYPE_ALPHA else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
        if isinstance(candidate, dict):
            cd = cast(dict[str, Any], candidate)
            candidate_id = first_non_empty(cd.get(_KEY_ID), cd.get(_KEY_ALPHA))
            if isinstance(candidate_id, str) and candidate_id:
                return candidate_id

    children = payload.get(_KEY_CHILDREN)
    if isinstance(children, list):
        for child in children:  # pyright: ignore[reportUnknownVariableType]
            if isinstance(child, dict):
                cd = cast(dict[str, Any], child)
                alpha_id = extract_alpha_id(cd)
            else:
                alpha_id = None
            if alpha_id:
                return alpha_id

    location = payload.get(_KEY_LOCATION)
    if isinstance(location, str):
        match = re.search(_ALPHA_ID_REGEX, location)
        if match:
            return match.group(1)
    return None


# ============================================================================
# 检查项提取与分析函数
# ============================================================================

def extract_checks(alpha_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    从嵌套或顶层 Alpha 结构中提取 check-submit 检查项。

    检查项可能位于 alpha.is.checks 或顶层 checks 字段中，
    此函数会检查这两种位置。

    Args:
        alpha_payload: Alpha 详情的 JSON 字典。

    Returns:
        list[dict[str, Any]]: 检查项列表，如果未找到则返回空列表。

    Example:
        >>> payload = {"is": {"checks": [{"name": "LOW_SHARPE", "result": "FAIL"}]}}
        >>> extract_checks(payload)
        [{'name': 'LOW_SHARPE', 'result': 'FAIL'}]

        >>> payload = {"checks": [{"name": "LOW_SHARPE", "result": "PASS"}]}
        >>> extract_checks(payload)
        [{'name': 'LOW_SHARPE', 'result': 'PASS'}]

    Note:
        - 检查项可能位于 alpha.is.checks 或顶层 checks
        - 返回空列表而不是 None，便于后续处理
    """
    is_section = alpha_payload.get(_KEY_IS)
    if isinstance(is_section, dict):
        section = cast(dict[str, Any], is_section)
        section_checks = section.get(_KEY_CHECKS)
        if isinstance(section_checks, list):
            return section_checks  # pyright: ignore[reportUnknownVariableType]
    checks = alpha_payload.get(_KEY_CHECKS)
    if isinstance(checks, list):
        return checks  # pyright: ignore[reportUnknownVariableType]
    return []


def extract_failed_checks(alpha_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    仅提取失败检查项，并转换为适合结果持久化的紧凑结构。

    从检查项列表中筛选出 result 为 FAIL 的检查项，
    并提取关键信息构建紧凑的结构。

    Args:
        alpha_payload: Alpha 详情的 JSON 字典。

    Returns:
        list[dict[str, Any]]: 失败检查项的紧凑列表，包含：
            - name: 检查项名称
            - result: 检查结果（FAIL）
            - value: 实际值
            - limit: 阈值限制

    Example:
        >>> payload = {"checks": [
        ...     {"name": "LOW_SHARPE", "result": "FAIL", "value": 0.8, "limit": 1.0},
        ...     {"name": "LOW_FITNESS", "result": "PASS", "value": 1.2, "limit": 1.0}
        ... ]}
        >>> extract_failed_checks(payload)
        [{'name': 'LOW_SHARPE', 'result': 'FAIL', 'value': 0.8, 'limit': 1.0}]

    Note:
        - 只返回失败的检查项
        - 使用 first_non_empty 选择 limit 或 threshold
    """
    failed_checks: list[dict[str, Any]] = []
    for check in extract_checks(alpha_payload):
        if str(check.get(_KEY_RESULT, "")).upper() != _RESULT_FAIL:
            continue
        failed_checks.append(
            {
                _KEY_NAME: check.get(_KEY_NAME),
                _KEY_RESULT: check.get(_KEY_RESULT),
                _KEY_VALUE: check.get(_KEY_VALUE),
                _KEY_LIMIT: first_non_empty(check.get(_KEY_LIMIT), check.get(_KEY_THRESHOLD)),
            }
        )
    return failed_checks


def is_submittable_from_checks(checks: list[dict[str, Any]]) -> bool | None:
    """
    将检查项列表折叠为 True、False 或 None 三态结果。

    根据检查项的结果判断 Alpha 是否可提交：
    - 如果所有检查项都通过，返回 True
    - 如果有任何检查项失败，返回 False
    - 如果检查项列表为空，返回 None

    Args:
        checks: 检查项列表。

    Returns:
        bool | None: 可提交状态，True 表示可提交，
            False 表示不可提交，None 表示检查信息不可用。

    Example:
        >>> checks = [{"name": "LOW_SHARPE", "result": "PASS"}]
        >>> is_submittable_from_checks(checks)
        True

        >>> checks = [{"name": "LOW_SHARPE", "result": "FAIL"}]
        >>> is_submittable_from_checks(checks)
        False

        >>> checks = []
        >>> is_submittable_from_checks(checks)
        None

    Note:
        - 空列表返回 None 表示检查信息不可用
        - 任何 FAIL 结果都会导致返回 False
    """
    if not checks:
        return None
    return all(str(check.get(_KEY_RESULT, "")).upper() != _RESULT_FAIL for check in checks)


# ============================================================================
# 模拟指标预检函数
# ============================================================================

def precheck_simulation_metrics(
    simulation_result: dict[str, Any],
    *,
    min_sharpe: float = SUBMIT_MIN_SHARPE,
    min_fitness: float = SUBMIT_MIN_FITNESS,
    min_turnover: float = SUBMIT_MIN_TURNOVER,
    max_turnover: float = SUBMIT_MAX_TURNOVER,
    max_weight: float = SUBMIT_MAX_WEIGHT,
) -> tuple[bool, str, list[dict[str, Any]]]:
    """
    在调用 checksubmit API 之前，用本地阈值预检模拟响应中的原始指标。

    模拟响应通常包含 is.sharpe、is.fitness、is.turnover 等原始指标。
    如果这些指标明显不达标，可以直接跳过 checksubmit API 调用，
    节省请求配额和网络开销。

    Args:
        simulation_result: 模拟完成的响应 JSON 字典。
        min_sharpe: 最低 Sharpe 阈值（默认 1.25）。
        min_fitness: 最低 Fitness 阈值（默认 1.0）。
        min_turnover: 最低 Turnover 阈值（默认 1%）。
        max_turnover: 最高 Turnover 阈值（默认 70%）。
        max_weight: 单股最大权重上限（默认 10%）。

    Returns:
        tuple: (passed: bool, reason: str, failed_checks: list)
            - passed=True 表示预检通过，可以继续 checksubmit
            - passed=False 表示预检不通过，reason 描述原因，
              failed_checks 是构造的失败检查项列表（用于结果持久化）

    Note:
        - 如果 is 段缺失或指标无法提取，返回 passed=True（回退到 checksubmit）
        - 阈值可被调用方覆盖以适应不同的 universe/region 设置
        - 构造的 failed_checks 结构与真实 checksubmit 返回一致
    """
    is_section = simulation_result.get(_KEY_IS)
    if not isinstance(is_section, dict):
        return True, "", []

    is_dict = cast(dict[str, Any], is_section)
    sharpe = is_dict.get(_KEY_SHARPE)
    fitness = is_dict.get(_KEY_FITNESS)
    turnover = is_dict.get(_KEY_TURNOVER)
    max_stock_weight = (
        is_dict.get(_KEY_MAX_WEIGHT)
        or is_dict.get(_KEY_MAX_WEIGHT_ALT)
        or is_dict.get(_KEY_CONCENTRATED_WEIGHT)
    )

    failures: list[dict[str, Any]] = []

    def _add_failure(check_name: str, v: int | float, limit: float) -> None:
        failures.append({
            _KEY_NAME: check_name,
            _KEY_RESULT: _RESULT_FAIL,
            _KEY_VALUE: float(v),
            _KEY_LIMIT: limit,
        })

    if isinstance(sharpe, (int, float)) and sharpe < min_sharpe:
        _add_failure(CHECK_LOW_SHARPE, sharpe, min_sharpe)
    if isinstance(fitness, (int, float)) and fitness < min_fitness:
        _add_failure(CHECK_LOW_FITNESS, fitness, min_fitness)
    if isinstance(turnover, (int, float)):
        if turnover < min_turnover:
            _add_failure(CHECK_LOW_TURNOVER, turnover, min_turnover)
        elif turnover > max_turnover:
            _add_failure(CHECK_HIGH_TURNOVER, turnover, max_turnover)
    if isinstance(max_stock_weight, (int, float)) and max_stock_weight > max_weight:
        _add_failure(CHECK_CONCENTRATED_WEIGHT, max_stock_weight, max_weight)

    if not failures:
        return True, "", []

    reason_parts = [
        f"{f[_KEY_NAME].lower()}: {f[_KEY_VALUE]:.4f} vs limit {f[_KEY_LIMIT]}"
        for f in failures
    ]
    return False, "; ".join(reason_parts), failures


# ============================================================================
# 失败摘要函数
# ============================================================================

def summarize_failure(payload: dict[str, Any]) -> str:
    """
    将冗长的 API 失败负载压缩为简短的运维可读消息。

    从响应负载中提取关键错误信息，生成简短的错误描述，
    便于日志记录和结果持久化。

    Args:
        payload: API 失败响应的 JSON 字典。

    Returns:
        str: 简短的错误描述消息。

    Example:
        >>> payload = {"detail": "Invalid expression syntax"}
        >>> summarize_failure(payload)
        'Invalid expression syntax'

        >>> payload = {"checks": [{"name": "LOW_SHARPE", "result": "FAIL"}]}
        >>> summarize_failure(payload)
        'failed checks: LOW_SHARPE'

        >>> payload = {"error": "Unknown error"}
        >>> summarize_failure(payload)
        'Unknown error'

    Note:
        - 优先提取 detail、message、error 字段
        - 其次提取失败的检查项名称
        - 最后截断原始 JSON 文本（最多 300 字符）
    """
    detail = first_non_empty(
        payload.get(API_KEY_DETAIL),
        payload.get(API_KEY_MESSAGE),
        payload.get(API_KEY_ERROR),
    )
    if detail:
        return str(detail)

    checks = extract_checks(payload)
    failed = [check for check in checks if str(check.get(_KEY_RESULT, "")).upper() == _RESULT_FAIL]
    if failed:
        names = ", ".join(
            str(check.get(_KEY_NAME, SENTINEL_UNKNOWN_CHECK)) for check in failed[:MAX_FAILED_CHECK_NAMES]
        )
        return f"failed checks: {names}"

    text = json.dumps(payload, ensure_ascii=False)[:FAILURE_SUMMARY_MAX_LEN]
    return text or "unknown error"


# ============================================================================
# simulation 阶段函数 (创建 + 轮询)
# ============================================================================

def create_simulation_with_retry(
    client: BrainClient,
    payload: dict[str, Any],
    retries: int
) -> tuple[str, str]:
    """
    创建模拟任务，并返回轮询地址与可读 simulation ID。

    使用重试机制创建模拟任务，返回 Location URL 和可读的模拟 ID。

    Args:
        client: BrainClient 实例，用于发送 API 请求。
        payload: 模拟请求体，包含 Alpha 表达式和设置。
        retries: 最大重试次数。

    Returns:
        tuple[str, str]: 返回一个元组，包含两个元素：
            - simulation_location: 模拟任务的 Location URL
            - simulation_id: 可读的模拟 ID（从 URL 中提取）

    Raises:
        BrainAPIError: 当所有重试都失败时抛出。

    Example:
        >>> location, sim_id = create_simulation_with_retry(client, payload, 3)
        >>> print(location)
        https://api.worldquantbrain.com/simulations/sim_123
        >>> print(sim_id)
        sim_123

    Note:
        - 模拟创建是最容易遇到临时 API 问题或速率限制的阶段之一
        - 存储可读的 simulation_id 用于结果，但保留完整 location 用于轮询
        - 重试间隔为 3 秒
    """
    simulation_location = retry_operation(
        "create simulation",
        retries,
        lambda: client.create_simulation(payload),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )
    simulation_id_match = re.search(_SIM_ID_REGEX, simulation_location)
    simulation_id = simulation_id_match.group(1) if simulation_id_match else simulation_location
    logger.info(
        "[simulation] created simulation_id=%s location=%s", simulation_id, simulation_location,
    )
    return simulation_location, simulation_id


def poll_simulation_with_retry(
    client: BrainClient,
    simulation_location: str,
    retries: int,
    *,
    max_polls: int,
    max_wait_seconds: float,
    max_pending_cycles: int,
    max_queue_seconds: float,
) -> dict[str, Any]:
    """
    按独立的重试预算与排队限制轮询模拟任务。

    使用独立的重试预算轮询模拟任务状态，直到完成或超出限制。

    Args:
        client: BrainClient 实例。
        simulation_location: 模拟任务的 URL。
        retries: 最大重试次数。
        max_polls: 最大轮询次数。
        max_wait_seconds: 最大总等待时间（秒）。
        max_pending_cycles: 最大队列等待周期数。
        max_queue_seconds: 最大队列等待时间（秒）。

    Returns:
        dict[str, Any]: 模拟完成的响应 JSON 字典。

    Raises:
        BrainAPIError: 当超出轮询或等待限制时抛出。
        BrainQueueBusyError: 当队列等待超出限制时抛出。

    Example:
        >>> result = poll_simulation_with_retry(
        ...     client, location, 3,
        ...     max_polls=100, max_wait_seconds=600,
        ...     max_pending_cycles=10, max_queue_seconds=60
        ... )
        >>> print(result["status"])
        COMPLETED

    Note:
        - 轮询重试策略与创建重试策略分离，因为长时间运行的任务在这里是正常的
        - 重试间隔为 3 秒
    """
    return retry_operation(
        "poll simulation",
        retries,
        lambda: client.poll_simulation(
            simulation_location,
            max_polls=max_polls,
            max_wait_seconds=max_wait_seconds,
            max_pending_cycles=max_pending_cycles,
            max_queue_seconds=max_queue_seconds,
        ),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )


# ============================================================================
# checksubmit & submit 阶段函数
# ============================================================================

def checksubmit_with_retry(
    client: BrainClient,
    alpha_id: str,
    retries: int,
) -> tuple[bool | None, str, list[dict[str, Any]]]:
    """
    获取 Alpha 检查结果并转成可提交状态输出。

    获取 Alpha 的检查结果，判断是否可提交，并提取失败的检查项。

    Args:
        client: BrainClient 实例。
        alpha_id: Alpha 的唯一标识符。
        retries: 最大重试次数。

    Returns:
        tuple[bool | None, str, list[dict[str, Any]]]: 返回一个元组，包含三个元素：
            - submittable: 可提交状态（True/False/None）
            - message: 结果消息
            - failed_checks: 失败检查项列表

    Raises:
        BrainAPIError: 当所有重试都失败时抛出。

    Example:
        >>> submittable, message, failed_checks = checksubmit_with_retry(client, "alpha_123", 3)
        >>> print(submittable)
        True
        >>> print(message)
        checks passed

    Note:
        - 读取 alpha checks 并转换为简单的可提交状态
        - 重试间隔为 3 秒
    """
    alpha_detail = retry_operation(
        "checksubmit",
        retries,
        lambda: client.get_alpha_detail(alpha_id),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )
    checks = extract_checks(alpha_detail)
    submittable = is_submittable_from_checks(checks)
    failed_checks = extract_failed_checks(alpha_detail)
    message = "checks unavailable" if submittable is None else "checks passed" if submittable else "checks failed"
    logger.info(
        "[checksubmit] alpha_id=%s submittable=%s message=%s", alpha_id, submittable, message,
    )
    return submittable, message, failed_checks


def submit_with_retry(client: BrainClient, alpha_id: str, retries: int) -> str:
    """
    带重试地提交 Alpha，并返回紧凑状态消息。

    使用重试机制提交 Alpha，并返回提交状态消息。

    Args:
        client: BrainClient 实例。
        alpha_id: Alpha 的唯一标识符。
        retries: 最大重试次数。

    Returns:
        str: 提交状态消息（"submitted" 或错误描述）。

    Raises:
        BrainAPIError: 当所有重试都失败时抛出。

    Example:
        >>> message = submit_with_retry(client, "alpha_123", 3)
        >>> print(message)
        submitted

    Note:
        - 提交是最终的副作用阶段，因此重试处理与只读检查分离
        - 重试间隔为 3 秒
    """
    submit_result = retry_operation(
        "submit",
        retries,
        lambda: client.submit_alpha(alpha_id),
        retry_wait_seconds=SIMULATION_RETRY_WAIT,
    )
    if submit_result.get(API_KEY_STATUS) == API_KEY_FAILED:
        return summarize_failure(submit_result)
    return STATUS_SUBMITTED


# ============================================================================
# 结果构建函数
# ============================================================================

def build_failure_result(
    *,
    field_id: str,
    field_type: str,
    field_name: str,
    template_name: str,
    simulation_id: str | None,
    alpha_id: str | None,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    failed_stage: str,
    message: str,
    status: str = STATUS_ERROR,
    failed_checks: list[dict[str, Any]] | None = None,
) -> FieldTestResult:
    """
    构建标准化失败结果对象，简化后续落盘与统计逻辑。

    创建一个标准化的失败结果对象，包含所有必要信息，
    简化结果持久化和统计分析。

    Args:
        field_id: 字段的唯一标识符。
        field_type: 字段类型。
        field_name: 字段名称。
        template_name: 模板名称。
        simulation_id: 模拟任务 ID（可能为 None）。
        alpha_id: Alpha ID（可能为 None）。
        expression: Alpha 表达式。
        settings_fingerprint: 设置配置指纹。
        template_library_fingerprint: 模板库指纹。
        failed_stage: 失败的阶段名称。
        message: 错误消息。
        status: 状态字符串。默认为 "error"。
        failed_checks: 失败检查项列表。默认为 None。

    Returns:
        FieldTestResult: 标准化的失败结果对象。

    Example:
        >>> result = build_failure_result(
        ...     field_id="sales",
        ...     field_type="MATRIX",
        ...     field_name="sales",
        ...     template_name="ts_mean_20",
        ...     simulation_id=None,
        ...     alpha_id=None,
        ...     expression="rank(ts_mean(sales, 20))",
        ...     settings_fingerprint="abc123",
        ...     template_library_fingerprint="def456",
        ...     failed_stage="simulation",
        ...     message="Network error"
        ... )
        >>> print(result.status)
        error

    Note:
        - 规范化阶段失败，使下游结果落盘保持简单
        - 所有失败结果的 submittable 和 submitted 都为 False
    """
    return FieldTestResult(
        field_id=field_id,
        field_type=field_type,
        field_name=field_name,
        template_name=template_name,
        simulation_id=simulation_id,
        alpha_id=alpha_id,
        status=status,
        submittable=False,
        submitted=False,
        message=message,
        expression=expression,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
        failed_stage=failed_stage,
        failed_checks=failed_checks,
    )


# ============================================================================
# simulation / checksubmit / submit 三阶段子函数
# ============================================================================

def _handle_stage_error(
    ctx: FieldTestContext,
    failed_stage: str,
    exc: Exception,
    *,
    simulation_id: str | None = None,
    alpha_id: str | None = None,
) -> FieldTestResult:
    """将阶段异常统一转换为 FieldTestResult，同时确保 KeyboardInterrupt 不被吞掉。

    只捕获 BrainAPIError（及子类）和连接/超时等预期异常；KeyboardInterrupt 和
    SystemExit 直接向上传播，保证 Ctrl+C 能正常中断运行。
    """
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise
    return ctx.failure(
        failed_stage=failed_stage,
        message=str(exc),
        simulation_id=simulation_id,
        alpha_id=alpha_id,
    )


def _run_simulation_create(
    ctx: FieldTestContext,
    client: BrainClient,
    args: argparse.Namespace,
    *,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: threading.Semaphore | None = None,
) -> "FieldTestResult | tuple[str, str]":
    """simulation 阶段 (创建): 构建 payload 并创建模拟任务。

    Returns:
        - FieldTestResult: 发生失败，调用方应直接返回
        - Tuple[str, str]: (simulation_location, simulation_id) 继续流水线
    """
    try:
        payload = build_simulation_payload(args, ctx.expression)
        if simulation_settings is not None:
            payload["settings"] = dict(simulation_settings)
        if create_semaphore is not None:
            logger.info(
                "[simulation] waiting for create slot field=%s template=%s",
                ctx.field_id, ctx.template_name,
            )
            _ = create_semaphore.acquire()
        try:
            create_retries: int = args.simulation_create_retries
            simulation_location, simulation_id = create_simulation_with_retry(
                client,
                payload,
                create_retries,
            )
        finally:
            if create_semaphore is not None:
                create_semaphore.release()
        return simulation_location, simulation_id
    except Exception as exc:
        return _handle_stage_error(ctx, "simulation", exc)


def _run_simulation_poll(
    ctx: FieldTestContext,
    client: BrainClient,
    args: argparse.Namespace,
    *,
    simulation_location: str,
    simulation_id: str,
) -> "FieldTestResult | tuple[str, dict[str, Any]]":
    """simulation 阶段 (轮询): 等待模拟完成并提取 alpha_id。

    Returns:
        - FieldTestResult: 发生失败，调用方应直接返回
        - Tuple[str, Dict[str, Any]]: (alpha_id, simulation_result) 继续流水线
    """
    try:
        poll_retries: int = args.simulation_poll_retries
        max_polls: int = args.simulation_max_polls
        max_wait: float = args.simulation_max_wait_seconds
        max_pending: int = args.simulation_max_pending_cycles
        max_queue: float = args.simulation_max_queue_seconds
        simulation_result = poll_simulation_with_retry(
            client,
            simulation_location,
            poll_retries,
            max_polls=max_polls,
            max_wait_seconds=max_wait,
            max_pending_cycles=max_pending,
            max_queue_seconds=max_queue,
        )
        progress = first_non_empty(
            simulation_result.get(API_KEY_PROGRESS),
            simulation_result.get(API_KEY_STATUS),
            simulation_result.get(API_KEY_STATE),
        )
        logger.info(
            "[simulation] completed simulation_id=%s simulation_location=%s progress=%s",
            simulation_id, simulation_location, progress,
        )
        alpha_id = extract_alpha_id(simulation_result)
        if not alpha_id:
            return ctx.failure(
                failed_stage="simulation",
                message=summarize_failure(simulation_result),
                simulation_id=simulation_id,
                status="simulation_failed",
            )
        return alpha_id, simulation_result
    except Exception as exc:
        return _handle_stage_error(
            ctx, "simulation", exc,
            simulation_id=simulation_id,
        )


def _run_checksubmit_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    args: argparse.Namespace,
    *,
    alpha_id: str,
    simulation_id: str,
    simulation_result: dict[str, Any] | None = None,
) -> "FieldTestResult | tuple[bool | None, str, list[dict[str, Any]]]":
    """checksubmit 阶段: 先本地预检指标，达标后再调用 checksubmit API。

    模拟响应中已包含原始 is.sharpe、is.fitness、is.turnover 等指标。
    先用这些指标做一次本地预检：达标才调用 checksubmit API，
    否则直接标记为 precheck_failed 跳过，节省 API 调用。

    Returns:
        - FieldTestResult: 发生失败，调用方应直接返回
        - Tuple[bool, str, list]: (submittable, message, failed_checks) 继续流水线
    """
    # 本地预检：用模拟返回的原始指标判断是否值得提交
    if simulation_result:
        config = PrecheckConfig.from_args(args)
        passed, reason, precheck_failed_checks = precheck_simulation_metrics(
            simulation_result,
            min_sharpe=config.min_sharpe,
            min_fitness=config.min_fitness,
            min_turnover=config.min_turnover,
            max_turnover=config.max_turnover,
            max_weight=config.max_weight,
        )
        if not passed:
            logger.info(
                "[checksubmit-precheck] alpha_id=%s simulation_id=%s precheck_failed=%s",
                alpha_id, simulation_id, reason,
            )
            return False, f"precheck_failed: {reason}", precheck_failed_checks

    try:
        check_retries: int = args.check_submit_retries
        return checksubmit_with_retry(client, alpha_id, check_retries)
    except Exception as exc:
        return _handle_stage_error(
            ctx, "checksubmit", exc,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
        )


def _run_submit_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    args: argparse.Namespace,
    *,
    alpha_id: str,
    simulation_id: str,
    simulation_location: str,
    submittable: bool | None,
) -> "FieldTestResult | tuple[bool, str, str]":
    """submit 阶段: 条件提交 Alpha（仅当 args.submit 且 submittable 为真）。

    Returns:
        - FieldTestResult: 提交失败，调用方应直接返回
        - Tuple[bool, str, str]: (submitted, status, message) 继续流水线
    """
    should_submit: bool = args.submit
    if not (should_submit and submittable):
        return False, STATUS_SIMULATED, ""
    try:
        logger.info(
            "[submit] eligible alpha_id=%s simulation_id=%s simulation_location=%s",
            alpha_id, simulation_id, simulation_location,
        )
        submit_retries: int = args.submit_retries
        message = submit_with_retry(client, alpha_id, submit_retries)
        return True, STATUS_SUBMITTED, message
    except Exception as exc:
        return _handle_stage_error(
            ctx, "submit", exc,
            simulation_id=simulation_id,
            alpha_id=alpha_id,
        )


# ============================================================================
# 字段测试核心执行函数
# ============================================================================

def run_field_test(
    client: BrainClient,
    args: argparse.Namespace,
    field: dict[str, Any],
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: threading.Semaphore | None = None,
) -> FieldTestResult:
    """
    执行单个候选表达式的 simulation / checksubmit / submit 三阶段流程。

    这是字段测试的核心执行函数，协调三个独立的顶层阶段：
    1. simulation 阶段 (_run_simulation_create → _run_simulation_poll)
    2. checksubmit 阶段 (_run_checksubmit_stage)
    3. submit 阶段 (_run_submit_stage)

    Args:
        client: BrainClient 实例。
        args: 命令行参数命名空间。
        field: 字段元数据字典。
        template_name: 模板名称。
        expression: Alpha 表达式。
        settings_fingerprint: 设置配置指纹。
        template_library_fingerprint: 模板库指纹。
        simulation_settings: 模拟设置变体。默认为 None。
        create_semaphore: 创建信号量，用于控制并发创建。默认为 None。

    Returns:
        FieldTestResult: 测试结果对象，包含所有阶段的状态信息。

    Raises:
        ValueError: 当输入参数无效时抛出。

    Note:
        - 任一阶段失败都会立即返回失败结果，不阻塞后续字段
        - 使用信号量控制并发创建，避免速率限制
        - 三个顶层阶段各自由子函数实现，便于测试和调试
    """
    # Input validation
    if not expression or not expression.strip():
        raise ValueError("expression cannot be empty")
    if not template_name or not template_name.strip():
        raise ValueError("template_name cannot be empty")
    if "id" not in field:
        raise ValueError("field must contain 'id' key")
    if not settings_fingerprint:
        raise ValueError("settings_fingerprint cannot be empty")
    if not template_library_fingerprint:
        raise ValueError("template_library_fingerprint cannot be empty")
    ctx = FieldTestContext(
        field_id=str(first_non_empty(field.get("id"), SENTINEL_UNKNOWN)),
        field_type=choose_field_type(field),
        field_name=str(first_non_empty(field.get("name"), field.get("id"), SENTINEL_UNKNOWN)),
        template_name=template_name,
        expression=expression,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
    )

    logger.info(
        "[field] testing %s (%s) template=%s expression: %s",
        ctx.field_id, ctx.field_type, template_name, expression,
    )

    # simulation 阶段 (创建)
    create_result = _run_simulation_create(
        ctx, client, args,
        simulation_settings=simulation_settings,
        create_semaphore=create_semaphore,
    )
    if isinstance(create_result, FieldTestResult):
        return create_result
    simulation_location, simulation_id = create_result

    # simulation 阶段 (轮询等待)
    poll_result = _run_simulation_poll(
        ctx, client, args,
        simulation_location=simulation_location,
        simulation_id=simulation_id,
    )
    if isinstance(poll_result, FieldTestResult):
        return poll_result
    alpha_id, simulation_result = poll_result

    # checksubmit 阶段（先本地预检指标，达标才调 checksubmit API）
    check_result = _run_checksubmit_stage(
        ctx, client, args,
        alpha_id=alpha_id,
        simulation_id=simulation_id,
        simulation_result=simulation_result,
    )
    if isinstance(check_result, FieldTestResult):
        return check_result
    submittable, message, failed_checks = check_result

    # submit 阶段（条件提交）
    submit_result = _run_submit_stage(
        ctx, client, args,
        alpha_id=alpha_id,
        simulation_id=simulation_id,
        simulation_location=simulation_location,
        submittable=submittable,
    )
    if isinstance(submit_result, FieldTestResult):
        return submit_result
    submitted, status, _submit_message = submit_result
    if submitted:
        message = _submit_message

    if submittable:
        logger.info(
            "[submit] submittable alpha_id=%s simulation_id=%s simulation_location=%s",
            alpha_id, simulation_id, simulation_location,
        )

    return ctx.success(
        simulation_id=simulation_id,
        alpha_id=alpha_id,
        submittable=submittable,
        submitted=submitted,
        message=message,
        status=status,
        failed_checks=failed_checks,
    )


def run_field_test_in_worker(
    client_factory: WorkerClientFactory,
    args: argparse.Namespace,
    field: dict[str, Any],
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: SettingsVariant | None = None,
    create_semaphore: threading.Semaphore | None = None,
) -> FieldTestResult:
    """
    工作线程入口，先解析线程本地客户端再执行测试。

    作为工作线程的入口函数，先获取线程本地的已认证客户端，
    然后执行字段测试。

    Args:
        client_factory: WorkerClientFactory 实例。
        args: 命令行参数命名空间。
        field: 字段元数据字典。
        template_name: 模板名称。
        expression: Alpha 表达式。
        settings_fingerprint: 设置配置指纹。
        template_library_fingerprint: 模板库指纹。
        simulation_settings: 模拟设置变体。默认为 None。
        create_semaphore: 创建信号量。默认为 None。

    Returns:
        FieldTestResult: 测试结果对象。

    Example:
        >>> result = run_field_test_in_worker(
        ...     factory, args, field, "ts_mean_20",
        ...     "rank(ts_mean(sales, 20))", "abc123", "def456"
        ... )

    Note:
        - 每个工作线程解析自己的已认证客户端
        - 确保并发 simulation/checksubmit/submit 调用不共享 cookie 或连接状态
    """
    client = client_factory.get_client()
    return run_field_test(
        client,
        args,
        field,
        template_name,
        expression,
        settings_fingerprint,
        template_library_fingerprint,
        simulation_settings,
        create_semaphore,
    )
