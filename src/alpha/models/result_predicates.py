"""结果判断谓词。

纯 FieldTestResult 上的判断函数，无策略或分析依赖。
供 policy、analysis、core 等多包复用，避免反向循环依赖。
"""

from __future__ import annotations

from ..config._constants_strings import (
    STATUS_ERROR,
    STATUS_SKIPPED,
)
from .domain import FieldTestResult


def has_pending_checks(result: FieldTestResult) -> bool:
    """Return whether the platform reported a semantic PENDING check.

    A transport/API response with no usable checks is deliberately not treated
    as semantic PENDING.  Callers that own a bounded retry budget should use
    :func:`needs_submission_check_refresh` instead.
    """
    if any(str(check.result or "").upper() == "PENDING" for check in result.failed_checks or []):
        return True
    if result.submittable is False:
        return False
    message = str(result.message or "").strip().lower()
    return message == "checks pending"


def is_submission_check_unavailable(result: FieldTestResult) -> bool:
    """Return whether a submission-check read exhausted its transport budget."""
    if result.submittable is not None or has_pending_checks(result):
        return False
    return str(result.message or "").strip().lower() == "checks unavailable"


def needs_submission_check_refresh(result: FieldTestResult) -> bool:
    """Return whether a persisted result should receive a bounded status refresh."""
    return has_pending_checks(result) or is_submission_check_unavailable(result)


def is_queue_timeout_result(result: FieldTestResult) -> bool:
    """判断结果是否只是平台队列超时，而非 Alpha 质量反馈。"""
    message = str(result.message or "").lower()
    return result.failed_stage == "simulation" and (
        "queue budget" in message
        or "queued too long" in message
        or "stayed queued too long" in message
    )


def is_retryable_infrastructure_result(result: FieldTestResult) -> bool:
    """Return whether a failed candidate should be retried instead of learned from."""
    return result.status == STATUS_ERROR and result.failed_stage in {"simulation", "worker"}


def is_attempted_result(result: FieldTestResult) -> bool:
    """Return whether a persisted result is terminal for candidate de-duplication."""
    return result.status != STATUS_SKIPPED and not is_retryable_infrastructure_result(result)


def is_informative_result(result: FieldTestResult) -> bool:
    """判断结果是否应参与模板/字段质量学习。"""
    return result.status not in {STATUS_ERROR, STATUS_SKIPPED} and not is_queue_timeout_result(
        result
    )


def is_feedback_eligible_result(result: FieldTestResult) -> bool:
    """Return whether a terminal result may influence adaptive research feedback."""
    return (
        is_informative_result(result)
        and not has_pending_checks(result)
        and not is_submission_check_unavailable(result)
    )
