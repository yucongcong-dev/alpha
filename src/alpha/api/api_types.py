"""API 类型定义

本模块定义 Brain API 交互中的 TypedDict，用于增强 JSON
响应数据的类型安全性和 IDE 自动补全支持。
"""

from __future__ import annotations

from typing import Any, TypedDict

ApiPayload = dict[str, Any]
ApiParams = dict[str, Any]
ApiResultList = list[dict[str, Any]]
SimulationPayload = dict[str, Any]


class SimulationAlphaResult(TypedDict, total=False):
    """模拟 Alpha 结果的结构定义。"""

    id: str
    status: str
    alpha: str
    expression: str | None
    is_: ApiPayload
    os_: ApiPayload
    settings: ApiPayload
    regular: str | None
    submittable: bool | None
    failed_checks: list["CheckResultDict"] | None


class SimulationResponsePayload(TypedDict, total=False):
    """Brain API 模拟任务响应结构。"""

    id: str | None
    status: str | None
    queue_position: int | None
    detail: str | None
    retry_after: int | None
    result: SimulationAlphaResult | None


class FieldInfoDict(TypedDict, total=False):
    """Brain API 返回的数据集字段信息结构。"""

    id: str
    name: str | None
    type: str | None
    fieldType: str | None
    category: str | None
    mnemonic: str | None
    field: str | None


class CheckResultDict(TypedDict, total=False):
    """模拟结果中的检查项结构。"""

    name: str
    value: float | None
    result: str | None
    limit: float | None
