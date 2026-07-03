"""
simulation 响应解析与失败摘要辅助模块。
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

from ..api.api_types import ApiPayload, CheckResultDict
from ..models.domain import FailedCheck
from ..config.constants import (
    API_KEY_DETAIL,
    API_KEY_ERROR,
    API_KEY_MESSAGE,
    FAILURE_SUMMARY_MAX_LEN,
    MAX_FAILED_CHECK_NAMES,
    SENTINEL_UNKNOWN_CHECK,
)
from ..utils.helpers import first_non_empty

_ALPHA_ID_REGEX: re.Pattern[str] = re.compile(r"/alphas/([^/]+)", re.IGNORECASE)
_RESULT_FAIL: str = "FAIL"
_KEY_ALPHA: str = "alpha"
_KEY_ALPHA_ID: str = "alphaId"
_KEY_CHECKS: str = "checks"
_KEY_CHILDREN: str = "children"
_KEY_ID: str = "id"
_KEY_IS: str = "is"
_KEY_LIMIT: str = "limit"
_KEY_LOCATION: str = "location"
_KEY_NAME: str = "name"
_KEY_RESULT: str = "result"
_KEY_THRESHOLD: str = "threshold"
_KEY_TYPE: str = "type"
_KEY_VALUE: str = "value"
_TYPE_ALPHA: str = "ALPHA"
_RESULT_PENDING: str = "PENDING"


def extract_alpha_id(payload: ApiPayload) -> str | None:
    candidates = [
        payload.get(_KEY_ALPHA),
        payload.get(_KEY_ALPHA_ID),
        payload.get(_KEY_ID) if payload.get(_KEY_TYPE) == _TYPE_ALPHA else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
        if isinstance(candidate, dict):
            cd = cast(ApiPayload, candidate)
            candidate_id = first_non_empty(cd.get(_KEY_ID), cd.get(_KEY_ALPHA))
            if isinstance(candidate_id, str) and candidate_id:
                return candidate_id

    children = payload.get(_KEY_CHILDREN)
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                alpha_id = extract_alpha_id(cast(ApiPayload, child))
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


def extract_checks(alpha_payload: ApiPayload) -> list[CheckResultDict]:
    is_section = alpha_payload.get(_KEY_IS)
    if isinstance(is_section, dict):
        section = cast(ApiPayload, is_section)
        section_checks = section.get(_KEY_CHECKS)
        if isinstance(section_checks, list):
            return section_checks
    checks = alpha_payload.get(_KEY_CHECKS)
    if isinstance(checks, list):
        return checks
    return []


def extract_failed_checks(alpha_payload: ApiPayload) -> list[FailedCheck]:
    failed_checks: list[FailedCheck] = []
    for check in extract_checks(alpha_payload):
        if str(check.get(_KEY_RESULT, "")).upper() != _RESULT_FAIL:
            continue
        failed_checks.append(
            FailedCheck(
                name=str(check.get(_KEY_NAME, "")),
                result=check.get(_KEY_RESULT),
                value=check.get(_KEY_VALUE),
                limit=first_non_empty(check.get(_KEY_LIMIT), check.get(_KEY_THRESHOLD)),
            )
        )
    return failed_checks


def extract_pending_checks(alpha_payload: ApiPayload) -> list[FailedCheck]:
    pending_checks: list[FailedCheck] = []
    for check in extract_checks(alpha_payload):
        if str(check.get(_KEY_RESULT, "")).upper() != _RESULT_PENDING:
            continue
        pending_checks.append(
            FailedCheck(
                name=str(check.get(_KEY_NAME, "")),
                result=check.get(_KEY_RESULT),
                value=check.get(_KEY_VALUE),
                limit=first_non_empty(check.get(_KEY_LIMIT), check.get(_KEY_THRESHOLD)),
            )
        )
    return pending_checks


def is_submittable_from_checks(checks: list[FailedCheck]) -> bool | None:
    if not checks:
        return None
    return all(str(check.result or "").upper() != _RESULT_FAIL for check in checks)


def summarize_failure(payload: ApiPayload | list[Any] | Any) -> str:
    if not isinstance(payload, dict):
        text = json.dumps(payload, ensure_ascii=False)[:FAILURE_SUMMARY_MAX_LEN]
        return text or "unknown error"

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
            str(check.get(_KEY_NAME, SENTINEL_UNKNOWN_CHECK))
            for check in failed[:MAX_FAILED_CHECK_NAMES]
        )
        return f"failed checks: {names}"

    text = json.dumps(payload, ensure_ascii=False)[:FAILURE_SUMMARY_MAX_LEN]
    return text or "unknown error"


__all__ = [
    "extract_alpha_id",
    "extract_checks",
    "extract_failed_checks",
    "extract_pending_checks",
    "is_submittable_from_checks",
    "summarize_failure",
]
