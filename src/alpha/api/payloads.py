"""
Brain API 响应 payload 解析工具。
"""

from __future__ import annotations

import json
from typing import Any

from ..utils.helpers import first_non_empty
from .api_types import ApiPayload, ApiResultList


def safe_json_bytes(content: bytes) -> ApiPayload:
    """安全解码 JSON 字节内容，并保留可调试的原始文本回退。"""
    try:
        data = json.loads(content.decode("utf-8"))
        if isinstance(data, dict):
            return data
        return {"data": data}
    except ValueError:
        return {"text": content.decode("utf-8", errors="replace")[:500]}


def simulation_payload_is_pending(payload: ApiPayload) -> tuple[bool, str, Any]:
    """从 simulation 响应体判断任务是否仍在等待。"""
    status = str(first_non_empty(payload.get("status"), payload.get("state"), "")).upper()
    progress = first_non_empty(payload.get("progress"), payload.get("stage"), "")
    return status in {"PENDING", "RUNNING", "QUEUED"}, status, progress


def extract_total(payload: ApiPayload) -> int | None:
    """在接口提供时提取总数元数据。"""
    for key in ("count", "total", "total_count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return None


def normalize_results(payload: ApiPayload) -> ApiResultList:
    """从响应负载中规范化提取结果列表。"""
    for key in ("results", "items", "data", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []
