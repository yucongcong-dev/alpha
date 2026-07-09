"""Compatibility helpers for domain-adjacent payload coercion."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .domain import FailedCheck


def coerce_failed_check(check: Any) -> FailedCheck:
    """把任意 failed check 兼容对象归一化为领域 FailedCheck。"""
    from .domain import FailedCheck

    if isinstance(check, FailedCheck):
        return check
    if isinstance(check, dict):
        return FailedCheck.from_dict(check)
    return FailedCheck(
        name=str(getattr(check, "name", "") or ""),
        value=getattr(check, "value", None),
        limit=getattr(check, "limit", getattr(check, "threshold", None)),
        result=getattr(check, "result", None),
    )


def serialize_failed_check(check: Any) -> dict[str, Any]:
    """把 failed check 归一化为可 JSON 序列化的字典。"""
    return coerce_failed_check(check).to_dict()


def coerce_failed_checks(checks: Sequence[Any] | None) -> list[FailedCheck]:
    """把 failed checks 序列归一化为 FailedCheck 列表。"""
    if not checks:
        return []
    return [coerce_failed_check(check) for check in checks]
