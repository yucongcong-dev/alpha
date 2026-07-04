"""结果判断谓词。

纯 FieldTestResult 上的判断函数，无策略或分析依赖。
供 policy、analysis、core 等多包复用，避免反向循环依赖。
"""

from __future__ import annotations

from .domain import FieldTestResult

_CHECK_SELF_CORRELATION = "SELF_CORRELATION"
_RESULT_PENDING = "PENDING"
STATUS_PENDING_SELF_CORRELATION = "pending_self_correlation"


def is_queue_timeout_result(result: FieldTestResult) -> bool:
    """判断结果是否只是平台队列超时，而非 Alpha 质量反馈。"""
    message = str(result.message or "").lower()
    return result.failed_stage == "simulation" and (
        "queue budget" in message
        or "queued too long" in message
        or "stayed queued too long" in message
    )


def is_self_correlation_pending_result(result: FieldTestResult) -> bool:
    """判断结果是否仍停留在 SELF_CORRELATION 异步校验阶段。"""
    if result.status == STATUS_PENDING_SELF_CORRELATION:
        return True
    checks = result.failed_checks or []
    return any(
        str(check.get("name", "")).upper() == _CHECK_SELF_CORRELATION
        and str(check.get("result", "")).upper() == _RESULT_PENDING
        for check in checks
    )


def is_informative_result(result: FieldTestResult) -> bool:
    """判断结果是否应参与模板/字段质量学习。"""
    return not is_queue_timeout_result(result) and not is_self_correlation_pending_result(result)