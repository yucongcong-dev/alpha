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

import argparse
import json
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from ..api.client import (
    BrainClient,
    WorkerClientFactory,
    first_non_empty,
    retry_operation,
)
from ..config import (
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

# ============================================================================
# Alpha ID 提取与解析函数
# ============================================================================

def extract_alpha_id(payload: Dict[str, Any]) -> Optional[str]:
    """
    从结构不稳定的模拟返回中提取 Alpha ID。

    由于 API 响应格式在不同端点上不一致，此函数会检查多种可能的结构形态，
    以可靠地提取 Alpha ID。

    Args:
        payload: 模拟任务的响应 JSON 字典。

    Returns:
        Optional[str]: Alpha ID 字符串，如果未找到则返回 None。

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
        payload.get("alpha"),
        payload.get("alphaId"),
        payload.get("id") if payload.get("type") == "ALPHA" else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
        if isinstance(candidate, dict):
            candidate_id = first_non_empty(candidate.get("id"), candidate.get("alpha"))
            if isinstance(candidate_id, str) and candidate_id:
                return candidate_id

    children = payload.get("children")
    if isinstance(children, list):
        for child in children:
            alpha_id = extract_alpha_id(child if isinstance(child, dict) else {})
            if alpha_id:
                return alpha_id

    location = payload.get("location")
    if isinstance(location, str):
        match = re.search(r"/alphas/([^/]+)", location)
        if match:
            return match.group(1)
    return None


# ============================================================================
# 检查项提取与分析函数
# ============================================================================

def extract_checks(alpha_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从嵌套或顶层 Alpha 结构中提取 check-submit 检查项。

    检查项可能位于 alpha.is.checks 或顶层 checks 字段中，
    此函数会检查这两种位置。

    Args:
        alpha_payload: Alpha 详情的 JSON 字典。

    Returns:
        List[Dict[str, Any]]: 检查项列表，如果未找到则返回空列表。

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
    is_section = alpha_payload.get("is")
    if isinstance(is_section, dict) and isinstance(is_section.get("checks"), list):
        return is_section["checks"]
    checks = alpha_payload.get("checks")
    if isinstance(checks, list):
        return checks
    return []


def extract_failed_checks(alpha_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    仅提取失败检查项，并转换为适合结果持久化的紧凑结构。

    从检查项列表中筛选出 result 为 FAIL 的检查项，
    并提取关键信息构建紧凑的结构。

    Args:
        alpha_payload: Alpha 详情的 JSON 字典。

    Returns:
        List[Dict[str, Any]]: 失败检查项的紧凑列表，包含：
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
    failed_checks: List[Dict[str, Any]] = []
    for check in extract_checks(alpha_payload):
        if str(check.get("result", "")).upper() != "FAIL":
            continue
        failed_checks.append(
            {
                "name": check.get("name"),
                "result": check.get("result"),
                "value": check.get("value"),
                "limit": first_non_empty(check.get("limit"), check.get("threshold")),
            }
        )
    return failed_checks


def is_submittable_from_checks(checks: List[Dict[str, Any]]) -> Optional[bool]:
    """
    将检查项列表折叠为 True、False 或 None 三态结果。

    根据检查项的结果判断 Alpha 是否可提交：
    - 如果所有检查项都通过，返回 True
    - 如果有任何检查项失败，返回 False
    - 如果检查项列表为空，返回 None

    Args:
        checks: 检查项列表。

    Returns:
        Optional[bool]: 可提交状态，True 表示可提交，
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
    return all(str(check.get("result", "")).upper() != "FAIL" for check in checks)


# ============================================================================
# 模拟指标预检函数
# ============================================================================

def precheck_simulation_metrics(
    simulation_result: Dict[str, Any],
    *,
    min_sharpe: float = SUBMIT_MIN_SHARPE,
    min_fitness: float = SUBMIT_MIN_FITNESS,
    min_turnover: float = SUBMIT_MIN_TURNOVER,
    max_turnover: float = SUBMIT_MAX_TURNOVER,
    max_weight: float = SUBMIT_MAX_WEIGHT,
) -> tuple:
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

    Example:
        >>> result = {"is": {"sharpe": 0.8, "fitness": 0.5, "turnover": 0.15}}
        >>> passed, reason, checks = precheck_simulation_metrics(result)
        >>> print(passed)
        False
        >>> print(reason)
        'sharpe=0.8000 < 1.25; fitness=0.5000 < 1.00'

    Note:
        - 如果 is 段缺失或指标无法提取，返回 passed=True（回退到 checksubmit）
        - 阈值可被调用方覆盖以适应不同的 universe/region 设置
        - 构造的 failed_checks 结构与真实 checksubmit 返回一致
    """
    is_section = simulation_result.get("is")
    if not isinstance(is_section, dict):
        return True, "", []

    sharpe = is_section.get("sharpe")
    fitness = is_section.get("fitness")
    turnover = is_section.get("turnover")
    max_stock_weight = (
        is_section.get("maxWeight")
        or is_section.get("max_weight")
        or is_section.get("concentratedWeight")
    )

    failures: list = []

    if isinstance(sharpe, (int, float)) and sharpe < min_sharpe:
        failures.append(
            {
                "name": "LOW_SHARPE",
                "result": "FAIL",
                "value": float(sharpe),
                "limit": min_sharpe,
            }
        )
    if isinstance(fitness, (int, float)) and fitness < min_fitness:
        failures.append(
            {
                "name": "LOW_FITNESS",
                "result": "FAIL",
                "value": float(fitness),
                "limit": min_fitness,
            }
        )
    if isinstance(turnover, (int, float)):
        if turnover < min_turnover:
            failures.append(
                {
                    "name": "LOW_TURNOVER",
                    "result": "FAIL",
                    "value": float(turnover),
                    "limit": min_turnover,
                }
            )
        elif turnover > max_turnover:
            failures.append(
                {
                    "name": "HIGH_TURNOVER",
                    "result": "FAIL",
                    "value": float(turnover),
                    "limit": max_turnover,
                }
            )
    if isinstance(max_stock_weight, (int, float)) and max_stock_weight > max_weight:
        failures.append(
            {
                "name": "CONCENTRATED_WEIGHT",
                "result": "FAIL",
                "value": float(max_stock_weight),
                "limit": max_weight,
            }
        )

    if not failures:
        return True, "", []

    reason_parts = []
    for f in failures:
        reason_parts.append(
            f"{f['name'].lower()}: {f['value']:.4f} vs limit {f['limit']}"
        )
    return False, "; ".join(reason_parts), failures


# ============================================================================
# 失败摘要函数
# ============================================================================

def summarize_failure(payload: Dict[str, Any]) -> str:
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
    detail = first_non_empty(payload.get("detail"), payload.get("message"), payload.get("error"))
    if detail:
        return str(detail)

    checks = extract_checks(payload)
    failed = [check for check in checks if str(check.get("result", "")).upper() == "FAIL"]
    if failed:
        names = ", ".join(str(check.get("name", "UNKNOWN")) for check in failed[:5])
        return f"failed checks: {names}"

    text = json.dumps(payload, ensure_ascii=False)[:300]
    return text or "unknown error"


# ============================================================================
# simulation 阶段函数 (创建 + 轮询)
# ============================================================================

def create_simulation_with_retry(
    client: BrainClient,
    payload: Dict[str, Any],
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
        Tuple[str, str]: 返回一个元组，包含两个元素：
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
        retry_wait_seconds=3.0,
    )
    simulation_id_match = re.search(r"/simulations/([^/]+)", simulation_location)
    simulation_id = simulation_id_match.group(1) if simulation_id_match else simulation_location
    print(
        f"[simulation] created simulation_id={simulation_id} location={simulation_location}",
        flush=True,
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
) -> Dict[str, Any]:
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
        Dict[str, Any]: 模拟完成的响应 JSON 字典。

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
        retry_wait_seconds=3.0,
    )


# ============================================================================
# checksubmit & submit 阶段函数
# ============================================================================

def checksubmit_with_retry(
    client: BrainClient,
    alpha_id: str,
    retries: int,
) -> tuple[Optional[bool], str, List[Dict[str, Any]]]:
    """
    获取 Alpha 检查结果并转成可提交状态输出。

    获取 Alpha 的检查结果，判断是否可提交，并提取失败的检查项。

    Args:
        client: BrainClient 实例。
        alpha_id: Alpha 的唯一标识符。
        retries: 最大重试次数。

    Returns:
        Tuple[Optional[bool], str, List[Dict[str, Any]]]: 返回一个元组，包含三个元素：
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
        retry_wait_seconds=3.0,
    )
    checks = extract_checks(alpha_detail)
    submittable = is_submittable_from_checks(checks)
    failed_checks = extract_failed_checks(alpha_detail)
    message = "checks unavailable" if submittable is None else "checks passed" if submittable else "checks failed"
    print(
        f"[checksubmit] alpha_id={alpha_id} submittable={submittable} message={message}",
        flush=True,
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
        retry_wait_seconds=3.0,
    )
    if submit_result.get("status") == "failed":
        return summarize_failure(submit_result)
    return "submitted"


