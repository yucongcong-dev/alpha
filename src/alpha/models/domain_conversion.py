"""Compatibility helpers for domain-adjacent payload coercion."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .domain import (
    FailedCheck,
)
from .domain import (
    coerce_failed_check as _coerce_failed_check,
)
from .domain import (
    coerce_failed_checks as _coerce_failed_checks,
)
from .domain import (
    serialize_failed_check as _serialize_failed_check,
)


def coerce_failed_check(check: Any) -> FailedCheck:
    """把任意 failed check 兼容对象归一化为领域 FailedCheck。"""
    return _coerce_failed_check(check)


def serialize_failed_check(check: Any) -> dict[str, Any]:
    """把 failed check 归一化为可 JSON 序列化的字典。"""
    return _serialize_failed_check(check)


def coerce_failed_checks(checks: Sequence[Any] | None) -> list[FailedCheck]:
    """把 failed checks 序列归一化为 FailedCheck 列表。"""
    return _coerce_failed_checks(checks)