# ============================================================================
# 结果构建函数
# ============================================================================

def build_failure_result(
    *,
    field_id: str,
    field_type: str,
    field_name: str,
    template_name: str,
    simulation_id: Optional[str],
    alpha_id: Optional[str],
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    failed_stage: str,
    message: str,
    status: str = "error",
    failed_checks: Optional[List[Dict[str, Any]]] = None,
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

def _run_simulation_create(
    ctx: FieldTestContext,
    client: BrainClient,
    args: argparse.Namespace,
    *,
    simulation_settings: Optional[SettingsVariant] = None,
    create_semaphore: Optional[threading.Semaphore] = None,
) -> "FieldTestResult | Tuple[str, str]":
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
            print(
                f"[simulation] waiting for create slot field={ctx.field_id} template={ctx.template_name}",
                flush=True,
            )
            create_semaphore.acquire()
        try:
            simulation_location, simulation_id = create_simulation_with_retry(
                client,
                payload,
                args.simulation_create_retries,
            )
        finally:
            if create_semaphore is not None:
                create_semaphore.release()
        return simulation_location, simulation_id
    except Exception as exc:
        return ctx.failure(failed_stage="simulation", message=str(exc))


def _run_simulation_poll(
    ctx: FieldTestContext,
    client: BrainClient,
    args: argparse.Namespace,
    *,
    simulation_location: str,
    simulation_id: str,
) -> "FieldTestResult | Tuple[str, Dict[str, Any]]":
    """simulation 阶段 (轮询): 等待模拟完成并提取 alpha_id。

    Returns:
        - FieldTestResult: 发生失败，调用方应直接返回
        - Tuple[str, Dict[str, Any]]: (alpha_id, simulation_result) 继续流水线
    """
    try:
        simulation_result = poll_simulation_with_retry(
            client,
            simulation_location,
            args.simulation_poll_retries,
            max_polls=args.simulation_max_polls,
            max_wait_seconds=args.simulation_max_wait_seconds,
            max_pending_cycles=args.simulation_max_pending_cycles,
            max_queue_seconds=args.simulation_max_queue_seconds,
        )
        progress = first_non_empty(
            simulation_result.get("progress"),
            simulation_result.get("status"),
            simulation_result.get("state"),
        )
        print(
            f"[simulation] completed simulation_id={simulation_id} "
            f"simulation_location={simulation_location} progress={progress}",
            flush=True,
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
        return ctx.failure(
            failed_stage="simulation",
            message=str(exc),
            simulation_id=simulation_id,
        )


def _run_checksubmit_stage(
    ctx: FieldTestContext,
    client: BrainClient,
    args: argparse.Namespace,
    *,
    alpha_id: str,
    simulation_id: str,
    simulation_result: Optional[Dict[str, Any]] = None,
) -> "FieldTestResult | Tuple[Optional[bool], str, List[Dict[str, Any]]]":
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
        passed, reason, precheck_failed_checks = precheck_simulation_metrics(
            simulation_result
        )
        if not passed:
            print(
                f"[checksubmit-precheck] alpha_id={alpha_id} simulation_id={simulation_id} "
                f"precheck_failed={reason}",
                flush=True,
            )
            return False, f"precheck_failed: {reason}", precheck_failed_checks

    try:
        return checksubmit_with_retry(client, alpha_id, args.check_submit_retries)
    except Exception as exc:
        return ctx.failure(
            failed_stage="checksubmit",
            message=str(exc),
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
    submittable: Optional[bool],
) -> "FieldTestResult | Tuple[bool, str, str]":
    """submit 阶段: 条件提交 Alpha（仅当 args.submit 且 submittable 为真）。

    Returns:
        - FieldTestResult: 提交失败，调用方应直接返回
        - Tuple[bool, str, str]: (submitted, status, message) 继续流水线
    """
    if not (args.submit and submittable):
        return False, "simulated", ""
    try:
        print(
            f"[submit] eligible alpha_id={alpha_id} "
            f"simulation_id={simulation_id} simulation_location={simulation_location}",
            flush=True,
        )
        message = submit_with_retry(client, alpha_id, args.submit_retries)
        return True, "submitted", message
    except Exception as exc:
        return ctx.failure(
            failed_stage="submit",
            message=str(exc),
            simulation_id=simulation_id,
            alpha_id=alpha_id,
        )


# ============================================================================
# 字段测试核心执行函数
# ============================================================================

def run_field_test(
    client: BrainClient,
    args: argparse.Namespace,
    field: Dict[str, Any],
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: Optional[SettingsVariant] = None,
    create_semaphore: Optional[threading.Semaphore] = None,
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

    Note:
        - 任一阶段失败都会立即返回失败结果，不阻塞后续字段
        - 使用信号量控制并发创建，避免速率限制
        - 三个顶层阶段各自由子函数实现，便于测试和调试
    """
    ctx = FieldTestContext(
        field_id=str(first_non_empty(field.get("id"), "UNKNOWN")),
        field_type=choose_field_type(field),
        field_name=str(first_non_empty(field.get("name"), field.get("id"), "UNKNOWN")),
        template_name=template_name,
        expression=expression,
        settings_fingerprint=settings_fingerprint,
        template_library_fingerprint=template_library_fingerprint,
    )

    print(
        f"[field] testing {ctx.field_id} ({ctx.field_type}) "
        f"template={template_name} expression: {expression}",
        flush=True,
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
        print(
            f"[submit] submittable alpha_id={alpha_id} "
            f"simulation_id={simulation_id} simulation_location={simulation_location}",
            flush=True,
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
    field: Dict[str, Any],
    template_name: str,
    expression: str,
    settings_fingerprint: str,
    template_library_fingerprint: str,
    simulation_settings: Optional[SettingsVariant] = None,
    create_semaphore: Optional[threading.Semaphore] = None,
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
